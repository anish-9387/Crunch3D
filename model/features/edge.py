"""features/edge.py — the §8/§9/§10 edge feature tiers.

Tier A (§8) — always computed:
    normalized_edge_length  dihedral_angle  normal_difference
    curvature_difference    boundary_edge   surface_area_fraction

Tier B (§9) — computed when the asset carries the data:
    uv_seam  material_boundary  sharp_edge  vertex_color_difference
    bone_weight_difference

Tier C (§10) — registered but off by default, per §108 ("do not add texture /
AO / animation before geometry-only ML works"):
    texture_gradient  ambient_occlusion  screen_space_importance
    visibility_score  silhouette_score   animation_influence

Every cue reads from the shipped 19-cue descriptor so a value here and the value
the production optimizer protects with cannot diverge.  The two places the plan
asks for a different form than the descriptor stores (§8.1 length normalized by
the bbox diagonal, §8.3 normal difference as ``1 - dot(n1, n2)`` over adjacent
*face* normals) are derived exactly from it rather than recomputed.
"""

from __future__ import annotations

import numpy as np

from .base import FeatureExtractor, MeshContext, percentile_norm


class _DescriptorCue(FeatureExtractor):
    """An edge cue taken straight from the 19-cue descriptor."""

    cue: str = ""
    normalize: bool = True
    domain = "edge"

    def available(self, mesh: MeshContext) -> bool:
        return bool(mesh.descriptor.present.get(self.cue, False))

    def compute(self, mesh: MeshContext) -> np.ndarray:
        values = mesh.descriptor.features.get(self.cue)
        if values is None:
            return self.zeros(mesh)
        values = np.asarray(values, dtype=np.float64)
        out = percentile_norm(values) if self.normalize else values.astype(np.float32)
        return out[:, None]


# ── Tier A (§8) ─────────────────────────────────────────────────────────────


class EdgeLength(FeatureExtractor):
    """§8.1 — length divided by the bbox diagonal, so scale cannot leak."""

    name = "normalized_edge_length"
    tier = "A"
    domain = "edge"

    def compute(self, mesh: MeshContext) -> np.ndarray:
        raw = mesh.descriptor.features.get("edge_length")
        if raw is None:
            return self.zeros(mesh)
        return np.clip(np.asarray(raw) / mesh.diagonal, 0.0, 1.0).astype(np.float32)[:, None]


class DihedralAngle(_DescriptorCue):
    """§8.2 — acos(clamp(n1·n2, -1, 1)), stored as a fraction of pi."""

    name = "dihedral_angle"
    cue = "dihedral_angle"
    normalize = False
    tier = "A"


class NormalDifference(FeatureExtractor):
    """§8.3 — ``1 - dot(n1, n2)`` for the two adjacent face normals.

    Derived from the dihedral cue (which stores ``acos(dot)/pi``) so the two are
    consistent by construction; §8.3 asks for both to be kept until an ablation
    proves one redundant.
    """

    name = "normal_difference"
    tier = "A"
    domain = "edge"

    def compute(self, mesh: MeshContext) -> np.ndarray:
        dihedral = mesh.descriptor.features.get("dihedral_angle")
        if dihedral is None:
            return self.zeros(mesh)
        dot = np.cos(np.asarray(dihedral, dtype=np.float64) * np.pi)
        return (0.5 * (1.0 - dot)).astype(np.float32)[:, None]


class CurvatureDifference(FeatureExtractor):
    """§83 curvature jump — |H(u) - H(v)| across the edge."""

    name = "curvature_difference"
    tier = "A"
    domain = "edge"

    def compute(self, mesh: MeshContext) -> np.ndarray:
        edges = mesh.edges
        if len(edges) == 0:
            return self.zeros(mesh)
        curvature = mesh.mean_curvature
        jump = np.abs(curvature[edges[:, 0]] - curvature[edges[:, 1]])
        return percentile_norm(jump)[:, None]


class BoundaryEdge(_DescriptorCue):
    """§8.6 — set when only one face uses the edge."""

    name = "boundary_edge"
    cue = "boundary_edge_flag"
    normalize = False
    tier = "A"


class SurfaceAreaFraction(FeatureExtractor):
    """§8.7 — adjacent face-pair area as a fraction of total mesh area."""

    name = "surface_area_fraction"
    tier = "A"
    domain = "edge"

    def compute(self, mesh: MeshContext) -> np.ndarray:
        raw = mesh.descriptor.features.get("surface_area_contribution")
        if raw is None:
            return self.zeros(mesh)
        return np.clip(np.asarray(raw) / mesh.total_area, 0.0, 1.0).astype(np.float32)[:, None]


# ── Tier B (§9) ─────────────────────────────────────────────────────────────


class UvSeam(_DescriptorCue):
    name = "uv_seam"
    cue = "uv_seam"
    normalize = False
    tier = "B"


class MaterialBoundary(_DescriptorCue):
    name = "material_boundary"
    cue = "material_boundary"
    normalize = False
    tier = "B"


class SharpEdge(_DescriptorCue):
    name = "sharp_edge"
    cue = "sharp_edge_flag"
    normalize = False
    tier = "B"


class VertexColorDifference(_DescriptorCue):
    name = "vertex_color_difference"
    cue = "vertex_color_difference"
    tier = "B"


class BoneWeightDifference(_DescriptorCue):
    name = "bone_weight_difference"
    cue = "bone_weight_difference"
    tier = "B"


# ── Tier C (§10) — registered, off by default ───────────────────────────────


class TextureGradient(_DescriptorCue):
    name = "texture_gradient"
    cue = "texture_gradient"
    tier = "C"


class AmbientOcclusion(_DescriptorCue):
    name = "ambient_occlusion"
    cue = "ambient_occlusion"
    tier = "C"


class ScreenSpaceImportance(_DescriptorCue):
    name = "screen_space_importance"
    cue = "screen_space_importance"
    tier = "C"


class VisibilityScore(_DescriptorCue):
    name = "visibility_score"
    cue = "visibility_score"
    tier = "C"


class SilhouetteScore(_DescriptorCue):
    name = "silhouette_score"
    cue = "silhouette_score"
    tier = "C"


class AnimationInfluence(_DescriptorCue):
    name = "animation_influence"
    cue = "animation_influence"
    tier = "C"


EDGE_EXTRACTORS: list[FeatureExtractor] = [
    EdgeLength(),
    DihedralAngle(),
    NormalDifference(),
    CurvatureDifference(),
    BoundaryEdge(),
    SurfaceAreaFraction(),
    UvSeam(),
    MaterialBoundary(),
    SharpEdge(),
    VertexColorDifference(),
    BoneWeightDifference(),
    TextureGradient(),
    AmbientOcclusion(),
    ScreenSpaceImportance(),
    VisibilityScore(),
    SilhouetteScore(),
    AnimationInfluence(),
]

SAFETY_CUES = (
    "boundary_edge",
    "uv_seam",
    "material_boundary",
    "sharp_edge",
    "bone_weight_difference",
)
"""Cues that mark an edge as hard-constrained for the §20 Signal C safety loss."""
