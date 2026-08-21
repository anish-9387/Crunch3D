"""geometry/validation.py — mesh validation report (§5.2).

Detects the defect classes the plan enumerates and reports counts.  Nothing is
deleted unless ``repair=True``, and even then only the unambiguously safe
repairs (unreferenced vertices, zero-area faces, exact duplicate faces) are
applied — the report is the product, not a silent rewrite.
"""

from __future__ import annotations

import dataclasses

import numpy as np

_DUP_EPS_FRACTION = 1e-8
_AREA_EPS_FRACTION = 1e-12


@dataclasses.dataclass
class ValidationReport:
    vertices: int
    faces: int
    boundary_edges: int
    non_manifold_edges: int
    non_manifold_vertices: int
    degenerate_faces: int
    duplicate_faces: int
    duplicate_vertices: int
    isolated_vertices: int
    inconsistent_winding: int
    components: int
    nan_vertices: int

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @property
    def is_clean(self) -> bool:
        return (
            self.nan_vertices == 0
            and self.non_manifold_edges == 0
            and self.degenerate_faces == 0
            and self.duplicate_faces == 0
            and self.inconsistent_winding == 0
        )


def _edge_incidence(faces: np.ndarray, n_verts: int) -> tuple[np.ndarray, np.ndarray]:
    """Undirected edge keys and their face-incidence counts."""
    src = faces.ravel()
    dst = faces[:, [1, 2, 0]].ravel()
    keys = np.minimum(src, dst) * np.int64(max(n_verts, 1)) + np.maximum(src, dst)
    return np.unique(keys, return_counts=True)


def _component_count(faces: np.ndarray, n_verts: int) -> int:
    if len(faces) == 0:
        return 0
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    src = faces.ravel()
    dst = faces[:, [1, 2, 0]].ravel()
    adjacency = coo_matrix(
        (np.ones(len(src), dtype=np.int8), (src, dst)), shape=(n_verts, n_verts)
    )
    labels = connected_components(adjacency, directed=False, return_labels=True)[1]
    return int(len(np.unique(labels[np.unique(faces)])))


def validate(verts: np.ndarray, faces: np.ndarray) -> ValidationReport:
    """Build a defect report for a raw vertex/face array pair."""
    verts = np.asarray(verts, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    n_verts, n_faces = len(verts), len(faces)

    nan_vertices = int(np.sum(~np.isfinite(verts).all(axis=1))) if n_verts else 0

    if n_faces == 0:
        return ValidationReport(
            vertices=n_verts, faces=0, boundary_edges=0, non_manifold_edges=0,
            non_manifold_vertices=0, degenerate_faces=0, duplicate_faces=0,
            duplicate_vertices=0, isolated_vertices=n_verts,
            inconsistent_winding=0, components=0, nan_vertices=nan_vertices,
        )

    finite = verts[np.isfinite(verts).all(axis=1)]
    diagonal = (
        float(np.linalg.norm(finite.max(axis=0) - finite.min(axis=0)))
        if len(finite) else 0.0
    )

    p0, p1, p2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    areas = 0.5 * np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1)
    area_floor = max(_AREA_EPS_FRACTION * diagonal * diagonal, 0.0)
    degenerate = int(np.sum(~np.isfinite(areas) | (areas <= area_floor)))

    sorted_faces = np.sort(faces, axis=1)
    duplicate_faces = n_faces - len(np.unique(sorted_faces, axis=0))

    _, counts = _edge_incidence(faces, n_verts)
    boundary_edges = int(np.sum(counts == 1))
    non_manifold_edges = int(np.sum(counts > 2))

    directed = np.column_stack([
        faces.ravel(), faces[:, [1, 2, 0]].ravel()
    ])
    _, directed_counts = np.unique(directed, axis=0, return_counts=True)
    inconsistent_winding = int(np.sum(directed_counts > 1))

    referenced = np.zeros(n_verts, dtype=bool)
    referenced[np.unique(faces)] = True
    isolated = int(np.sum(~referenced))

    duplicate_vertices = 0
    if diagonal > 0.0 and len(finite) > 1:
        quantized = np.round(verts / max(diagonal * _DUP_EPS_FRACTION, 1e-12))
        duplicate_vertices = n_verts - len(np.unique(quantized, axis=0))

    non_manifold_vertices = _count_non_manifold_vertices(faces, n_verts)

    return ValidationReport(
        vertices=n_verts,
        faces=n_faces,
        boundary_edges=boundary_edges,
        non_manifold_edges=non_manifold_edges,
        non_manifold_vertices=non_manifold_vertices,
        degenerate_faces=degenerate,
        duplicate_faces=int(duplicate_faces),
        duplicate_vertices=int(duplicate_vertices),
        isolated_vertices=isolated,
        inconsistent_winding=inconsistent_winding,
        components=_component_count(faces, n_verts),
        nan_vertices=nan_vertices,
    )


def _face_adjacency(faces: np.ndarray, n_verts: int) -> list[list[int]]:
    """Face -> faces sharing an edge with it."""
    n_faces = len(faces)
    src = faces.ravel()
    dst = faces[:, [1, 2, 0]].ravel()
    keys = np.minimum(src, dst) * np.int64(max(n_verts, 1)) + np.maximum(src, dst)
    face_of = np.repeat(np.arange(n_faces, dtype=np.int64), 3)

    order = np.argsort(keys, kind="stable")
    sorted_keys, sorted_faces = keys[order], face_of[order]
    boundaries = np.flatnonzero(
        np.concatenate(([True], sorted_keys[1:] != sorted_keys[:-1]))
    )
    boundaries = np.concatenate((boundaries, [len(sorted_keys)]))

    neighbours: list[list[int]] = [[] for _ in range(n_faces)]
    for start, end in zip(boundaries[:-1], boundaries[1:]):
        group = sorted_faces[start:end]
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = int(group[i]), int(group[j])
                neighbours[a].append(b)
                neighbours[b].append(a)
    return neighbours


def _count_non_manifold_vertices(faces: np.ndarray, n_verts: int) -> int:
    """Vertices whose incident faces form more than one fan (a pinch point)."""
    neighbours = _face_adjacency(faces, n_verts)

    flat_v = faces.ravel()
    flat_f = np.repeat(np.arange(len(faces), dtype=np.int64), 3)
    order = np.argsort(flat_v, kind="stable")
    sorted_v, sorted_f = flat_v[order], flat_f[order]
    lo = np.searchsorted(sorted_v, np.arange(n_verts), side="left")
    hi = np.searchsorted(sorted_v, np.arange(n_verts), side="right")

    count = 0
    for v in range(n_verts):
        fan = sorted_f[lo[v]:hi[v]]
        if len(fan) < 2:
            continue
        remaining = {int(f) for f in fan}
        seed = next(iter(remaining))
        stack = [seed]
        reached = {seed}
        while stack:
            face = stack.pop()
            for other in neighbours[face]:
                if other in remaining and other not in reached:
                    reached.add(other)
                    stack.append(other)
        if len(reached) != len(remaining):
            count += 1
    return count
