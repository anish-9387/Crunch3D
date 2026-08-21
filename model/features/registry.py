"""features/registry.py — the §2 extraction entry point.

    features = extract(mesh, tiers=("A", "B"))
    features.vertex     (V, D_v)
    features.edge       (E, D_e)
    features.edges      (E, 2)
    features.metadata

Column order is derived from the registry, so it is identical for every mesh:
missing Tier B/C cues are emitted as zero columns with ``present=False`` rather
than being dropped.  That is what lets one trained model consume assets with and
without UVs, colours or rigs.

``exclude`` masks a cue by name for the §62 feature ablation without touching
model code; the column stays (so the input width is stable) and is zeroed.
"""

from __future__ import annotations

import logging

import numpy as np

from .base import FeatureExtractor, FeatureSet, MeshContext
from .edge import EDGE_EXTRACTORS, SAFETY_CUES
from .vertex import VERTEX_EXTRACTORS

logger = logging.getLogger(__name__)

DEFAULT_TIERS = ("A", "B")

FEATURE_REGISTRY: dict[str, FeatureExtractor] = {
    extractor.name: extractor
    for extractor in (*VERTEX_EXTRACTORS, *EDGE_EXTRACTORS)
}


def _selected(extractors: list[FeatureExtractor], tiers: tuple[str, ...]) -> list[FeatureExtractor]:
    return [e for e in extractors if e.tier in tiers]


def _assemble(
    extractors: list[FeatureExtractor],
    context: MeshContext,
    exclude: frozenset[str],
    present: dict[str, bool],
    rows: int,
) -> tuple[np.ndarray, list[str]]:
    blocks: list[np.ndarray] = []
    names: list[str] = []

    for extractor in extractors:
        names.extend(extractor.columns())
        if extractor.name in exclude:
            present[extractor.name] = False
            blocks.append(np.zeros((rows, extractor.output_dim), dtype=np.float32))
            continue
        try:
            available = extractor.available(context)
            block = extractor.compute(context) if available else extractor.zeros(context)
        except Exception as exc:
            logger.warning("Feature %s failed, emitting zeros: %s", extractor.name, exc)
            available, block = False, extractor.zeros(context)

        block = np.asarray(block, dtype=np.float32).reshape(rows, extractor.output_dim)
        present[extractor.name] = bool(available)
        blocks.append(np.nan_to_num(block, nan=0.0, posinf=0.0, neginf=0.0))

    matrix = (
        np.concatenate(blocks, axis=1)
        if blocks
        else np.zeros((rows, 0), dtype=np.float32)
    )
    return matrix, names


def extract(
    mesh,
    tiers: tuple[str, ...] = DEFAULT_TIERS,
    exclude: tuple[str, ...] = (),
    normalize: bool = True,
) -> FeatureSet:
    """Build the vertex and edge feature matrices for one mesh."""
    context = MeshContext(mesh, normalize=normalize)
    excluded = frozenset(exclude)
    present: dict[str, bool] = {}

    vertex_matrix, vertex_names = _assemble(
        _selected(VERTEX_EXTRACTORS, tiers), context, excluded, present, context.n_verts
    )
    edge_matrix, edge_names = _assemble(
        _selected(EDGE_EXTRACTORS, tiers), context, excluded, present, len(context.edges)
    )

    return FeatureSet(
        vertex=vertex_matrix,
        vertex_names=vertex_names,
        edge=edge_matrix,
        edge_names=edge_names,
        edges=context.edges,
        present=present,
        metadata={
            "tiers": list(tiers),
            "excluded": sorted(excluded),
            "diagonal": context.diagonal,
            "normalization": context.normalization.to_dict(),
        },
    )


def vertex_dim(tiers: tuple[str, ...] = DEFAULT_TIERS) -> int:
    return sum(e.output_dim for e in _selected(VERTEX_EXTRACTORS, tiers))


def edge_dim(tiers: tuple[str, ...] = DEFAULT_TIERS) -> int:
    return sum(e.output_dim for e in _selected(EDGE_EXTRACTORS, tiers))


def safety_mask(features: FeatureSet, bone_threshold: float = 0.5) -> np.ndarray:
    """Edges the model must not learn to destroy (§20 Signal C, §44)."""
    mask = np.zeros(len(features.edges), dtype=bool)
    for cue in SAFETY_CUES:
        column = features.column(cue)
        if column is None or not features.present.get(cue, False):
            continue
        threshold = bone_threshold if cue == "bone_weight_difference" else 0.5
        mask |= column > threshold
    return mask
