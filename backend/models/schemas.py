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


class OptimizeRequest(BaseModel):
    job_id: str
    target_faces: int = Field(gt=0)
    preset: Optional[str] = None  # "web", "mobile", "pc", "vr", "custom"
    generate_lods: bool = False
    preserve_normals: bool = True
    preserve_boundaries: bool = True
    strict_quality: bool = True
    max_deviation_percent: float = Field(default=2.0, gt=0.05, le=15.0)


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
    message: str


class JobStatus(BaseModel):
    job_id: str
    status: str  # "uploaded", "processing", "completed", "failed"
    progress: int  # 0-100
    stage: Optional[str] = None
    error: Optional[str] = None
