"""features/vertex.py — the §11 vertex feature block.

    [x, y, z]  [nx, ny, nz]  normalized_valence  boundary_flag
    vertex_mean_curvature  vertex_gaussian_curvature

Positions come from the scale-normalized copy (§5.3), so the encoder cannot
learn "large object = important".  The Laplacian positional encoding is added
separately by ``graph/positional_encoding.py`` because it needs the graph, not
the mesh.
"""

from __future__ import annotations

import numpy as np

from .base import FeatureExtractor, MeshContext, percentile_norm


class Position(FeatureExtractor):
    name = "position"
    output_dim = 3
    tier = "A"
    domain = "vertex"

    def compute(self, mesh: MeshContext) -> np.ndarray:
        return mesh.verts.astype(np.float32)


class Normal(FeatureExtractor):
    name = "normal"
    output_dim = 3
    tier = "A"
    domain = "vertex"

    def compute(self, mesh: MeshContext) -> np.ndarray:
        return mesh.vertex_normals.astype(np.float32)


class Valence(FeatureExtractor):
    name = "valence"
    tier = "A"
    domain = "vertex"

    def compute(self, mesh: MeshContext) -> np.ndarray:
        valence = mesh.valence
        ceiling = float(valence.max()) if valence.size else 0.0
        scaled = valence / ceiling if ceiling > 0.0 else valence
        return scaled.astype(np.float32)[:, None]


class BoundaryVertex(FeatureExtractor):
    name = "boundary_flag"
    tier = "A"
    domain = "vertex"

    def compute(self, mesh: MeshContext) -> np.ndarray:
        return mesh.boundary_vertex.astype(np.float32)[:, None]


class VertexMeanCurvature(FeatureExtractor):
    name = "vertex_mean_curvature"
    tier = "A"
    domain = "vertex"

    def compute(self, mesh: MeshContext) -> np.ndarray:
        return percentile_norm(mesh.mean_curvature)[:, None]


class VertexGaussianCurvature(FeatureExtractor):
    name = "vertex_gaussian_curvature"
    tier = "A"
    domain = "vertex"

    def compute(self, mesh: MeshContext) -> np.ndarray:
        return percentile_norm(mesh.gaussian_curvature)[:, None]


VERTEX_EXTRACTORS: list[FeatureExtractor] = [
    Position(),
    Normal(),
    Valence(),
    BoundaryVertex(),
    VertexMeanCurvature(),
    VertexGaussianCurvature(),
]
