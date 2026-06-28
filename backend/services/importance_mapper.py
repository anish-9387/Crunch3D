"""
importance_mapper.py — Crunch3D / OptiMesh v1.1

Computes a per-vertex importance score (0.0 → 1.0) for a Trimesh.

Higher score = more geometrically important = protected from aggressive QEM.

Pipeline:
    Mesh
      ↓
    Compute Mean Curvature         (adaptive radius, scale-invariant)
      ↓
    Compute Normal Variation       (per-vertex angular deviation)
      ↓
    Compute Boundary Importance    (conservative — noisy meshes friendly)
      ↓
    Compute Local Feature Density  (vertex valence proxy)
      ↓
    Weighted Combination
      ↓
    Percentile Normalization       (robust to outlier spikes)
      ↓
    Laplacian Smoothing            (remove noise from raw curvature)
      ↓
    Final importance map  [0.0, 1.0]

Weights (tunable):
    curvature        0.45
    normal_variation 0.20
    boundary         0.20
    feature_density  0.15
"""

from __future__ import annotations

import numpy as np
import trimesh
import trimesh.graph


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Fraction of bounding-box diagonal used as curvature sampling radius
ADAPTIVE_RADIUS_FRACTION = 0.02

# Percentile used for normalization (guards against outlier spikes)
NORMALIZATION_PERCENTILE = 95

# Laplacian smoothing iterations
SMOOTH_ITERATIONS = 3

# Combination weights — must sum to 1.0
W_CURVATURE        = 0.45
W_NORMAL_VARIATION = 0.20
W_BOUNDARY         = 0.20
W_FEATURE_DENSITY  = 0.15

# Boundary bonus (kept conservative — scanned meshes have noisy boundaries)
BOUNDARY_BONUS = 0.3


# ---------------------------------------------------------------------------
# Individual cues
# ---------------------------------------------------------------------------

def _adaptive_radius(mesh: trimesh.Trimesh) -> float:
    """
    Scale-invariant sampling radius = 2% of the mesh's longest bounding axis.
    Works for a 1m character and a 100m building equally.
    """
    bbox_max = float(mesh.bounding_box.extents.max())
    return max(bbox_max * ADAPTIVE_RADIUS_FRACTION, 1e-6)


def _mean_curvature(mesh: trimesh.Trimesh, radius: float) -> np.ndarray:
    """
    Discrete mean curvature via trimesh's built-in sphere measure.
    Returns per-vertex absolute curvature, un-normalized.
    """
    try:
        from trimesh.curvature import discrete_mean_curvature_measure
        curvature = discrete_mean_curvature_measure(mesh, mesh.vertices, radius=radius)
        return np.abs(np.asarray(curvature, dtype=np.float64))
    except Exception:
        # Fallback: approximate via vertex normal deviation from face normals
        return _normal_variation(mesh)


def _normal_variation(mesh: trimesh.Trimesh) -> np.ndarray:
    """
    Per-vertex normal variation = average angular difference between
    the vertex normal and the normals of its adjacent faces.

    High variation → sharp feature / crease → high importance.
    """
    n_verts = len(mesh.vertices)
    variation = np.zeros(n_verts, dtype=np.float64)
    count     = np.zeros(n_verts, dtype=np.float64)

    vertex_normals = mesh.vertex_normals          # (V, 3)
    face_normals   = mesh.face_normals            # (F, 3)

    for face_idx, face in enumerate(mesh.faces):
        fn = face_normals[face_idx]
        for v_idx in face:
            vn = vertex_normals[v_idx]
            dot = float(np.clip(np.dot(fn, vn), -1.0, 1.0))
            variation[v_idx] += np.arccos(abs(dot))   # 0 → π/2
            count[v_idx]     += 1

    mask = count > 0
    variation[mask] /= count[mask]
    # Normalize to [0, 1] — max possible angle is π/2
    variation /= (np.pi / 2)
    return variation


