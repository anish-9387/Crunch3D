"""
texture/reallocation.py — Persistence-gated texture reallocation.

Implements §IV-C, Eq. 3:
    texel_density(f) ∝ ŷ^γ · 𝟙[pers(f) > τ_topo]

After decimation, this module redistributes texture atlas space
so that topologically significant, high-importance faces receive
more texels, and low-importance faces are compressed.

Requires: numpy only (no external deps beyond the base project).
"""

from __future__ import annotations

import logging

import numpy as np

from ..core.config import GAMMA, TAU_TOPO

logger = logging.getLogger(__name__)


def compute_face_persistence(
    faces: np.ndarray,
    edge_persistence: dict[tuple[int, int], float],
) -> np.ndarray:
    """Compute per-face persistence as the max edge persistence.

    Parameters
    ----------
    faces : (F, 3) int array
        Triangle face indices.
    edge_persistence : dict[(v_i, v_j), float]
        Per-edge persistence values.

    Returns
    -------
    face_pers : (F,) float array
        Max persistence of any edge in each face.
    """
    face_pers = np.zeros(len(faces), dtype=np.float64)
    for f_idx, face in enumerate(faces):
        a, b, c = int(face[0]), int(face[1]), int(face[2])
        edges = [
            tuple(sorted((a, b))),
            tuple(sorted((b, c))),
            tuple(sorted((a, c))),
        ]
        max_pers = max(edge_persistence.get(e, 0.0) for e in edges)
        face_pers[f_idx] = max_pers
    return face_pers


def reallocate_texel_density(
    faces: np.ndarray,
    importance: np.ndarray,
    edge_persistence: dict[tuple[int, int], float],
    gamma: float | None = None,
    tau_topo: float | None = None,
) -> np.ndarray:
    """Compute target texel density per face.

    Implements Eq. 3:
        texel_density(f) ∝ ŷ^γ · 𝟙[pers(f) > τ_topo]

    Parameters
    ----------
    faces : (F, 3) int array
        Triangle face indices.
    importance : (F,) float array
        Per-face importance score (aggregated from per-vertex).
    edge_persistence : dict[(v_i, v_j), float]
        Per-edge persistence values.
    gamma : float, optional
        Texel density exponent.  Defaults to GAMMA from config.
    tau_topo : float, optional
        Persistence threshold.  Defaults to TAU_TOPO from config.

    Returns
    -------
    density : (F,) float array
        Target texel density per face, normalized to sum to 1.
    """
    if gamma is None:
        gamma = GAMMA
    if tau_topo is None:
        tau_topo = TAU_TOPO

    face_pers = compute_face_persistence(faces, edge_persistence)

    # ŷ^γ
    imp_powered = np.power(np.clip(importance, 1e-8, 1.0), gamma)

    # 𝟙[pers(f) > τ_topo]  — indicator for topologically significant faces
    topo_mask = (face_pers > tau_topo).astype(np.float64)

    # Combined density
    density = imp_powered * topo_mask

    # Normalize
    total = density.sum()
    if total > 1e-12:
        density /= total
    else:
        # Uniform fallback
        density = np.ones(len(faces), dtype=np.float64) / max(len(faces), 1)

    logger.info(
        "Texture reallocation: %d/%d faces have non-zero density (γ=%.2f, τ=%.4f)",
        int(np.sum(density > 1e-12)), len(faces), gamma, tau_topo,
    )

    return density
