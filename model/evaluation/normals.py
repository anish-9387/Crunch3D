"""evaluation/normals.py — point-sampled normal error (§55).

Normals are compared at nearest-neighbour correspondences between the two
sampled point sets.  The dot product is kept *signed*: an inverted face is a
real defect and must not be forgiven by taking an absolute value.
"""

from __future__ import annotations

import numpy as np


def normal_error(
    reference_points: np.ndarray,
    reference_normals: np.ndarray,
    candidate_points: np.ndarray,
    candidate_normals: np.ndarray,
) -> dict:
    """Symmetric normal error over nearest-neighbour correspondences."""
    from scipy.spatial import cKDTree

    if len(reference_points) == 0 or len(candidate_points) == 0:
        return {"normal_error": None, "normal_angle_deg": None, "flipped_fraction": None}

    forward = cKDTree(candidate_points).query(reference_points, workers=-1)[1]
    backward = cKDTree(reference_points).query(candidate_points, workers=-1)[1]

    dots = np.concatenate([
        np.einsum("ij,ij->i", reference_normals, candidate_normals[forward]),
        np.einsum("ij,ij->i", candidate_normals, reference_normals[backward]),
    ])
    dots = np.clip(dots, -1.0, 1.0)

    return {
        "normal_error": round(float(np.mean(1.0 - dots)), 8),
        "normal_angle_deg": round(float(np.degrees(np.arccos(dots)).mean()), 5),
        "normal_angle_p95_deg": round(
            float(np.percentile(np.degrees(np.arccos(dots)), 95)), 5
        ),
        "flipped_fraction": round(float(np.mean(dots < 0.0)), 6),
    }
