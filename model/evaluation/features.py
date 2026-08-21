"""evaluation/features.py — feature-preservation metrics (§59).

A cue counts as preserved when a simplified edge carrying the same flag exists
within ``tolerance × bbox_diagonal`` of the original edge's midpoint.  The
tolerance is a fixed fraction of the diagonal rather than a multiple of the
(method-dependent) mean edge length, so the number is comparable across methods
that all reached the same face count.

Cue definitions come from ``importance/edge_features.py`` so a metric and the
feature it measures can never drift apart.
"""

from __future__ import annotations

import numpy as np

FEATURE_TOLERANCE = 0.02
CURVATURE_PERCENTILE = 90.0

_FLAG_CUES = {
    "sharp_feature_recall": "sharp_edge_flag",
    "uv_seam_preservation": "uv_seam",
    "material_boundary_preservation": "material_boundary",
}


def _descriptor(mesh):
    from ..importance.edge_features import compute_edge_feature_importance

    return compute_edge_feature_importance(mesh)


def _midpoints(mesh, edges: np.ndarray) -> np.ndarray:
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    return 0.5 * (verts[edges[:, 0]] + verts[edges[:, 1]])


def _recall(
    reference_points: np.ndarray, candidate_points: np.ndarray, radius: float
) -> float | None:
    from scipy.spatial import cKDTree

    if len(reference_points) == 0:
        return None
    if len(candidate_points) == 0:
        return 0.0
    distances = cKDTree(candidate_points).query(reference_points, workers=-1)[0]
    return round(float(np.mean(distances <= radius)), 6)


def feature_metrics(
    original_mesh,
    simplified_mesh,
    tolerance: float = FEATURE_TOLERANCE,
) -> dict:
    """Recall of sharp edges, seams, silhouette and high-curvature regions."""
    verts = np.asarray(original_mesh.vertices, dtype=np.float64)
    diagonal = float(np.linalg.norm(verts.max(axis=0) - verts.min(axis=0))) if len(verts) else 1.0
    radius = max(tolerance * diagonal, 1e-9)

    before = _descriptor(original_mesh)
    after = _descriptor(simplified_mesh)
    if len(before.edges) == 0:
        return {"feature_recall": None}

    before_mid = _midpoints(original_mesh, before.edges)
    after_mid = _midpoints(simplified_mesh, after.edges) if len(after.edges) else np.zeros((0, 3))

    metrics: dict = {}
    for name, cue in _FLAG_CUES.items():
        if not before.present.get(cue, False):
            metrics[name] = None
            continue
        flagged = before.features[cue] > 0.5
        candidate = (
            after_mid[after.features[cue] > 0.5]
            if after.present.get(cue, False)
            else np.zeros((0, 3))
        )
        metrics[name] = _recall(before_mid[flagged], candidate, radius)

    metrics["silhouette_preservation"] = _percentile_recall(
        before.features.get("silhouette_score"), before_mid,
        after.features.get("silhouette_score"), after_mid, radius,
    )
    metrics["high_curvature_retention"] = _percentile_recall(
        before.features.get("mean_curvature"), before_mid,
        after.features.get("mean_curvature"), after_mid, radius,
    )

    scored = [v for v in metrics.values() if v is not None]
    metrics["feature_recall"] = round(float(np.mean(scored)), 6) if scored else None
    metrics["feature_tolerance"] = tolerance
    return metrics


def _percentile_recall(
    before_values: np.ndarray | None,
    before_points: np.ndarray,
    after_values: np.ndarray | None,
    after_points: np.ndarray,
    radius: float,
    percentile: float = CURVATURE_PERCENTILE,
) -> float | None:
    """Recall of the top-decile edges of a continuous cue."""
    if before_values is None or len(before_values) == 0:
        return None
    threshold = float(np.percentile(before_values, percentile))
    reference = before_points[before_values >= threshold]

    if after_values is None or len(after_values) == 0:
        return 0.0
    after_threshold = float(np.percentile(after_values, percentile))
    return _recall(reference, after_points[after_values >= after_threshold], radius)
