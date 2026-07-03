from pydantic import BaseModel, Field
from typing import Optional


class MeshStats(BaseModel):
    vertex_count: int
    face_count: int
    file_size_bytes: int
    file_size_mb: float
    has_uvs: bool
    has_normals: bool
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
    message: str


class JobStatus(BaseModel):
    job_id: str
    status: str  # "uploaded", "processing", "completed", "failed"
    progress: int  # 0-100
    stage: Optional[str] = None
    error: Optional[str] = None


class FeedbackRequest(BaseModel):
    job_id: str
    satisfied: bool
    preserve_shape: bool
    preserve_vertices: bool
    preserve_faces: bool
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    issues: Optional[list[str]] = None
    notes: Optional[str] = None


class FeedbackResponse(BaseModel):
    job_id: str
    saved: bool
    recommendations: list[str]


class TrainingSummaryResponse(BaseModel):
    total_optimization_events: int
    total_feedback_events: int
    positive_feedback: int
    negative_feedback: int
    top_negative_issues: list[str]
    suggested_focus_areas: list[str]


class TrainingBootstrapResponse(BaseModel):
    generated_at_utc: str
    training_samples_used: int
    profiles: list[dict]


class OptimizationRecommendationResponse(BaseModel):
    job_id: str
    source: str
    recommended_preset: str
    recommended_target_faces: int
    enable_performance_mode: bool
    risk_level: str
    reasons: list[str]
