"""
topology/gate.py — Persistence-gated collapse admissibility.

Implements Eq. 1 from the paper:
    Admissible(σ) ⟺ pers(σ) ≤ τ_topo

An edge is admissible for collapse if and only if its persistence
value is below the threshold.  This prevents collapsing edges that
are topologically significant (tunnels, handles, boundaries).

Reference: §IV-A of the paper.
"""

from __future__ import annotations

import logging

from ..core.config import TAU_TOPO

logger = logging.getLogger(__name__)


def admissible_edges(
    persistence_map: dict[tuple[int, int], float],
    tau_topo: float | None = None,
) -> set[tuple[int, int]]:
    """Return the set of edges admissible for collapse.

    Parameters
    ----------
    persistence_map : dict[(v_i, v_j), float]
        Per-edge persistence values from compute_edge_persistence().
    tau_topo : float, optional
        Persistence threshold.  Defaults to TAU_TOPO from config.

    Returns
    -------
    admissible : set of (v_i, v_j) tuples
        Edges where pers(σ) ≤ τ_topo.
    """
    if tau_topo is None:
        tau_topo = TAU_TOPO

    admissible = {
        edge for edge, pers in persistence_map.items()
        if pers <= tau_topo
    }

    total = len(persistence_map)
    admitted = len(admissible)
    blocked = total - admitted

    logger.info(
        "Persistence gate (τ=%.4f): %d/%d edges admissible, %d blocked",
        tau_topo, admitted, total, blocked,
    )

    return admissible
