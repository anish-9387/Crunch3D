"""
topology/filtration.py — Build a simplicial filtration from curvature data.

Constructs a filtered simplicial complex from a mesh, where the filtration
values are derived from the per-vertex curvature field.  This is the input
to persistent homology computation.

Reference: §IV-A of the paper.
"""

from __future__ import annotations

import numpy as np


def build_lower_star_filtration(
    vertices: np.ndarray,
    faces: np.ndarray,
    curvature: np.ndarray,
) -> list[tuple[list[int], float]]:
    """Build a lower-star filtration from vertex curvature values.

    Parameters
    ----------
    vertices : (V, 3) array
        Vertex positions (used only for dimension).
    faces : (F, 3) int array
        Triangle face indices.
    curvature : (V,) array
        Per-vertex curvature values.  Higher curvature → later entry in
        filtration → more topologically "important".

    Returns
    -------
    simplices : list of (simplex, filtration_value)
        Each simplex is a list of vertex indices.
        Ordered for input to gudhi.SimplexTree.
    """
    simplices: list[tuple[list[int], float]] = []

    # 0-simplices (vertices)
    for v_idx in range(len(vertices)):
        simplices.append(([v_idx], float(curvature[v_idx])))

    # Vectorized 1-simplices (edges) and 2-simplices (faces)
    faces_c = curvature[faces]  # shape (F, 3)
    
    # 2-simplices (faces): max curvature among its 3 vertices
    face_max = np.max(faces_c, axis=1)
    
    # 1-simplices (edges)
    # E0: edges between faces[:, 0] and faces[:, 1]
    e0_max = np.max(faces_c[:, [0, 1]], axis=1)
    # E1: edges between faces[:, 1] and faces[:, 2]
    e1_max = np.max(faces_c[:, [1, 2]], axis=1)
    # E2: edges between faces[:, 0] and faces[:, 2]
    e2_max = np.max(faces_c[:, [0, 2]], axis=1)
    
    for i, face in enumerate(faces):
        a, b, c = int(face[0]), int(face[1]), int(face[2])
        simplices.append(([a, b], float(e0_max[i])))
        simplices.append(([b, c], float(e1_max[i])))
        simplices.append(([a, c], float(e2_max[i])))
        simplices.append(([a, b, c], float(face_max[i])))

    return simplices