def _boundary_importance(mesh: trimesh.Trimesh) -> np.ndarray:
    """
    Vertices on boundary edges get a bonus.
    Conservative value (0.3) avoids over-protecting noisy scan boundaries.
    """
    importance = np.zeros(len(mesh.vertices), dtype=np.float64)
    try:
        # unique_edges has shape (E, 2); edges used by exactly one face are boundary
        edge_counts = np.zeros(len(mesh.edges_unique), dtype=np.int32)
        for face in mesh.faces:
            edges_in_face = [
                tuple(sorted([face[0], face[1]])),
                tuple(sorted([face[1], face[2]])),
                tuple(sorted([face[2], face[0]])),
            ]
            for e in edges_in_face:
                # find index in unique edges — use trimesh's mapping
                pass

        # Simpler and faster: use trimesh's is_watertight negation
        # boundary verts = vertices on edges that appear only once
        edge_face_count = np.zeros(len(mesh.edges_unique), dtype=np.int32)
        for i in range(len(mesh.edges_unique)):
            edge_face_count[i] = 1  # placeholder

        # Use trimesh.graph for correct boundary detection
        adjacency = trimesh.graph.face_adjacency(mesh.faces)
        all_edge_pairs = set(map(tuple, np.sort(mesh.edges_unique, axis=1)))
        adj_edges = set(
            tuple(sorted(pair))
            for pair in mesh.edges_unique[adjacency.flatten()] if False
        )

        # Correct approach: edges referenced by only 1 face
        edge_refs = {}
        for face in mesh.faces:
            for a, b in [(face[0], face[1]), (face[1], face[2]), (face[2], face[0])]:
                key = (min(a, b), max(a, b))
                edge_refs[key] = edge_refs.get(key, 0) + 1

        boundary_verts = set()
        for (a, b), count in edge_refs.items():
            if count == 1:
                boundary_verts.add(a)
                boundary_verts.add(b)

        for v in boundary_verts:
            importance[v] = BOUNDARY_BONUS

    except Exception:
        pass  # Non-critical — return zeros if boundary detection fails

    return importance


