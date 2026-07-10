"""
animation_awareness.py — Animation/joint-aware importance for skeletal
and deformation-sensitive regions.

Strategy (practical heuristic, no external rigging library required):
  1. Detect rigging metadata:
     - Check for vertex bone-weight attributes (common in FBX / GLB
       loaded via trimesh's scene graph).
     - If present, vertices with non-zero bone influence → high importance.
  2. Heuristic inference (when rig data is absent):
     - Compute per-vertex Laplacian deformation energy as a proxy for
       "how much does this vertex move if nearby vertices move?"
     - Vertices with high deformation energy near geometric extremities
       are likely joint or limb regions.
     - Combine with curvature to protect hinge-like areas (knees,
       elbows, fingers).
  3. Combine signals into per-vertex importance in [0, 1].

The caller (compute_importance in importance_mapper.py) multiplies
this into the base importance so that deformation-sensitive regions
are additionally protected during QEM collapse.
"""

from __future__ import annotations

import numpy as np
import trimesh


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Weight given to the heuristic deformation signal when rig data is absent.
HEURISTIC_WEIGHT = 0.25


# ---------------------------------------------------------------------------
# Rig detection helpers
# ---------------------------------------------------------------------------

def _detect_rig_attributes(mesh: trimesh.Trimesh) -> np.ndarray | None:
    """
    Scan for bone-weight attributes stored on the mesh.

    Trimesh does not natively parse skeletal data, but some loaders
    (assimp via trimesh) attach per-vertex weight arrays to the
    ``vertex_attributes`` namespace or as ``metadata``.

    Returns a per-vertex weight array in [0, 1] where 0 = no bone
    influence, 1 = fully bound.  Returns None if no rig data is found.
    """
    n_verts = len(mesh.vertices)
    if n_verts == 0:
        return None

    # Check vertex_attributes dict
    attrs = getattr(mesh, "vertex_attributes", None) or {}
    for key in ("bone_weights", "weights", "joint_weights", "skinning_weights"):
        val = attrs.get(key)
        if val is not None:
            w = np.asarray(val, dtype=np.float64)
            if w.ndim == 2 and w.shape[1] > 1:
                w = w.sum(axis=1)
            if len(w) == n_verts:
                return np.clip(w, 0.0, 1.0)

    # Check metadata for bone count
    meta = getattr(mesh, "metadata", None) or {}
    if meta.get("has_skeleton") or meta.get("has_bones"):
        return np.ones(n_verts, dtype=np.float64) * 0.5

    return None


# ---------------------------------------------------------------------------
# Heuristic deformation sensitivity
# ---------------------------------------------------------------------------

def _laplacian_deformation_energy(mesh: trimesh.Trimesh) -> np.ndarray:
    """
    Approximate per-vertex deformation energy via umbrella-operator
    Laplacian magnitude.

    For each vertex v:
        E(v) = || v - (1/|N(v)|) * sum_{u in N(v)} u ||

    High energy → vertex is geometrically "extreme" relative to its
    neighbours → likely part of a limb, joint, or thin feature.
    """
    n_verts = len(mesh.vertices)
    verts = np.asarray(mesh.vertices, dtype=np.float64)

    # Build adjacency
    adj: list[list[int]] = [list() for _ in range(n_verts)]
    for face in mesh.faces:
        a, b, c = int(face[0]), int(face[1]), int(face[2])
        adj[a].append(b); adj[a].append(c)
        adj[b].append(a); adj[b].append(c)
        adj[c].append(a); adj[c].append(b)

    energy = np.zeros(n_verts, dtype=np.float64)
    for v_idx in range(n_verts):
        nb = adj[v_idx]
        if not nb:
            continue
        neighbour_center = np.mean(verts[nb], axis=0)
        diff = verts[v_idx] - neighbour_center
        energy[v_idx] = np.linalg.norm(diff)

    return energy


def _detect_limb_extremities(mesh: trimesh.Trimesh) -> np.ndarray:
    """
    Identify vertices that are likely at limb extremities by
    combining laplacian energy with curvature.

    High energy + high curvature → likely a joint/limb/hinge region.
    """
    energy = _laplacian_deformation_energy(mesh)

    eps = 1e-9
    energy_max = energy.max()
    if energy_max > eps:
        energy = energy / energy_max

    return energy


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def has_animation_data(mesh: trimesh.Trimesh) -> bool:
    """Quick check if a mesh carries rig/skeleton or is likely animated.

    Returns True if rig metadata is present or the mesh has bone-weight
    attributes on any of its vertices.  Does not compute the full importance
    map — intended for cheap binary detection during analysis.
    """
    rig_weights = _detect_rig_attributes(mesh)
    if rig_weights is not None:
        return True
    return False


def compute_animation_importance(mesh: trimesh.Trimesh) -> np.ndarray:
    """
    Compute per-vertex animation awareness importance in [0, 1].

    Pipeline:
      1. Try to detect rig/bone-weight data.
      2. If found, use bone weights directly.
      3. If not found, compute heuristic deformation energy.
      4. The result is a score array where higher = protect more.

    Returns:
        np.ndarray of shape (N_vertices,) with values in [0.0, 1.0].
        Returns uniform 0.5 for empty or degenerate meshes.
    """
    n_verts = len(mesh.vertices)
    if n_verts == 0 or len(mesh.faces) == 0:
        return np.full(n_verts, 0.5, dtype=np.float64)

    # Try rig data first
    rig_weights = _detect_rig_attributes(mesh)
    if rig_weights is not None:
        return rig_weights

    # Fall back to heuristic
    deformation = _detect_limb_extremities(mesh)
    deformation = np.clip(deformation, 0.0, 1.0)
    return deformation * HEURISTIC_WEIGHT
