"""
learning/features.py — Geometry-aware per-vertex feature computation.

Computes scale-invariant features that generalize across meshes:
  [mean_curvature, gaussian_curvature, dihedral_angle, valence, boundary_flag, uv_stretch]

These features are shared between training (dataset.py) and inference (inference.py).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import trimesh

logger = logging.getLogger(__name__)

NUM_FEATURES = 6


def compute_vertex_features(mesh: "trimesh.Trimesh") -> np.ndarray:
    """Compute 6 geometry-aware features per vertex.

    Features (all scale-invariant):
        0: mean_curvature     — discrete mean curvature, percentile-normalized
        1: gaussian_curvature — discrete Gaussian curvature (angle defect), percentile-normalized
        2: dihedral_angle     — mean dihedral angle of adjacent edges, normalized to [0,1]
        3: valence            — vertex degree / max_degree (how many edges connect)
        4: boundary_flag      — 1.0 if vertex is on a boundary edge, else 0.0
        5: uv_stretch         — UV stretch ratio if UVs present, else 0.0

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Input mesh.

    Returns
    -------
    features : (V, 6) float32 array
        Per-vertex feature matrix.
    """
    n_verts = len(mesh.vertices)
    features = np.zeros((n_verts, NUM_FEATURES), dtype=np.float32)

    # ── Feature 0: Mean curvature ─────────────────────────────────────────
    features[:, 0] = _mean_curvature(mesh)

    # ── Feature 1: Gaussian curvature (angle defect) ─────────────────────
    features[:, 1] = _gaussian_curvature(mesh)

    # ── Feature 2: Dihedral angle ─────────────────────────────────────────
    features[:, 2] = _dihedral_angle(mesh)

    # ── Feature 3: Valence ────────────────────────────────────────────────
    features[:, 3] = _valence(mesh)

    # ── Feature 4: Boundary flag ──────────────────────────────────────────
    features[:, 4] = _boundary_flag(mesh)

    # ── Feature 5: UV stretch ─────────────────────────────────────────────
    features[:, 5] = _uv_stretch(mesh)

    return features


def _percentile_norm(arr: np.ndarray, pct: float = 95.0) -> np.ndarray:
    """Normalize array by its Nth percentile, clipped to [0, 1]."""
    arr = np.abs(np.asarray(arr, dtype=np.float64))
    ceil = np.percentile(arr, pct) if len(arr) > 0 else 0.0
    if ceil <= 1e-9:
        return np.zeros_like(arr, dtype=np.float32)
    return np.clip(arr / ceil, 0.0, 1.0).astype(np.float32)


def _mean_curvature(mesh: "trimesh.Trimesh") -> np.ndarray:
    """Discrete mean curvature via trimesh, percentile-normalized."""
    try:
        from trimesh.curvature import discrete_mean_curvature_measure
        bbox_max = float(mesh.bounding_box.extents.max())
        radius = max(bbox_max * 0.02, 1e-6)
        raw = discrete_mean_curvature_measure(mesh, mesh.vertices, radius=radius)
        return _percentile_norm(raw)
    except Exception:
        return np.full(len(mesh.vertices), 0.5, dtype=np.float32)


def _gaussian_curvature(mesh: "trimesh.Trimesh") -> np.ndarray:
    """Discrete Gaussian curvature via angle defect, percentile-normalized."""
    try:
        from trimesh.curvature import discrete_gaussian_curvature_measure
        bbox_max = float(mesh.bounding_box.extents.max())
        radius = max(bbox_max * 0.02, 1e-6)
        raw = discrete_gaussian_curvature_measure(mesh, mesh.vertices, radius=radius)
        return _percentile_norm(raw)
    except Exception:
        # Fallback: angle defect method
        try:
            n_verts = len(mesh.vertices)
            angle_sum = np.zeros(n_verts, dtype=np.float64)
            verts = mesh.vertices
            for face in mesh.faces:
                for i in range(3):
                    v0 = face[i]
                    v1 = face[(i + 1) % 3]
                    v2 = face[(i + 2) % 3]
                    e1 = verts[v1] - verts[v0]
                    e2 = verts[v2] - verts[v0]
                    cos_a = np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2) + 1e-12)
                    angle_sum[v0] += np.arccos(np.clip(cos_a, -1.0, 1.0))
            defect = 2.0 * np.pi - angle_sum
            return _percentile_norm(defect)
        except Exception:
            return np.full(len(mesh.vertices), 0.5, dtype=np.float32)


def _dihedral_angle(mesh: "trimesh.Trimesh") -> np.ndarray:
    """Mean dihedral angle per vertex from adjacent face pairs, normalized to [0,1]."""
    n_verts = len(mesh.vertices)
    angle_sum = np.zeros(n_verts, dtype=np.float64)
    angle_count = np.zeros(n_verts, dtype=np.float64)

    try:
        face_normals = mesh.face_normals
        face_adj = mesh.face_adjacency
        face_adj_edges = mesh.face_adjacency_edges

        for idx in range(len(face_adj)):
            f1, f2 = face_adj[idx]
            n1 = face_normals[f1]
            n2 = face_normals[f2]
            dot = np.clip(np.dot(n1, n2), -1.0, 1.0)
            dihedral = np.arccos(dot)  # 0 = flat, π = sharp fold

            v1, v2 = face_adj_edges[idx]
            angle_sum[v1] += dihedral
            angle_count[v1] += 1
            angle_sum[v2] += dihedral
            angle_count[v2] += 1

        mask = angle_count > 0
        result = np.zeros(n_verts, dtype=np.float32)
        result[mask] = (angle_sum[mask] / angle_count[mask]).astype(np.float32)
        # Normalize: 0 = perfectly flat, 1 = sharp fold (π radians)
        result = result / np.pi
        return np.clip(result, 0.0, 1.0).astype(np.float32)

    except Exception:
        return np.full(n_verts, 0.0, dtype=np.float32)


def _valence(mesh: "trimesh.Trimesh") -> np.ndarray:
    """Vertex degree (number of connected edges), normalized by max."""
    n_verts = len(mesh.vertices)
    degree = np.zeros(n_verts, dtype=np.float64)
    for e in mesh.edges_unique:
        degree[e[0]] += 1
        degree[e[1]] += 1
    max_deg = degree.max() if degree.max() > 0 else 1.0
    return (degree / max_deg).astype(np.float32)


def _boundary_flag(mesh: "trimesh.Trimesh") -> np.ndarray:
    """1.0 for vertices on boundary edges (edges shared by exactly 1 face)."""
    n_verts = len(mesh.vertices)
    flags = np.zeros(n_verts, dtype=np.float32)
    try:
        edge_refs: dict[tuple[int, int], int] = {}
        for face in mesh.faces:
            for a, b in [(face[0], face[1]), (face[1], face[2]), (face[2], face[0])]:
                key = (min(a, b), max(a, b))
                edge_refs[key] = edge_refs.get(key, 0) + 1
        for (a, b), count in edge_refs.items():
            if count == 1:
                flags[a] = 1.0
                flags[b] = 1.0
    except Exception:
        pass
    return flags


def _uv_stretch(mesh: "trimesh.Trimesh") -> np.ndarray:
    """Per-vertex UV stretch ratio if UVs present, else 0."""
    n_verts = len(mesh.vertices)
    try:
        from ..importance.uv_density import compute_uv_density_importance, has_uvs
        if has_uvs(mesh):
            raw = compute_uv_density_importance(mesh)
            return _percentile_norm(raw)
    except Exception:
        pass
    return np.zeros(n_verts, dtype=np.float32)
