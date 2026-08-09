"""
edge_features.py — 19-cue per-edge feature descriptor for Crunch3D.

Computes a feature vector for every unique edge of a mesh and fuses the cues
into a single per-edge importance score in [0, 1].  The fused score is used
by the optimizer to modulate the QEM collapse cost so perceptually critical
edges (sharp creases, silhouettes, UV seams, rig-deformed regions, ...) are
protected during decimation.

Feature suite (in fusion order):

    1.  edge_length                  spatial extent of the edge
    2.  curvature                    multi-cue vertex importance mapped to edges
    3.  mean_curvature               discrete mean curvature (mode-aware)
    4.  gaussian_curvature           angle-defect Gaussian curvature
    5.  dihedral_angle               angle between adjacent face normals
    6.  surface_normal_difference    angle between endpoint vertex normals
    7.  material_boundary            edge between faces with differing color
    8.  uv_seam                      UV-space discontinuity flag
    9.  bone_weight_difference       rig influence imbalance across endpoints
    10. texture_gradient             color / UV-space gradient magnitude
    11. ambient_occlusion            cheap concavity-based occlusion estimate
    12. vertex_color_difference      endpoint color distance
    13. sharp_edge_flag              dihedral-angle threshold flag
    14. boundary_edge_flag           edge referenced by a single face
    15. surface_area_contribution    area of the adjacent face pair
    16. screen_space_importance      canonical projected edge length
    17. visibility_score             normal-vs-view facing + ambient occlusion
    18. silhouette_score             perpendicular-of-normal-to-view estimate
    19. animation_influence          deformation / rig sensitivity score

All computations are vectorised with NumPy. Every cue degrades gracefully when
the attribute it needs (UVs, vertex colors, rig weights, ...) is missing: the
cue is reported as ``present=False`` and excluded from the fusion, so the rest
of the pipeline is never disturbed.
"""

from __future__ import annotations

import dataclasses
from typing import Optional

import numpy as np
import trimesh

from .animation_awareness import _detect_rig_attributes
from .config import CURVATURE_MODE
from .uv_density import has_uvs

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FEATURE_NAMES: list[str] = [
    "edge_length",
    "curvature",
    "mean_curvature",
    "gaussian_curvature",
    "dihedral_angle",
    "surface_normal_difference",
    "material_boundary",
    "uv_seam",
    "bone_weight_difference",
    "texture_gradient",
    "ambient_occlusion",
    "vertex_color_difference",
    "sharp_edge_flag",
    "boundary_edge_flag",
    "surface_area_contribution",
    "screen_space_importance",
    "visibility_score",
    "silhouette_score",
    "animation_influence",
]

EDGE_FEATURE_COUNT: int = len(FEATURE_NAMES)

# Fusion weights — must be non-negative. Cues with no data are excluded from
# the weighted average, so the weights never need to sum to 1 exactly.
# Dihedral angle (in degrees) above which an edge is considered "sharp".
SHARP_DIHEDRAL_DEGREES: float = 40.0

# UV edge length (relative to the median) above which an edge is a UV seam.
UV_SEAM_FACTOR: float = 4.0

# Distance fraction of the diagonal used to place the canonical camera.
CAMERA_DISTANCE_FRACTION: float = 2.5

# Percentile used for robust normalisation of continuous cues.
NORMALIZATION_PERCENTILE: float = 95.0

FEATURE_WEIGHTS: dict[str, float] = {
    "edge_length": 0.05,
    "curvature": 0.07,
    "mean_curvature": 0.07,
    "gaussian_curvature": 0.05,
    "dihedral_angle": 0.09,
    "surface_normal_difference": 0.06,
    "material_boundary": 0.04,
    "uv_seam": 0.06,
    "bone_weight_difference": 0.08,
    "texture_gradient": 0.05,
    "ambient_occlusion": 0.05,
    "vertex_color_difference": 0.03,
    "sharp_edge_flag": 0.10,
    "boundary_edge_flag": 0.04,
    "surface_area_contribution": 0.04,
    "screen_space_importance": 0.03,
    "visibility_score": 0.03,
    "silhouette_score": 0.03,
    "animation_influence": 0.08,
}

