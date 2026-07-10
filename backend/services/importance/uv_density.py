"""
uv_density.py — UV-density-aware texture preservation importance.

Provides per-vertex importance based on UV stretch / texel density ratio.

Strategy (lightweight — no per-face UV stretch solver):
  For each face, compute:
    stretch = world_space_area / (uv_space_area + epsilon)

  Higher stretch means a small UV region maps to a large world-space area →
  texture detail is sparse → collapsing those vertices would lose texel
  fidelity disproportionately.  Such regions receive higher protection.

  The per-vertex score is the max stretch of all adjacent faces,
  normalised across the mesh.

Edge cases:
  - Mesh without UVs → returns uniform 0.5 (neutral — no UV signal).
  - Degenerate UV faces (zero-area in UV space) → clamped to a cap.
  - Multi-component meshes are handled by the caller (compute_importance
    is called per-component).
"""

from __future__ import annotations

import numpy as np
import trimesh


# If a face has zero UV area, we clamp to this ratio to avoid infinities.
_MAX_STRETCH_CAP = 10.0


def has_uvs(mesh: trimesh.Trimesh) -> bool:
    """Return True if the mesh carries UV coordinates."""
    visual = getattr(mesh, "visual", None)
    if visual is None:
        return False
    if hasattr(visual, "uv") and visual.uv is not None:
        return True
    if getattr(visual, "kind", None) == "texture":
        return True
    return False


def compute_uv_density_importance(mesh: trimesh.Trimesh) -> np.ndarray:
    """
    Compute per-vertex UV density importance in [0, 1].

    Returns a flat array of shape (N_vertices,).  Higher values indicate
    regions where texture fidelity is at greater risk if decimated.

    When the mesh has no UV data the array is filled with 0.5 (neutral).
    """
    n_verts = len(mesh.vertices)
    if n_verts == 0 or len(mesh.faces) == 0:
        return np.full(n_verts, 0.5, dtype=np.float64)

    if not has_uvs(mesh):
        return np.full(n_verts, 0.5, dtype=np.float64)

    uv = np.asarray(mesh.visual.uv, dtype=np.float64)        # (V, 2)
    verts = np.asarray(mesh.vertices, dtype=np.float64)      # (V, 3)
    faces = np.asarray(mesh.faces, dtype=np.int64)           # (F, 3)

    # Per-face world-space area (half of cross-product magnitude)
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    world_area = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)

    # Per-face UV-space area
    uv0 = uv[faces[:, 0]]
    uv1 = uv[faces[:, 1]]
    uv2 = uv[faces[:, 2]]
    uv_cross = (uv1[:, 0] - uv0[:, 0]) * (uv2[:, 1] - uv0[:, 1]) - \
               (uv1[:, 1] - uv0[:, 1]) * (uv2[:, 0] - uv0[:, 0])
    uv_area = 0.5 * np.abs(uv_cross)

    # Stretch ratio = world_area / uv_area  (clamped)
    eps = 1e-12
    stretch = np.where(uv_area > eps, world_area / uv_area, _MAX_STRETCH_CAP)
    stretch = np.clip(stretch, 1.0, _MAX_STRETCH_CAP)

    # Convert to per-vertex: each vertex gets the max stretch of its faces
    v_stretch = np.zeros(n_verts, dtype=np.float64)
    for f_idx in range(len(faces)):
        s = stretch[f_idx]
        for v in faces[f_idx]:
            if s > v_stretch[v]:
                v_stretch[v] = s

    # Normalise to [0, 1]
    stretch_max = v_stretch.max()
    if stretch_max > 1.0:
        v_stretch = (v_stretch - 1.0) / (stretch_max - 1.0)
    else:
        v_stretch = np.zeros_like(v_stretch)

    return v_stretch
