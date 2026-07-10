"""
topology/persistence.py — Compute persistent homology for edge admissibility.

Uses gudhi (import-guarded) to compute persistence diagrams from the
lower-star filtration built by filtration.py.

Reference: §IV-A, Eq. 1:
    Admissible(σ) ⟺ pers(σ) ≤ τ_topo

If gudhi is not installed, functions raise ImportError with a helpful message.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import trimesh

from .filtration import build_lower_star_filtration

logger = logging.getLogger(__name__)


def _require_gudhi():
    """Import gudhi or raise a clear error."""
    try:
        import gudhi
        return gudhi
    except ImportError as e:
        raise ImportError(
            "The topology module requires 'gudhi'. "
            "Install it with: pip install gudhi"
        ) from e


def compute_edge_persistence(
    mesh: "trimesh.Trimesh",
    curvature: np.ndarray,
) -> dict[tuple[int, int], float]:
    """Compute persistence values for each edge in the mesh.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Input mesh.
    curvature : (V,) array
        Per-vertex curvature values.

    Returns
    -------
    persistence_map : dict[(v_i, v_j), float]
        Maps each edge (as sorted tuple of vertex indices) to its
        persistence value.  Edges not appearing in any persistence pair
        are assigned persistence = 0.0 (always admissible).
    """
    gudhi = _require_gudhi()

    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)

    # Build filtration
    simplices = build_lower_star_filtration(vertices, faces, curvature)

    # Insert into SimplexTree
    st = gudhi.SimplexTree()
    for simplex, filt_val in simplices:
        st.insert(simplex, filtration=filt_val)

    st.make_filtration_non_decreasing()
    st.persistence()

    # Extract persistence pairs
    persistence_map: dict[tuple[int, int], float] = {}

    # Initialize all edges with 0 persistence
    for face in faces:
        a, b, c = int(face[0]), int(face[1]), int(face[2])
        for u, v in [(a, b), (b, c), (a, c)]:
            edge = tuple(sorted((u, v)))
            persistence_map.setdefault(edge, 0.0)

    # For each persistence pair, assign persistence = death - birth
    pairs = st.persistence_pairs()
    for birth_simplex, death_simplex in pairs:
        if len(birth_simplex) == 2:
            # This is an edge giving birth to a 1-cycle
            edge = tuple(sorted(birth_simplex))
            birth_val = st.filtration(birth_simplex)
            death_val = st.filtration(death_simplex) if death_simplex else float("inf")
            pers = death_val - birth_val
            persistence_map[edge] = max(persistence_map.get(edge, 0.0), pers)

    logger.info(
        "Computed persistence for %d edges (max=%.4f, mean=%.4f)",
        len(persistence_map),
        max(persistence_map.values()) if persistence_map else 0.0,
        np.mean(list(persistence_map.values())) if persistence_map else 0.0,
    )

    return persistence_map