# Human-readable metadata for each cue. Lives here rather than in the frontend
# so the API, the logs and the UI all describe a cue the same way.
FEATURE_METADATA: dict[str, dict[str, str]] = {
    "edge_length": {
        "label": "Edge Length",
        "group": "Geometry",
        "description": "Spatial extent of the edge. Long edges span more surface, so collapsing one moves more geometry.",
    },
    "curvature": {
        "label": "Curvature",
        "group": "Geometry",
        "description": "Fused multi-cue vertex importance mapped onto the edge.",
    },
    "mean_curvature": {
        "label": "Mean Curvature",
        "group": "Geometry",
        "description": "Discrete mean curvature across the edge — how sharply the surface bends.",
    },
    "gaussian_curvature": {
        "label": "Gaussian Curvature",
        "group": "Geometry",
        "description": "Angle-defect curvature. Peaks at cones, tips and saddle points.",
    },
    "dihedral_angle": {
        "label": "Dihedral Angle",
        "group": "Geometry",
        "description": "Angle between the two adjacent face normals. High on hard creases.",
    },
    "surface_normal_difference": {
        "label": "Surface Normal Difference",
        "group": "Geometry",
        "description": "Angle between the endpoint vertex normals — shading discontinuity risk.",
    },
    "surface_area_contribution": {
        "label": "Surface Area Contribution",
        "group": "Geometry",
        "description": "Combined area of the adjacent faces. Large faces carry more of the silhouette.",
    },
    "sharp_edge_flag": {
        "label": "Sharp Edge Flag",
        "group": "Topology",
        "description": f"Set when the dihedral angle exceeds {SHARP_DIHEDRAL_DEGREES:.0f} degrees — a hard crease to preserve.",
    },
    "boundary_edge_flag": {
        "label": "Boundary Edge Flag",
        "group": "Topology",
        "description": "Set when only one face uses the edge — an open border or hole rim.",
    },
    "material_boundary": {
        "label": "Material Boundary",
        "group": "Appearance",
        "description": "Set where adjacent faces differ in colour, marking a material transition.",
    },
    "uv_seam": {
        "label": "UV Seam",
        "group": "Appearance",
        "description": "Discontinuity in UV space. Collapsing a seam smears the texture.",
    },
    "texture_gradient": {
        "label": "Texture Gradient",
        "group": "Appearance",
        "description": "Rate of colour or UV change along the edge — high-detail texture regions.",
    },
    "vertex_color_difference": {
        "label": "Vertex Color Difference",
        "group": "Appearance",
        "description": "Colour distance between the endpoints of the edge.",
    },
    "ambient_occlusion": {
        "label": "Ambient Occlusion",
        "group": "Appearance",
        "description": "Cavity estimate from local concavity. Creases and folds read as occluded.",
    },
    "screen_space_importance": {
        "label": "Screen-space Importance",
        "group": "View",
        "description": "Projected edge length from a canonical camera — the on-screen footprint.",
    },
    "visibility_score": {
        "label": "Visibility Score",
        "group": "View",
        "description": "How much the edge faces the viewer, damped by its occlusion estimate.",
    },
    "silhouette_score": {
        "label": "Silhouette Score",
        "group": "View",
        "description": "Peaks where the surface turns away from the camera — the outline of the model.",
    },
    "bone_weight_difference": {
        "label": "Bone Weight Difference",
        "group": "Deformation",
        "description": "Rig influence imbalance across the edge. High at joints that bend.",
    },
    "animation_influence": {
        "label": "Animation Influence",
        "group": "Deformation",
        "description": "Deformation sensitivity from rig weights, or a Laplacian energy heuristic.",
    },
}

