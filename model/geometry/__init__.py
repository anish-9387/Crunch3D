"""Deterministic geometry engine (System A) — half-edge, quadrics, validation."""

from .halfedge import HalfEdgeMesh
from .normalize import Normalization, normalize_mesh
from .quadric import QuadricSet
from .validation import ValidationReport, validate

__all__ = [
    "HalfEdgeMesh",
    "Normalization",
    "QuadricSet",
    "ValidationReport",
    "normalize_mesh",
    "validate",
]
