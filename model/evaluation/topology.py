"""evaluation/topology.py — topology integrity metrics (§56).

Reports the 2026 paper's "percentage of wrong adjacency" plus the defect
deltas Crunch3D additionally cares about (non-manifold edges created, boundary
and component drift, collapses the validator refused).

Wrong adjacency is well defined only against a vertex correspondence.  We build
one by snapping each simplified vertex to its nearest original vertex, then
count simplified edges whose mapped endpoints were **more than two hops apart**
in the original graph.  Two hops is the tolerance a legitimate single collapse
introduces; anything beyond that is adjacency the simplifier invented.
"""

from __future__ import annotations

import numpy as np

from ..geometry.validation import validate


def _unique_edges(faces: np.ndarray, n_verts: int) -> np.ndarray:
    if len(faces) == 0:
        return np.zeros((0, 2), dtype=np.int64)
    src = faces.ravel()
    dst = faces[:, [1, 2, 0]].ravel()
    return np.unique(
        np.column_stack((np.minimum(src, dst), np.maximum(src, dst))), axis=0
    )


def wrong_adjacency(
    original_verts: np.ndarray,
    original_faces: np.ndarray,
    simplified_verts: np.ndarray,
    simplified_faces: np.ndarray,
) -> float | None:
    """Fraction of simplified edges whose endpoints were >2 hops apart."""
    from scipy.sparse import coo_matrix
    from scipy.spatial import cKDTree

    edges = _unique_edges(np.asarray(simplified_faces, dtype=np.int64), len(simplified_verts))
    if len(edges) == 0 or len(original_faces) == 0:
        return None

    mapping = cKDTree(original_verts).query(simplified_verts, workers=-1)[1]
    n = len(original_verts)

    original_edges = _unique_edges(np.asarray(original_faces, dtype=np.int64), n)
    rows = np.concatenate([original_edges[:, 0], original_edges[:, 1]])
    cols = np.concatenate([original_edges[:, 1], original_edges[:, 0]])
    adjacency = coo_matrix(
        (np.ones(len(rows), dtype=np.int8), (rows, cols)), shape=(n, n)
    ).tocsr()
    reachable = (adjacency + adjacency @ adjacency).tocsr()

    a, b = mapping[edges[:, 0]], mapping[edges[:, 1]]
    same = a == b
    linked = np.asarray(reachable[a, b]).ravel() > 0
    wrong = int(np.sum(~(same | linked)))
    return round(100.0 * wrong / len(edges), 5)


def topology_metrics(
    original_verts: np.ndarray,
    original_faces: np.ndarray,
    simplified_verts: np.ndarray,
    simplified_faces: np.ndarray,
    rejected: dict | None = None,
) -> dict:
    before = validate(original_verts, original_faces)
    after = validate(simplified_verts, simplified_faces)

    created = max(after.non_manifold_edges - before.non_manifold_edges, 0)
    return {
        "wrong_adjacency_percent": wrong_adjacency(
            np.asarray(original_verts, dtype=np.float64),
            np.asarray(original_faces, dtype=np.int64),
            np.asarray(simplified_verts, dtype=np.float64),
            np.asarray(simplified_faces, dtype=np.int64),
        ),
        "non_manifold_edges_before": before.non_manifold_edges,
        "non_manifold_edges_after": after.non_manifold_edges,
        "topology_violations_created": created,
        "boundary_edges_before": before.boundary_edges,
        "boundary_edges_after": after.boundary_edges,
        "components_before": before.components,
        "components_after": after.components,
        "component_delta": after.components - before.components,
        "degenerate_faces_after": after.degenerate_faces,
        "invalid_collapses_rejected": int((rejected or {}).get("total", 0)),
        "rejection_reasons": (rejected or {}).get("by_reason", {}),
    }