# Binary (0/1) cues that must not be percentile-normalised during fusion.
_FLAG_FEATURES = {
    "material_boundary",
    "uv_seam",
    "sharp_edge_flag",
    "boundary_edge_flag",
}


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class EdgeFeatureResult:
    """Per-edge descriptor plus the fused importance score for one mesh.

    ``edges`` is the ``(E, 2)`` unique-edge index array the feature arrays are
    aligned with. Callers must use these edge indices (not ``edges_unique``
    from trimesh) when scatter-mapping scores back to vertices.
    """

    edges: np.ndarray
    features: dict[str, np.ndarray]
    present: dict[str, bool]
    importance: np.ndarray
    summary: dict

    def feature_matrix(self) -> np.ndarray:
        """Return the cues as an ``(E, 19)`` matrix in ``FEATURE_NAMES`` order.

        Missing cues are emitted as zero columns so the layout is stable across
        meshes — this is what makes the descriptor usable as a GNN edge-feature
        block without per-mesh bookkeeping.
        """
        n_edges = len(self.edges)
        matrix = np.zeros((n_edges, EDGE_FEATURE_COUNT), dtype=np.float32)
        for col, name in enumerate(FEATURE_NAMES):
            arr = self.features.get(name)
            if arr is None or len(arr) != n_edges:
                continue
            matrix[:, col] = np.asarray(arr, dtype=np.float32)
        return matrix


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _percentile_normalize(
    arr: np.ndarray, percentile: float = NORMALIZATION_PERCENTILE
) -> np.ndarray:
    arr = np.asarray(arr, dtype=np.float64)
    if arr.size == 0:
        return arr
    ceil = float(np.percentile(arr, percentile))
    if ceil <= 1e-12:
        return np.zeros_like(arr)
    return np.clip(arr / ceil, 0.0, 1.0)


def _vertex_to_edge(arr: np.ndarray, e0: np.ndarray, e1: np.ndarray) -> np.ndarray:
    return (np.asarray(arr, dtype=np.float64)[e0] + np.asarray(arr, dtype=np.float64)[e1]) * 0.5


def _canonical_camera_pos(verts: np.ndarray) -> tuple[np.ndarray, float]:
    center = (verts.min(axis=0) + verts.max(axis=0)) * 0.5
    diag = float(np.linalg.norm(verts.max(axis=0) - verts.min(axis=0)))
    direction = np.array([3.0, 2.0, 3.0], dtype=np.float64)
    direction = direction / max(float(np.linalg.norm(direction)), 1e-12)
    return center + direction * max(diag * CAMERA_DISTANCE_FRACTION, 1e-6), diag