def _feature_density(mesh: trimesh.Trimesh) -> np.ndarray:
    """
    Local feature density proxy = vertex valence (number of connected faces).

    High valence → local geometric complexity → higher importance.
    Normalized to [0, 1] via percentile.
    """
    valence = np.zeros(len(mesh.vertices), dtype=np.float64)
    for face in mesh.faces:
        valence[face[0]] += 1
        valence[face[1]] += 1
        valence[face[2]] += 1
    return valence


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def _percentile_normalize(arr: np.ndarray, percentile: float = NORMALIZATION_PERCENTILE) -> np.ndarray:
    """
    Normalize using the Nth percentile as the ceiling.

    Why not max?  One outlier spike can compress everything else to near-zero.
    Percentile normalization is far more stable for real-world meshes.
    """
    arr = np.asarray(arr, dtype=np.float64)
    ceil = np.percentile(arr, percentile)
    if ceil <= 1e-9:
        return np.zeros_like(arr)
    return np.clip(arr / ceil, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Laplacian smoothing
# ---------------------------------------------------------------------------

def _build_adjacency(mesh: trimesh.Trimesh) -> list[list[int]]:
    """Build a vertex → [neighbour vertex indices] adjacency list."""
    n = len(mesh.vertices)
    adj: list[set[int]] = [set() for _ in range(n)]
    for face in mesh.faces:
        a, b, c = int(face[0]), int(face[1]), int(face[2])
        adj[a].update([b, c])
        adj[b].update([a, c])
        adj[c].update([a, b])
    return [list(s) for s in adj]


def _laplacian_smooth(
    scores: np.ndarray,
    adjacency: list[list[int]],
    iterations: int = SMOOTH_ITERATIONS,
    alpha: float = 0.5,
) -> np.ndarray:
    """
    Iterative Laplacian smoothing on the importance map.

    Each vertex blends its score with the mean of its neighbours:
        score_new = (1 - alpha) * score + alpha * mean(neighbours)

    alpha=0.5 gives equal weight to self and neighbourhood.
    More iterations → smoother map.

    This removes the noisy spike pattern raw curvature produces.
    """
    result = scores.copy()
    for _ in range(iterations):
        new_result = result.copy()
        for v_idx, neighbours in enumerate(adjacency):
            if not neighbours:
                continue
            neighbour_mean = float(np.mean(result[neighbours]))
            new_result[v_idx] = (1.0 - alpha) * result[v_idx] + alpha * neighbour_mean
        result = new_result
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_importance(mesh: trimesh.Trimesh) -> np.ndarray:
    """
    Compute a per-vertex importance score for a single Trimesh component.

    Returns:
        np.ndarray of shape (N_vertices,) with values in [0.0, 1.0].
        Higher = more important = protected from QEM collapse.

    Safe to call on any valid Trimesh — all sub-steps handle failures
    gracefully and fall back to uniform importance (0.5) if needed.
    """
    n_verts = len(mesh.vertices)

    if n_verts == 0 or len(mesh.faces) == 0:
        return np.full(n_verts, 0.5, dtype=np.float64)

    try:
        radius = _adaptive_radius(mesh)

        # ── Compute each cue ──────────────────────────────────────────────
        curvature        = _mean_curvature(mesh, radius)
        normal_var       = _normal_variation(mesh)
        boundary         = _boundary_importance(mesh)
        feature_dens     = _feature_density(mesh)

        # ── Percentile-normalize each cue independently ───────────────────
        curvature    = _percentile_normalize(curvature)
        normal_var   = _percentile_normalize(normal_var)
        boundary     = _percentile_normalize(boundary)
        feature_dens = _percentile_normalize(feature_dens)

        # ── Weighted combination ──────────────────────────────────────────
        importance = (
            W_CURVATURE        * curvature    +
            W_NORMAL_VARIATION * normal_var   +
            W_BOUNDARY         * boundary     +
            W_FEATURE_DENSITY  * feature_dens
        )

        # ── Laplacian smoothing — removes noisy spikes ────────────────────
        adjacency  = _build_adjacency(mesh)
        importance = _laplacian_smooth(importance, adjacency)

        # ── Final normalization to [0, 1] ─────────────────────────────────
        importance = _percentile_normalize(importance)

        return importance.astype(np.float64)

    except Exception:
        # Non-critical path — fall back to uniform importance
        # so decimation still works even if importance fails
        return np.full(n_verts, 0.5, dtype=np.float64)


def importance_to_heatmap_colors(importance: np.ndarray) -> np.ndarray:
    """
    Map importance scores to RGB colors for the Three.js heatmap overlay.

    Color ramp:  Blue → Green → Yellow → Orange → Red
    (5-stop perceptual ramp — humans read this intuitively)

    Args:
        importance: (N,) array of floats in [0.0, 1.0]

    Returns:
        (N, 3) array of RGB floats in [0.0, 1.0]
    """
    t = np.clip(importance, 0.0, 1.0)
    colors = np.zeros((len(t), 3), dtype=np.float64)

    # Stop 0 → 1:  Blue  (0,0,1)  →  Cyan  (0,1,1)   at t=[0.00, 0.25]
    # Stop 1 → 2:  Cyan  (0,1,1)  →  Green (0,1,0)   at t=[0.25, 0.50]
    # Stop 2 → 3:  Green (0,1,0)  →  Yellow(1,1,0)   at t=[0.50, 0.75]
    # Stop 3 → 4:  Yellow(1,1,0)  →  Red   (1,0,0)   at t=[0.75, 1.00]

    stops = np.array([
        [0.0,  0.0, 1.0],   # Blue
        [0.0,  1.0, 1.0],   # Cyan
        [0.0,  1.0, 0.0],   # Green
        [1.0,  1.0, 0.0],   # Yellow
        [1.0,  0.0, 0.0],   # Red
    ])
    stop_positions = np.array([0.0, 0.25, 0.50, 0.75, 1.0])

    for i in range(len(stop_positions) - 1):
        lo = stop_positions[i]
        hi = stop_positions[i + 1]
        mask = (t >= lo) & (t <= hi)
        if not np.any(mask):
            continue
        alpha = (t[mask] - lo) / (hi - lo)
        colors[mask] = (
            stops[i] * (1 - alpha[:, None]) +
            stops[i + 1] * alpha[:, None]
        )

    return colors