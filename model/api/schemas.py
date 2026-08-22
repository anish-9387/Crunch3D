from pydantic import BaseModel, Field
from typing import Optional


class MeshStats(BaseModel):
    vertex_count: int
    face_count: int
    file_size_bytes: int
    file_size_mb: float
    has_uvs: bool
    has_normals: bool
    has_animation: bool = False
    bounding_box: Optional[dict] = None


class UploadResponse(BaseModel):
    job_id: str
    filename: str
    original_stats: MeshStats
    message: str


class DesiredOutputSpec(BaseModel):
    use_case: Optional[str] = None
    quality_priority: Optional[str] = None  # "balanced", "quality", "aggressive_reduction"
    preserve_shape: bool = True
    preserve_vertices: bool = True
    preserve_faces: bool = True
    notes: Optional[str] = None


class OptimizeRequest(BaseModel):
    job_id: str
    target_faces: int = Field(gt=0)
    preset: Optional[str] = None  # "web", "mobile", "pc", "vr", "custom"
    generate_lods: bool = False
    preserve_normals: bool = True
    preserve_boundaries: bool = True
    reoptimize_from_latest: bool = True
    strict_quality: bool = True
    max_deviation_percent: float = Field(default=2.0, gt=0.05, le=15.0)
    max_target_overshoot_percent: float = Field(default=12.0, ge=0.0, le=40.0)
    desired_output: Optional[DesiredOutputSpec] = None


class LODResult(BaseModel):
    level: str
    face_count: int
    vertex_count: int
    filename: str
    file_size_mb: float
    reduction_percent: float


class TextureExportInfo(BaseModel):
    texture_preserved: bool = True
    texture_loss_reason: Optional[str] = None
    export_mode_used: str = "full"
    warnings: list[str] = []


class EdgeFeatureStat(BaseModel):
    """Summary of one of the 19 edge-importance cues.

    ``present`` is False when the mesh lacks the data a cue needs (no UVs, no
    skinning, no vertex colours), in which case the cue contributed nothing to
    the importance map and the statistics are all zero.
    """
    key: str
    label: str
    group: str
    description: str
    present: bool
    weight: float
    min: float
    max: float
    mean: float


class EdgeFeatureSummary(BaseModel):
    enabled: bool
    edge_count: int
    features: list[EdgeFeatureStat]


class OptimizeResponse(BaseModel):
    job_id: str
    original_stats: MeshStats
    optimized_stats: MeshStats
    optimized_filename: str
    optimized_format: str
    format_was_converted: bool = False
    target_faces_used: Optional[int] = None
    quality_deviation_percent: Optional[float] = None
    quality_guard_relaxed: bool = False
    quality_guard_satisfied: bool = True
    lods: Optional[list[LODResult]] = None
    reduction_percent: float
    processing_time_seconds: float
    has_importance_map: bool = False
    has_uv_density_map: bool = False
    has_animation_map: bool = False
    is_animated: bool = False
    texture_export: Optional[TextureExportInfo] = None
    edge_features: Optional[EdgeFeatureSummary] = None
    message: str


class JobStatus(BaseModel):
    job_id: str
    status: str  # "uploaded", "processing", "completed", "failed"
    progress: int  # 0-100
    stage: Optional[str] = None
    error: Optional[str] = None


class BrushStampPayload(BaseModel):
    """One dab of the refactor brush, in bbox-normalised model space.

    ``center`` and ``radius`` are expressed as fractions of the mesh's bounding
    box diagonal (origin at ``bbox.min``), which is what makes a stroke painted
    in the viewer land on the same surface the engine loads regardless of the
    model's units or how the two ends centre it.
    """
    center: list[float] = Field(min_length=3, max_length=3)
    radius: float = Field(gt=0.0, le=4.0)
    erase: bool = False
    strength: float = Field(default=1.0, ge=0.0, le=1.0)


class BrushRefineRequest(BaseModel):
    job_id: str
    stamps: list[BrushStampPayload] = Field(min_length=1, max_length=4000)
    reduction_percent: float = Field(default=40.0, gt=0.0, le=95.0)
    falloff: str = "smooth"  # "smooth", "linear", "hard"
    preserve_normals: bool = True
    preserve_boundaries: bool = True
    from_latest: bool = True
    """Refine the most recent optimized output when one exists; when False the
    pass always starts from the original upload."""
    client_extents: Optional[list[float]] = Field(default=None, min_length=3, max_length=3)
    """The viewer's bbox extents divided by its bbox diagonal.

    Used as a frame-agreement check: bbox normalisation already absorbs unit and
    placement differences, so extents that disagree mean an axis was permuted or
    flipped by one of the two loaders and the stroke cannot be located. Omit to
    skip the check."""


class BrushRefineResponse(BaseModel):
    job_id: str
    source: str  # "latest_output" or "original"
    original_stats: MeshStats
    optimized_stats: MeshStats
    optimized_filename: str
    optimized_format: str
    selected_vertex_count: int
    selected_face_count: int
    region_percent: float
    faces_removed: int
    reduction_percent: float
    components_refined: int
    components_total: int
    region_mode: str  # "selected_faces", "weighted_region" or "untouched"
    region_escalated: bool = False
    """The region only reduced once the importance term was dropped.

    Region confinement is unchanged either way; what this reports is that the
    painted area's importance map was too flat to choose between edges, so the
    reduction came from geometric error alone.
    """
    processing_time_seconds: float
    texture_export: Optional[TextureExportInfo] = None
    message: str


class OptimizationRecommendationResponse(BaseModel):
    job_id: str
    source: str
    recommended_preset: str
    recommended_target_faces: int
    enable_performance_mode: bool
    risk_level: str
    reasons: list[str]