def _build_edge_mapping(faces: np.ndarray, n_verts: int) -> tuple[np.ndarray, ...]:
    """Return (edges, face_a, face_b, counts) for every unique edge.

    ``edges`` is in deterministic sorted-(min,max) key order. ``face_a`` /
    ``face_b`` are the two adjacent face indices (``-1`` when the edge belongs
    to a single face). ``counts`` is the face-incidence count per edge.
    """
    f = len(faces)
    triplets = np.empty((3 * f, 2), dtype=np.int64)
    triplets[0::3] = faces[:, [0, 1]]
    triplets[1::3] = faces[:, [1, 2]]
    triplets[2::3] = faces[:, [2, 0]]

    lo = np.minimum(triplets[:, 0], triplets[:, 1])
    hi = np.maximum(triplets[:, 0], triplets[:, 1])
    keys = lo * n_verts + hi

    order = np.argsort(keys, kind="stable")
    sorted_keys = keys[order]
    face_of = np.repeat(np.arange(f), 3)[order]

    unique_keys, starts, counts = np.unique(sorted_keys, return_index=True, return_counts=True)

    edges = np.column_stack([unique_keys // n_verts, unique_keys % n_verts]).astype(np.int64)
    face_a = face_of[starts]

    # ``np.where`` evaluates both branches, so the second-face lookup must be a
    # valid index even for boundary edges. Clamping keeps it in range; the
    # ``counts >= 2`` mask discards whatever it read.
    second = np.minimum(starts + 1, len(face_of) - 1)
    face_b = np.where(counts >= 2, face_of[second], -1)
    return edges, face_a, face_b, counts


# ---------------------------------------------------------------------------
# Vertex-level cues
# ---------------------------------------------------------------------------

def _vertex_normal_deviation(mesh: trimesh.Trimesh) -> np.ndarray:
    """Vectorised normal-deviation curvature proxy (replaces the scalar loop)."""
    vn = np.asarray(mesh.vertex_normals, dtype=np.float64)
    fn = np.asarray(mesh.face_normals, dtype=np.float64)
    v = np.asarray(mesh.faces, dtype=np.int64)
    acc = np.zeros(len(mesh.vertices), dtype=np.float64)
    cnt = np.zeros(len(mesh.vertices), dtype=np.float64)

    for vi in range(3):
        col = v[:, vi]
        dot = np.clip(np.einsum("ij,ij->i", vn[col], fn), -1.0, 1.0)
        np.add.at(acc, col, np.arccos(np.abs(dot)))
        np.add.at(cnt, col, 1.0)

    mask = cnt > 0
    acc[mask] /= cnt[mask]
    acc /= (np.pi / 2.0)
    return np.clip(acc, 0.0, 1.0)


def _vertex_mean_curvature(mesh: trimesh.Trimesh) -> np.ndarray:
    """Discrete mean curvature, honouring ``CURVATURE_MODE``."""
    if CURVATURE_MODE == "accurate":
        try:
            from trimesh.curvature import discrete_mean_curvature_measure
            bbox_max = float(mesh.bounding_box.extents.max())
            radius = max(bbox_max * 0.02, 1e-6)
            raw = discrete_mean_curvature_measure(mesh, mesh.vertices, radius=radius)
            return np.abs(np.asarray(raw, dtype=np.float64))
        except Exception:
            pass
    return _vertex_normal_deviation(mesh)


def _vertex_gaussian_curvature(verts: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Angle-defect Gaussian curvature (vectorised, no scipy required)."""
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]

    def corner_angle(pa: np.ndarray, pb: np.ndarray, pc: np.ndarray) -> np.ndarray:
        ab = pb - pa
        ac = pc - pa
        denom = np.linalg.norm(ab, axis=1) * np.linalg.norm(ac, axis=1)
        cos = np.einsum("ij,ij->i", ab, ac) / (denom + 1e-12)
        return np.arccos(np.clip(cos, -1.0, 1.0))

    acc = np.zeros(len(verts), dtype=np.float64)
    np.add.at(acc, faces[:, 0], corner_angle(v0, v1, v2))
    np.add.at(acc, faces[:, 1], corner_angle(v1, v2, v0))
    np.add.at(acc, faces[:, 2], corner_angle(v2, v0, v1))

    defect = 2.0 * np.pi - acc
    return np.abs(defect)


def _vertex_ambient_occlusion(
    verts: np.ndarray,
    edges: np.ndarray,
    vertex_normals: np.ndarray,
) -> np.ndarray:
    """Cheap concavity-based ambient occlusion estimate in [0, 1].

    For every 1-ring neighbour ``u`` of a vertex ``v`` we take the signed
    projection of the (normalised) direction ``u - v`` onto ``n_v``:

        occ(v) = mean_u  clamp( dot(normalize(u - v), n_v), 0, 1 )

    A neighbour sitting *in front of* the tangent plane means the surface
    folds back over ``v`` — a cavity, so more occluded. A convex vertex has
    all its neighbours behind the plane and scores ~0. This is the standard
    cheap curvature-AO approximation and needs no ray casting.

    Uses the unique-edge list so each 1-ring neighbour is counted once,
    which the face-corner formulation would not guarantee.
    """
    n_verts = len(verts)
    acc = np.zeros(n_verts, dtype=np.float64)
    cnt = np.zeros(n_verts, dtype=np.float64)

    if len(edges) == 0:
        return acc

    a = edges[:, 0]
    b = edges[:, 1]
    delta = verts[b] - verts[a]
    length = np.linalg.norm(delta, axis=1)
    direction = delta / (length[:, None] + 1e-12)

    # a → b for one endpoint, b → a (negated) for the other.
    occ_a = np.clip(np.einsum("ij,ij->i", direction, vertex_normals[a]), 0.0, 1.0)
    occ_b = np.clip(np.einsum("ij,ij->i", -direction, vertex_normals[b]), 0.0, 1.0)

    np.add.at(acc, a, occ_a)
    np.add.at(cnt, a, 1.0)
    np.add.at(acc, b, occ_b)
    np.add.at(cnt, b, 1.0)

    return np.clip(acc / np.maximum(cnt, 1.0), 0.0, 1.0)


def _vertex_deformation_energy(verts: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Vectorised umbrella-operator deformation energy per vertex.

    Mirrors ``animation_awareness._laplacian_deformation_energy`` but without
    the per-vertex Python loop, so the animation cue stays cheap enough to run
    inside the decimation hot path.
    """
    n_verts = len(verts)
    if len(edges) == 0:
        return np.zeros(n_verts, dtype=np.float64)

    a = edges[:, 0]
    b = edges[:, 1]
    neighbour_sum = np.zeros((n_verts, 3), dtype=np.float64)
    neighbour_count = np.zeros(n_verts, dtype=np.float64)

    np.add.at(neighbour_sum, a, verts[b])
    np.add.at(neighbour_count, a, 1.0)
    np.add.at(neighbour_sum, b, verts[a])
    np.add.at(neighbour_count, b, 1.0)

    safe = np.maximum(neighbour_count, 1.0)[:, None]
    centroid = neighbour_sum / safe
    energy = np.linalg.norm(verts - centroid, axis=1)
    energy[neighbour_count == 0] = 0.0
    return energy


def _edge_animation_influence(
    mesh: trimesh.Trimesh,
    verts: np.ndarray,
    edges: np.ndarray,
    animation_importance: Optional[np.ndarray],
) -> np.ndarray:
    """Per-vertex rig / deformation sensitivity for the animation cue.

    Order of preference:
      1. a caller-supplied ``animation_importance`` array (no recomputation),
      2. real rig weights when the loader attached them,
      3. a vectorised deformation-energy heuristic.

    The expensive ``compute_animation_importance`` path is deliberately not
    used here: ``compute_importance`` already folds it into the base score,
    and its per-vertex Python loop would double the cost of every component.
    """
    n_verts = len(verts)
    if animation_importance is not None and len(animation_importance) == n_verts:
        return np.asarray(animation_importance, dtype=np.float64)

    rig_weights = _detect_rig_attributes(mesh)
    if rig_weights is not None and len(rig_weights) == n_verts:
        return np.asarray(rig_weights, dtype=np.float64)

    return _vertex_deformation_energy(verts, edges)


def _vertex_colors(mesh: trimesh.Trimesh) -> np.ndarray | None:
    n_verts = len(mesh.vertices)
    color: np.ndarray | None = None
    attrs = getattr(mesh, "vertex_attributes", None) or {}
    if "color" in attrs:
        raw = np.asarray(attrs["color"], dtype=np.float64)
        if raw.ndim == 2 and raw.shape[1] >= 3 and raw.shape[0] == n_verts:
            color = np.clip(raw[:, :3] / 255.0, 0.0, 1.0)
    if color is None:
        try:
            visual = getattr(mesh, "visual", None)
            if visual is not None:
                vc = visual.vertex_colors
                if vc is not None and len(vc) == n_verts and np.asarray(vc).ndim == 2:
                    raw = np.asarray(vc, dtype=np.float64)
                    if raw.shape[1] >= 4:
                        color = np.clip(raw[:, :3] / 255.0, 0.0, 1.0)
        except Exception:
            pass
    if color is None:
        return None
    if float(np.std(color)) < 1e-4:
        return None
    return color


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_edge_feature_importance(
    mesh: trimesh.Trimesh,
    vertex_importance: Optional[np.ndarray] = None,
    animation_importance: Optional[np.ndarray] = None,
) -> EdgeFeatureResult:
    """Compute the 19-cue edge descriptor and fused per-edge importance.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Single-component input mesh.
    vertex_importance : (V,) array, optional
        Pre-computed per-vertex importance from ``compute_importance``. Used as
        the ``curvature`` cue (already encodes curvature, UV density, animation
        sensitivity) and to avoid re-running the expensive heuristic path.
    animation_importance : (V,) array, optional
        Pre-computed per-vertex animation importance to avoid re-deriving it.

    Returns
    -------
    EdgeFeatureResult
        Aligned edge index array, per-cue feature arrays, presence flags, fused
        importance and a JSON-safe summary.
    """
    n_verts = len(mesh.vertices)
    n_faces = len(mesh.faces)

    if n_verts == 0 or n_faces == 0:
        return _empty_result()

    verts = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    edges, face_a, face_b, counts = _build_edge_mapping(faces, n_verts)
    e0 = edges[:, 0]
    e1 = edges[:, 1]
    n_edges_total = len(edges)

    vertex_normals = np.asarray(mesh.vertex_normals, dtype=np.float64)
    face_normals = np.asarray(mesh.face_normals, dtype=np.float64)

    pos0 = verts[e0]
    pos1 = verts[e1]

    features: dict[str, np.ndarray] = {}
    present: dict[str, bool] = {}

    # 1. Edge length -------------------------------------------------------
    edge_length = np.linalg.norm(pos1 - pos0, axis=1)
    features["edge_length"] = edge_length
    present["edge_length"] = True

    # 2. Curvature (multi-cue importance proxy, mapped to edges)
    mean_curv = _vertex_mean_curvature(mesh)
    if vertex_importance is not None and len(vertex_importance) == n_verts:
        curvature = _vertex_to_edge(vertex_importance, e0, e1)
    else:
        curvature = _vertex_to_edge(mean_curv, e0, e1)
    features["curvature"] = curvature
    present["curvature"] = True

    # 3. Mean curvature
    features["mean_curvature"] = _vertex_to_edge(mean_curv, e0, e1)
    present["mean_curvature"] = True

    # 4. Gaussian curvature (angle defect)
    features["gaussian_curvature"] = _vertex_to_edge(
        _vertex_gaussian_curvature(verts, faces), e0, e1
    )
    present["gaussian_curvature"] = True

    # 5. Dihedral angle (between the two adjacent face normals, [0, pi/pi])
    dihedral = np.zeros(n_edges_total, dtype=np.float64)
    manifold = counts >= 2
    if np.any(manifold):
        n1 = face_normals[face_a[manifold]]
        n2 = face_normals[face_b[manifold]]
        dot = np.clip(np.einsum("ij,ij->i", n1, n2), -1.0, 1.0)
        dihedral[manifold] = np.arccos(dot) / np.pi
    features["dihedral_angle"] = dihedral
    present["dihedral_angle"] = True

    # 6. Surface normal difference (endpoint vertex normals)
    vn_dot = np.clip(np.einsum("ij,ij->i", vertex_normals[e0], vertex_normals[e1]), -1.0, 1.0)
    features["surface_normal_difference"] = np.arccos(vn_dot) / np.pi
    present["surface_normal_difference"] = True

    # 7. Material boundary (face-color divergence, when colours are present)
    material_boundary = np.zeros(n_edges_total, dtype=np.float64)
    has_material_boundary = False
    vcolors = _vertex_colors(mesh)
    has_colors = vcolors is not None
    if has_colors:
        face_color = (vcolors[faces[:, 0]] + vcolors[faces[:, 1]] + vcolors[faces[:, 2]]) / 3.0
        d = np.zeros(n_edges_total, dtype=np.float64)
        d[manifold] = np.linalg.norm(
            face_color[face_a[manifold]] - face_color[face_b[manifold]], axis=1
        )
        material_mask = d > 0.1
        material_boundary[material_mask] = 1.0
        has_material_boundary = bool(np.any(material_mask))
    features["material_boundary"] = material_boundary
    present["material_boundary"] = has_material_boundary

    # 8. UV seam
    uv_seam = np.zeros(n_edges_total, dtype=np.float64)
    has_uvs_data = has_uvs(mesh)
    uv = None
    if has_uvs_data:
        try:
            uv = np.asarray(mesh.visual.uv, dtype=np.float64)
            if uv.shape != (n_verts, 2):
                uv = None
        except Exception:
            uv = None
    uv_seam_present = uv is not None
    if uv is not None:
        uv_len = np.linalg.norm(uv[e0] - uv[e1], axis=1)
        median_len = float(np.median(uv_len))
        if median_len > 1e-9:
            uv_seam[uv_len > UV_SEAM_FACTOR * median_len] = 1.0
        uv_seam_present = True
    features["uv_seam"] = uv_seam
    present["uv_seam"] = uv_seam_present

    # 9. Bone weight difference
    rig_weights = _detect_rig_attributes(mesh)
    bone_diff = np.zeros(n_edges_total, dtype=np.float64)
    if rig_weights is not None and len(rig_weights) == n_verts:
        bone_diff = np.abs(rig_weights[e0] - rig_weights[e1])
    features["bone_weight_difference"] = bone_diff
    present["bone_weight_difference"] = rig_weights is not None

    # 10. Texture gradient (color distance / length, else UV-space gradient)
    texture_gradient = np.zeros(n_edges_total, dtype=np.float64)
    has_texture_gradient = False
    if vcolors is not None:
        color_dist = np.linalg.norm(vcolors[e0] - vcolors[e1], axis=1)
        texture_gradient = color_dist / (edge_length + 1e-12)
        has_texture_gradient = True
    elif uv is not None:
        uv_len = np.linalg.norm(uv[e0] - uv[e1], axis=1)
        texture_gradient = uv_len / (edge_length + 1e-12)
        has_texture_gradient = True
    features["texture_gradient"] = texture_gradient
    present["texture_gradient"] = has_texture_gradient

    # 11. Ambient occlusion (concavity estimate over the 1-ring)
    ao = _vertex_ambient_occlusion(verts, edges, vertex_normals)
    features["ambient_occlusion"] = _vertex_to_edge(ao, e0, e1)
    present["ambient_occlusion"] = True

    # 12. Vertex color difference
    color_difference = np.zeros(n_edges_total, dtype=np.float64)
    if vcolors is not None:
        d = np.linalg.norm(vcolors[e0] - vcolors[e1], axis=1)
        color_difference = np.clip(d / np.sqrt(3.0), 0.0, 1.0)
    features["vertex_color_difference"] = color_difference
    present["vertex_color_difference"] = vcolors is not None

    # 13. Sharp edge flag
    sharp_flag = (dihedral > SHARP_DIHEDRAL_DEGREES / 180.0).astype(np.float64)
    features["sharp_edge_flag"] = sharp_flag
    present["sharp_edge_flag"] = True

    # 14. Boundary edge flag
    boundary_flag = (counts == 1).astype(np.float64)
    features["boundary_edge_flag"] = boundary_flag
    present["boundary_edge_flag"] = True

    # 15. Surface area contribution (sum of adjacent face areas)
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    face_areas = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
    pair = face_areas[face_a] + np.where(manifold, face_areas[face_b], 0.0)
    features["surface_area_contribution"] = pair
    present["surface_area_contribution"] = True

    # Canonical camera for view-dependent cues
    camera_pos, diag = _canonical_camera_pos(verts)
    mid = (pos0 + pos1) * 0.5
    depth = np.linalg.norm(camera_pos[None, :] - mid, axis=1)
    view_dir = camera_pos[None, :] - verts
    view_norm = np.linalg.norm(view_dir, axis=1)
    view_dir = view_dir / (view_norm[:, None] + 1e-12)
    view_mid = camera_pos[None, :] - mid
    view_mid = view_mid / (np.linalg.norm(view_mid, axis=1)[:, None] + 1e-12)

    # 16. Screen-space importance (canonical projected length)
    ss = edge_length / np.maximum(depth, 1e-9)
    features["screen_space_importance"] = ss
    present["screen_space_importance"] = True

    # 17. Visibility score (facing + ambient occlusion)
    facing = 0.5 + 0.5 * np.maximum(0.0, np.einsum("ij,ij->i", vertex_normals, view_dir))
    vis_v = facing * (0.25 + 0.75 * np.maximum(ao, 0.0))
    features["visibility_score"] = _vertex_to_edge(vis_v, e0, e1)
    present["visibility_score"] = True

    # 18. Silhouette score (|normal . view| ~ 0 for silhouette edges)
    n_a = face_normals[face_a]
    n_b_eff = np.where(manifold[:, None], face_normals[face_b], n_a)
    edge_normals = n_a + n_b_eff
    edge_normals = edge_normals / (np.linalg.norm(edge_normals, axis=1)[:, None] + 1e-12)
    sil_raw = 1.0 - np.abs(np.einsum("ij,ij->i", edge_normals, view_mid))
    max_len = float(edge_length.max()) if edge_length.size else 0.0
    sil = sil_raw * (edge_length / max(max_len, 1e-12)) if max_len > 0 else sil_raw
    features["silhouette_score"] = sil
    present["silhouette_score"] = True

    # 19. Animation influence (rig weights when present, else deformation energy)
    anim_vertex = _edge_animation_influence(mesh, verts, edges, animation_importance)
    features["animation_influence"] = _vertex_to_edge(anim_vertex, e0, e1)
    present["animation_influence"] = True

    # ── Fusion into a single [0, 1] importance score ────────────────────────
    acc = np.zeros(n_edges_total, dtype=np.float64)
    weight_sum = 0.0
    for name in FEATURE_NAMES:
        raw = features[name]
        if not present.get(name, False):
            continue
        weight = FEATURE_WEIGHTS.get(name, 0.0)
        if weight <= 0.0:
            continue
        cue = raw if name in _FLAG_FEATURES else _safe_normalize(raw)
        acc += weight * cue
        weight_sum += weight

    if weight_sum <= 1e-12:
        importance = np.full(n_edges_total, 0.5, dtype=np.float64)
    else:
        importance = _normalize_importance(acc / weight_sum)

    summary = _build_summary(features, present, importance)

    return EdgeFeatureResult(
        edges=edges,
        features=features,
        present=present,
        importance=importance,
        summary=summary,
    )


def _safe_normalize(arr: np.ndarray) -> np.ndarray:
    return _percentile_normalize(arr)


def _normalize_importance(arr: np.ndarray) -> np.ndarray:
    """Final shaping of the fused importance — bounded to [0, 1] without
    re-compressing the distribution, so relative ordering is preserved."""
    return np.clip(np.asarray(arr, dtype=np.float64), 0.0, 1.0)


def _build_summary(
    features: dict[str, np.ndarray], present: dict[str, bool], importance: np.ndarray
) -> dict:
    items: list[dict] = []
    for name in FEATURE_NAMES:
        arr = features.get(name)
        if arr is None or arr.size == 0:
            items.append({"name": name, "mean": 0.0, "min": 0.0, "max": 0.0,
                          "present": bool(present.get(name, False))})
            continue
        items.append({
            "name": name,
            "mean": round(float(np.mean(arr)), 4),
            "min": round(float(np.min(arr)), 4),
            "max": round(float(np.max(arr)), 4),
            "present": bool(present.get(name, False)),
        })

    if importance.size == 0:
        imp_stats = {"mean": 0.0, "min": 0.0, "max": 0.0, "p95": 0.0}
    else:
        imp_stats = {
            "mean": round(float(np.mean(importance)), 4),
            "min": round(float(np.min(importance)), 4),
            "max": round(float(np.max(importance)), 4),
            "p95": round(float(np.percentile(importance, 95)), 4),
        }

    return {
        "edge_count": int(importance.size),
        "features": items,
        "importance": imp_stats,
    }


def _empty_result() -> EdgeFeatureResult:
    summary = {
        "edge_count": 0,
        "features": [
            {"name": name, "mean": 0.0, "min": 0.0, "max": 0.0, "present": False}
            for name in FEATURE_NAMES
        ],
        "importance": {"mean": 0.0, "min": 0.0, "max": 0.0, "p95": 0.0},
    }
    return EdgeFeatureResult(
        edges=np.zeros((0, 2), dtype=np.int64),
        features={},
        present={},
        importance=np.zeros(0, dtype=np.float64),
        summary=summary,
    )


def scatter_to_vertices(result: EdgeFeatureResult, n_verts: int) -> np.ndarray:
    """Collapse per-edge importance onto vertices, taking the max per vertex.

    Max (rather than mean) is deliberate: a vertex touching a single sharp
    crease must inherit that crease's protection even when its remaining
    incident edges are flat, otherwise averaging would dilute exactly the
    feature the descriptor is meant to preserve.
    """
    vertex_importance = np.zeros(max(n_verts, 0), dtype=np.float64)
    if n_verts <= 0 or result.importance.size == 0 or len(result.edges) == 0:
        return vertex_importance

    edges = result.edges
    in_range = (edges[:, 0] < n_verts) & (edges[:, 1] < n_verts)
    if not np.all(in_range):
        edges = edges[in_range]
        scores = result.importance[in_range]
    else:
        scores = result.importance

    np.maximum.at(vertex_importance, edges[:, 0], scores)
    np.maximum.at(vertex_importance, edges[:, 1], scores)
    return vertex_importance