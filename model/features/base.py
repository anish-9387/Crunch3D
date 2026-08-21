"""features/base.py — the modular feature-extractor interface (§2 System B).

Every cue is an independent extractor with a declared tier, dimension and set of
requirements, so the pipeline stays extensible and a single cue can be masked by
name for the §62 ablation without touching model code.

Extractors receive a ``MeshContext`` rather than a bare Trimesh.  It exposes the
same mesh plus lazily-cached shared derivations (edge mapping, curvature, the
19-cue descriptor), so N extractors cost one traversal instead of N.
"""

from __future__ import annotations

import dataclasses
from functools import cached_property

import numpy as np

_EPS = 1e-12


class MeshContext:
    """A mesh plus the shared intermediates its feature extractors need."""

    def __init__(self, mesh, normalize: bool = True):
        from ..geometry.normalize import normalize_points

        self.mesh = mesh
        self.faces = np.asarray(mesh.faces, dtype=np.int64)
        raw = np.asarray(mesh.vertices, dtype=np.float64)
        self.raw_verts = raw
        if normalize:
            self.verts, self.normalization = normalize_points(raw)
        else:
            from ..geometry.normalize import Normalization

            self.verts, self.normalization = raw, Normalization(np.zeros(3), 1.0)

    @property
    def n_verts(self) -> int:
        return len(self.verts)

    @cached_property
    def diagonal(self) -> float:
        if self.n_verts == 0:
            return 1.0
        span = float(np.linalg.norm(self.raw_verts.max(axis=0) - self.raw_verts.min(axis=0)))
        return span if span > _EPS else 1.0

    @cached_property
    def descriptor(self):
        """The shipped 19-cue edge descriptor — single source of truth per cue."""
        from ..importance.edge_features import compute_edge_feature_importance

        return compute_edge_feature_importance(
            self.mesh, vertex_importance=self.vertex_importance
        )

    @cached_property
    def edges(self) -> np.ndarray:
        return self.descriptor.edges

    @cached_property
    def vertex_importance(self) -> np.ndarray:
        from ..importance.importance_mapper import compute_importance

        return compute_importance(self.mesh)

    @cached_property
    def vertex_normals(self) -> np.ndarray:
        return np.asarray(self.mesh.vertex_normals, dtype=np.float64)

    @cached_property
    def mean_curvature(self) -> np.ndarray:
        from ..importance.edge_features import _vertex_mean_curvature

        return _vertex_mean_curvature(self.mesh)

    @cached_property
    def gaussian_curvature(self) -> np.ndarray:
        from ..importance.edge_features import _vertex_gaussian_curvature

        return _vertex_gaussian_curvature(self.verts, self.faces)

    @cached_property
    def valence(self) -> np.ndarray:
        counts = np.zeros(self.n_verts, dtype=np.float64)
        edges = self.edges
        if len(edges):
            np.add.at(counts, edges[:, 0], 1.0)
            np.add.at(counts, edges[:, 1], 1.0)
        return counts

    @cached_property
    def boundary_vertex(self) -> np.ndarray:
        flags = np.zeros(self.n_verts, dtype=np.float64)
        boundary = self.descriptor.features.get("boundary_edge_flag")
        if boundary is not None and len(self.edges):
            mask = boundary > 0.5
            flags[self.edges[mask, 0]] = 1.0
            flags[self.edges[mask, 1]] = 1.0
        return flags

    @cached_property
    def total_area(self) -> float:
        p0, p1, p2 = (
            self.verts[self.faces[:, 0]],
            self.verts[self.faces[:, 1]],
            self.verts[self.faces[:, 2]],
        )
        area = 0.5 * float(np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1).sum())
        return area if area > _EPS else 1.0


class FeatureExtractor:
    """One named cue.  Subclasses set the class attributes and implement compute."""

    name: str = ""
    requires: list[str] = []
    output_dim: int = 1
    tier: str = "A"
    domain: str = "vertex"
    """``vertex`` or ``edge`` — which matrix the columns land in."""

    def available(self, mesh: MeshContext) -> bool:
        return True

    def compute(self, mesh: MeshContext) -> np.ndarray:
        raise NotImplementedError

    def columns(self) -> list[str]:
        if self.output_dim == 1:
            return [self.name]
        return [f"{self.name}_{i}" for i in range(self.output_dim)]

    def zeros(self, mesh: MeshContext) -> np.ndarray:
        rows = mesh.n_verts if self.domain == "vertex" else len(mesh.edges)
        return np.zeros((rows, self.output_dim), dtype=np.float32)


@dataclasses.dataclass
class FeatureSet:
    """The §2 extraction result: vertex matrix, edge matrix, graph, metadata."""

    vertex: np.ndarray
    vertex_names: list[str]
    edge: np.ndarray
    edge_names: list[str]
    edges: np.ndarray
    present: dict[str, bool]
    metadata: dict

    def column(self, name: str) -> np.ndarray | None:
        if name in self.edge_names:
            return self.edge[:, self.edge_names.index(name)]
        if name in self.vertex_names:
            return self.vertex[:, self.vertex_names.index(name)]
        return None

    def summary(self) -> dict:
        return {
            "vertex_dim": int(self.vertex.shape[1]),
            "edge_dim": int(self.edge.shape[1]),
            "vertices": int(self.vertex.shape[0]),
            "edges": int(self.edge.shape[0]),
            "present": dict(self.present),
            **self.metadata,
        }


def percentile_norm(values: np.ndarray, percentile: float = 95.0) -> np.ndarray:
    """Robust [0, 1] scaling shared by the continuous cues."""
    values = np.abs(np.asarray(values, dtype=np.float64))
    if values.size == 0:
        return values.astype(np.float32)
    ceiling = float(np.percentile(values, percentile))
    if ceiling <= _EPS:
        return np.zeros_like(values, dtype=np.float32)
    return np.clip(values / ceiling, 0.0, 1.0).astype(np.float32)
