"""Modular feature-extraction engine (System B, §7-11)."""

from .base import FeatureExtractor, FeatureSet, MeshContext
from .registry import (
    DEFAULT_TIERS,
    FEATURE_REGISTRY,
    edge_dim,
    extract,
    safety_mask,
    vertex_dim,
)

__all__ = [
    "DEFAULT_TIERS",
    "FEATURE_REGISTRY",
    "FeatureExtractor",
    "FeatureSet",
    "MeshContext",
    "edge_dim",
    "extract",
    "safety_mask",
    "vertex_dim",
]
