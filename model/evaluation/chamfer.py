"""evaluation/chamfer.py — surface deviation between two meshes (§54).

One sampling protocol, fixed seed and fixed sample count, shared by every
method so the comparison is apples-to-apples.  All distances are normalised by
the bounding-box diagonal of the *reference* mesh and additionally reported as
percentages, matching crunch3d-v2 §"All geometric deviations normalized by
D_bbox".
"""

from __future__ import annotations

import numpy as np

SAMPLE_COUNT = 50_000
SAMPLE_SEED = 42

_EPS = 1e-12


def sample_surface(
    verts: np.ndarray,
    faces: np.ndarray,
    count: int = SAMPLE_COUNT,
    seed: int = SAMPLE_SEED,
) -> tuple[np.ndarray, np.ndarray]:
    """Area-weighted uniform surface sampling; returns ``(points, normals)``."""
    verts = np.asarray(verts, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    if len(faces) == 0:
        return np.zeros((0, 3)), np.zeros((0, 3))

    p0, p1, p2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    cross = np.cross(p1 - p0, p2 - p0)
    length = np.linalg.norm(cross, axis=1)
    total = float(length.sum())
    if total <= _EPS:
        return p0.copy(), np.zeros_like(p0)

    rng = np.random.default_rng(seed)
    index = rng.choice(len(faces), size=count, p=length / total)

    a = rng.random((count, 1))
    b = rng.random((count, 1))
    outside = (a + b) > 1.0
    a[outside] = 1.0 - a[outside]
    b[outside] = 1.0 - b[outside]

    base = p0[index]
    points = base + a * (p1[index] - base) + b * (p2[index] - base)
    normals = cross[index] / (length[index, None] + _EPS)
    return points, normals


def bbox_diagonal(verts: np.ndarray) -> float:
    verts = np.asarray(verts, dtype=np.float64)
    if len(verts) == 0:
        return 1.0
    diagonal = float(np.linalg.norm(verts.max(axis=0) - verts.min(axis=0)))
    return diagonal if diagonal > _EPS else 1.0


def chamfer_distance(
    reference_points: np.ndarray,
    candidate_points: np.ndarray,
    diagonal: float,
) -> dict:
    """Bidirectional nearest-neighbour surface deviation, diagonal-normalised."""
    from scipy.spatial import cKDTree

    if len(reference_points) == 0 or len(candidate_points) == 0:
        return {"chamfer": None, "chamfer_p95": None, "chamfer_max": None}

    forward = cKDTree(candidate_points).query(reference_points, workers=-1)[0]
    backward = cKDTree(reference_points).query(candidate_points, workers=-1)[0]

    mean = 0.5 * (float(forward.mean()) + float(backward.mean()))
    p95 = max(float(np.percentile(forward, 95)), float(np.percentile(backward, 95)))
    worst = max(float(forward.max()), float(backward.max()))

    return {
        "chamfer": round(mean / diagonal, 8),
        "chamfer_p95": round(p95 / diagonal, 8),
        "chamfer_max": round(worst / diagonal, 8),
        "chamfer_percent": round(100.0 * mean / diagonal, 5),
        "chamfer_p95_percent": round(100.0 * p95 / diagonal, 5),
    }
