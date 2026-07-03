import json
import time
import zipfile
import io
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from ..models.schemas import (
    UploadResponse, OptimizeRequest, OptimizeResponse, JobStatus,
    FeedbackRequest, FeedbackResponse, TrainingSummaryResponse, TrainingBootstrapResponse,
    OptimizationRecommendationResponse,
    MeshStats,
)
from ..services.file_handler import (
    generate_job_id, get_upload_path, get_processed_path,
    validate_extension, cleanup_job,
)
from ..services.mesh_analyzer import analyze_mesh
from ..services.mesh_optimizer import decimate_mesh, generate_lods, resolve_output_extension
from ..services.feedback_trainer import (
    record_optimization_event,
    record_feedback_event,
    get_training_summary,
    bootstrap_preference_model,
    find_preference_profile,
)

router = APIRouter(prefix="/api", tags=["mesh"])

# In-memory job store (replace with Redis for production)
jobs: dict[str, dict] = {}

MAX_FILE_SIZE_MB = 50

PRESET_TARGETS = {
    "tiny_ui": 8000,
    "decorative_bg": 25000,
    "hero_standard": 70000,
    "interactive_model": 100000,
    "multi_scene": 220000,
    "mobile_hero": 45000,
}

JOB_META_FILENAME = "_job_meta.json"
UPLOAD_BASE_DIR = Path(__file__).resolve().parent.parent / "uploads"


def _job_meta_path(job_id: str) -> Path:
    return UPLOAD_BASE_DIR / job_id / JOB_META_FILENAME


def _serialize_job_value(value):
    if isinstance(value, dict):
        return {k: _serialize_job_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_job_value(v) for v in value]
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def _deserialize_job(payload: dict) -> dict:
    job = dict(payload)
    for key in ("original_stats", "optimized_stats"):
        stats_payload = job.get(key)
        if isinstance(stats_payload, dict):
            try:
                job[key] = MeshStats(**stats_payload)
            except Exception:
                # Keep raw payload if schema reconstruction fails.
                pass
    return job


def _save_job(job_id: str) -> None:
    job = jobs.get(job_id)
    if not job:
        return

    meta_path = _job_meta_path(job_id)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(_serialize_job_value(job), f, ensure_ascii=True)


def _recover_job_from_filesystem(job_id: str) -> dict | None:
    upload_dir = UPLOAD_BASE_DIR / job_id
    if not upload_dir.exists() or not upload_dir.is_dir():
        return None

    mesh_files = [
        p
        for p in upload_dir.iterdir()
        if p.is_file() and p.name != JOB_META_FILENAME and validate_extension(p.name)
    ]
    if not mesh_files:
        return None

    input_file = max(mesh_files, key=lambda p: p.stat().st_mtime)
    try:
        stats = analyze_mesh(input_file)
    except Exception:
        return None

    return {
        "status": "uploaded",
        "progress": 100,
        "stage": "Recovered from disk",
        "filename": input_file.name,
        "filepath": str(input_file),
        "original_stats": stats,
    }


def _get_job(job_id: str) -> dict:
    cached = jobs.get(job_id)
    if cached:
        return cached

    meta_path = _job_meta_path(job_id)
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            recovered = _deserialize_job(payload)
            jobs[job_id] = recovered
            return recovered
        except Exception:
            pass

    recovered = _recover_job_from_filesystem(job_id)
    if recovered is not None:
        jobs[job_id] = recovered
        _save_job(job_id)
        return recovered

    raise HTTPException(404, "Job not found")


def _risk_level(face_count: int) -> str:
    if face_count < 50000:
        return "safe"
    if face_count <= 150000:
        return "moderate"
    if face_count <= 500000:
        return "heavy"
    return "avoid"


def _recommend_for_stats(face_count: int, file_size_mb: float) -> tuple[str, int, bool, str, list[str]]:
    reasons: list[str] = []

    if face_count > 500000:
        preset = "mobile_hero"
        reasons.append("Very high geometry budget detected, prioritize aggressive landing-page reduction.")
    elif face_count > 300000:
        preset = "hero_standard"
        reasons.append("High geometry model detected, strong optimization recommended for smooth web FPS.")
    elif face_count > 150000:
        preset = "decorative_bg"
        reasons.append("Moderately heavy model detected, reduce to background-safe budget.")
    elif face_count > 90000:
        preset = "hero_standard"
        reasons.append("Model is above standard hero budget, target balanced hero preset.")
    elif face_count > 50000:
        preset = "interactive_model"
        reasons.append("Model fits interactive range, preserve enough detail for user interactions.")
    elif face_count > 25000:
        preset = "mobile_hero"
        reasons.append("Model is already moderate, tune for better mobile and cross-device FPS.")
    elif face_count > 10000:
        preset = "decorative_bg"
        reasons.append("Model fits decorative range, maintain lightweight rendering.")
    else:
        preset = "tiny_ui"
        reasons.append("Model is already lightweight and suitable for tiny UI elements.")

    if file_size_mb > 25:
        reasons.append("Large file size detected, enabling stronger FPS-focused recommendation.")

    target_faces = PRESET_TARGETS[preset]
    enable_performance_mode = face_count > 50000 or file_size_mb > 15
    risk_level = _risk_level(face_count)

    return preset, target_faces, enable_performance_mode, risk_level, reasons


def _preset_for_target(target_faces: int) -> str:
    closest = min(PRESET_TARGETS.items(), key=lambda item: abs(item[1] - target_faces))
    return closest[0]


@router.post("/upload", response_model=UploadResponse)
async def upload_mesh(file: UploadFile = File(...)):
    if not file.filename or not validate_extension(file.filename):
        raise HTTPException(400, "Unsupported file format. Use: .obj, .stl, .ply, .glb, .gltf, .fbx, .off")

    job_id = generate_job_id()
    upload_dir = get_upload_path(job_id)
    filepath = upload_dir / file.filename

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(413, f"File too large. Max: {MAX_FILE_SIZE_MB}MB, got: {size_mb:.1f}MB")

    with open(filepath, "wb") as f:
        f.write(content)

    try:
        stats = analyze_mesh(filepath)
    except Exception as e:
        cleanup_job(job_id)
        raise HTTPException(422, f"Could not analyze mesh: {str(e)}")

    jobs[job_id] = {
        "status": "uploaded",
        "progress": 100,
        "stage": "Upload complete",
        "filename": file.filename,
        "filepath": str(filepath),
        "original_stats": stats,
    }
    _save_job(job_id)

    return UploadResponse(
        job_id=job_id,
        filename=file.filename,
        original_stats=stats,
        message="File uploaded and analyzed successfully",
    )


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_mesh(request: OptimizeRequest):
    job = _get_job(request.job_id)

    # Platform presets
    presets = PRESET_TARGETS

    target_faces = request.target_faces
    if request.preset and request.preset in presets:
        target_faces = presets[request.preset]

    latest_stats = job.get("optimized_stats")
    base_original_stats = job.get("original_stats")

    using_latest_output = (
        request.reoptimize_from_latest
        and job.get("status") == "completed"
        and latest_stats is not None
        and job.get("output_path") is not None
    )

    source_reason = "latest_output"
    if using_latest_output and latest_stats is not None and base_original_stats is not None:
        latest_faces = latest_stats.face_count
        original_faces = base_original_stats.face_count

        # If user increases target above current optimized mesh, switch back to original source.
        # This allows recovering detail budget between current output and original model.
        if target_faces > latest_faces and target_faces < original_faces:
            using_latest_output = False
            source_reason = "fallback_to_original_for_face_increase"
        elif target_faces >= original_faces:
            using_latest_output = False
            source_reason = "fallback_to_original_for_high_target"

    source_stats = job.get("optimized_stats") if using_latest_output else job["original_stats"]
    original_stats = source_stats

    jobs[request.job_id]["status"] = "processing"
    jobs[request.job_id]["progress"] = 10
    jobs[request.job_id]["stage"] = "Starting decimation"

    start_time = time.time()
    input_path = job["output_path"] if using_latest_output else job["filepath"]
    output_dir = get_processed_path(request.job_id)
    base_name = Path(input_path).stem
    input_ext = Path(input_path).suffix.lower()
    output_ext = resolve_output_extension(input_ext)
    output_filename = f"{base_name}_optimized{output_ext}"
    output_path = output_dir / output_filename

    try:
        jobs[request.job_id]["progress"] = 30
        jobs[request.job_id]["stage"] = "Decimating mesh"

        optimized_stats, quality_meta = decimate_mesh(
            input_path=input_path,
            output_path=output_path,
            target_faces=target_faces,
            preserve_normals=request.preserve_normals,
            preserve_boundaries=request.preserve_boundaries,
            strict_quality=request.strict_quality,
            max_deviation_percent=request.max_deviation_percent,
            max_target_overshoot_percent=request.max_target_overshoot_percent,
        )

        lod_results = None
        if request.generate_lods:
            jobs[request.job_id]["progress"] = 60
            jobs[request.job_id]["stage"] = "Generating LODs"
            lod_results = generate_lods(
                input_path=input_path,
                output_dir=output_dir,
                base_name=base_name,
                original_faces=original_stats.face_count,
                output_extension=output_ext,
                preserve_normals=request.preserve_normals,
                preserve_boundaries=request.preserve_boundaries,
            )

        processing_time = round(time.time() - start_time, 2)
        reduction = 0.0
        if original_stats.face_count > 0:
            reduction = round((1 - optimized_stats.face_count / original_stats.face_count) * 100, 1)
        format_was_converted = output_ext != input_ext

        jobs[request.job_id]["status"] = "completed"
        jobs[request.job_id]["progress"] = 100
        jobs[request.job_id]["stage"] = "Complete"
        jobs[request.job_id]["optimized_stats"] = optimized_stats
        jobs[request.job_id]["output_path"] = str(output_path)
        jobs[request.job_id]["optimized_filename"] = output_filename
        jobs[request.job_id]["optimized_format"] = output_ext.lstrip(".")
        jobs[request.job_id]["format_was_converted"] = format_was_converted
        jobs[request.job_id]["target_faces_used"] = quality_meta.get("target_faces_used")
        jobs[request.job_id]["quality_deviation_percent"] = quality_meta.get("quality_deviation_percent")
        jobs[request.job_id]["quality_guard_relaxed"] = quality_meta.get("quality_guard_relaxed", False)
        jobs[request.job_id]["quality_guard_satisfied"] = quality_meta.get("quality_guard_satisfied", True)
        jobs[request.job_id]["optimize_request"] = request.model_dump()
        jobs[request.job_id]["reduction_percent"] = reduction
        jobs[request.job_id]["processing_time_seconds"] = processing_time
        jobs[request.job_id]["source_reason"] = source_reason
        jobs[request.job_id]["has_importance_map"] = quality_meta.get("importance_scores") is not None
        if quality_meta.get("importance_scores") is not None:
            jobs[request.job_id]["importance_scores"] = quality_meta["importance_scores"]
        _save_job(request.job_id)

        record_optimization_event(
            job_id=request.job_id,
            original_stats=original_stats.model_dump(),
            optimized_stats=optimized_stats.model_dump(),
            request_payload=request.model_dump(),
            quality_meta=quality_meta,
            processing_time_seconds=processing_time,
            reduction_percent=reduction,
        )

        message = (
            f"Mesh optimized: {original_stats.face_count:,} -> {optimized_stats.face_count:,} faces ({reduction}% reduction)"
        )
        if request.strict_quality:
            quality_deviation = quality_meta.get("quality_deviation_percent")
            if quality_meta.get("quality_guard_relaxed"):
                message += (
                    " | Quality lock adjusted target to preserve structure"
                )
            if quality_deviation is not None:
                message += f" | deviation={quality_deviation}%"
            if not quality_meta.get("quality_guard_satisfied", True):
                message += " | requested reduction was too aggressive for strict quality"

        if format_was_converted:
            message += f". Output converted from {input_ext or 'unknown'} to {output_ext} for compatibility"

        if source_reason == "fallback_to_original_for_face_increase":
            message += " | face target increased above latest output, so optimization restarted from original mesh"
        elif source_reason == "fallback_to_original_for_high_target":
            message += " | face target is near original budget, so optimization used original mesh"

        return OptimizeResponse(
            job_id=request.job_id,
            original_stats=original_stats,
            optimized_stats=optimized_stats,
            optimized_filename=output_filename,
            optimized_format=output_ext.lstrip("."),
            format_was_converted=format_was_converted,
            target_faces_used=quality_meta.get("target_faces_used"),
            quality_deviation_percent=quality_meta.get("quality_deviation_percent"),
            quality_guard_relaxed=quality_meta.get("quality_guard_relaxed", False),
            quality_guard_satisfied=quality_meta.get("quality_guard_satisfied", True),
            lods=lod_results,
            reduction_percent=reduction,
            processing_time_seconds=processing_time,
            has_importance_map=quality_meta.get("importance_scores") is not None,
            message=message,
        )

    except Exception as e:
        jobs[request.job_id]["status"] = "failed"
        jobs[request.job_id]["stage"] = "Error"
        jobs[request.job_id]["error"] = str(e)
        _save_job(request.job_id)
        raise HTTPException(422, f"Optimization failed: {str(e)}")


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest):
    job = _get_job(request.job_id)
    if job.get("status") != "completed":
        raise HTTPException(400, "Feedback can be submitted after optimization completes")

    optimization_snapshot = {
        "optimize_request": job.get("optimize_request"),
        "original_stats": job.get("original_stats").model_dump() if job.get("original_stats") else None,
        "optimized_stats": job.get("optimized_stats").model_dump() if job.get("optimized_stats") else None,
        "reduction_percent": job.get("reduction_percent"),
        "processing_time_seconds": job.get("processing_time_seconds"),
        "quality_guard_relaxed": job.get("quality_guard_relaxed"),
        "quality_guard_satisfied": job.get("quality_guard_satisfied"),
    }

    recommendations = record_feedback_event(
        feedback=request,
        optimization_snapshot=optimization_snapshot,
    )

    return FeedbackResponse(
        job_id=request.job_id,
        saved=True,
        recommendations=recommendations,
    )


@router.get("/training/summary", response_model=TrainingSummaryResponse)
async def training_summary():
    return TrainingSummaryResponse(**get_training_summary())


@router.post("/training/bootstrap", response_model=TrainingBootstrapResponse)
async def training_bootstrap():
    return TrainingBootstrapResponse(**bootstrap_preference_model())


@router.get("/recommend/{job_id}", response_model=OptimizationRecommendationResponse)
async def recommend_optimization(job_id: str, from_latest: bool = False):
    job = _get_job(job_id)

    use_latest = bool(from_latest and job.get("optimized_stats") is not None)
    stats = job.get("optimized_stats") if use_latest else job.get("original_stats")
    if stats is None:
        raise HTTPException(400, "No mesh stats available for recommendation")

    optimize_request = job.get("optimize_request") or {}
    desired_output = optimize_request.get("desired_output") or {}
    use_case = desired_output.get("use_case") or "general"
    quality_priority = desired_output.get("quality_priority") or "balanced"

    profile = find_preference_profile(use_case=use_case, quality_priority=quality_priority)
    if profile and int(profile.get("sample_count", 0)) > 0:
        learned_target = int(profile.get("recommended_target_faces", PRESET_TARGETS["hero_standard"]))
        learned_target = max(8000, min(learned_target, max(stats.face_count - 1, 8000)))
        preset = _preset_for_target(learned_target)
        target_faces = learned_target
        performance_mode = stats.face_count > 50000 or stats.file_size_mb > 15
        risk_level = _risk_level(stats.face_count)
        reasons = [
            (
                f"Learned from positive feedback profile: "
                f"{profile.get('use_case', 'general')} / {profile.get('quality_priority', 'balanced')} "
                f"(samples={profile.get('sample_count', 0)})."
            ),
            "Recommendation adapted from saved user-approved outputs.",
        ]
    else:
        preset, target_faces, performance_mode, risk_level, reasons = _recommend_for_stats(
            face_count=stats.face_count,
            file_size_mb=stats.file_size_mb,
        )

    source = "optimized" if use_latest else "original"
    return OptimizationRecommendationResponse(
        job_id=job_id,
        source=source,
        recommended_preset=preset,
        recommended_target_faces=target_faces,
        enable_performance_mode=performance_mode,
        risk_level=risk_level,
        reasons=reasons,
    )


@router.get("/status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    job = _get_job(job_id)

    return JobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        stage=job.get("stage"),
        error=job.get("error"),
    )


class ImportanceResponse(BaseModel):
    scores: list[float]
    vertex_count: int


@router.get("/importance/{job_id}", response_model=ImportanceResponse)
async def get_importance_map(job_id: str):
    job = _get_job(job_id)
    scores = job.get("importance_scores")
    if scores is None:
        raise HTTPException(404, "No importance map available for this job")
    return ImportanceResponse(scores=scores, vertex_count=len(scores))


@router.get("/download/{job_id}")
async def download_result(job_id: str):
    job = _get_job(job_id)
    if job["status"] != "completed":
        raise HTTPException(400, "Job not yet completed")

    output_dir = get_processed_path(job_id)
    files = sorted(output_dir.iterdir())

    if not files:
        raise HTTPException(404, "No output files found")

    if len(files) == 1:
        return FileResponse(
            path=str(files[0]),
            filename=files[0].name,
            media_type="application/octet-stream",
        )

    # Multiple files (LODs) — zip them
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, f.name)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=optimesh_{job_id}.zip"},
    )


@router.get("/preview/{job_id}")
async def preview_result(job_id: str):
    job = _get_job(job_id)
    if job["status"] != "completed":
        raise HTTPException(400, "Job not yet completed")

    output_path = job.get("output_path")
    if not output_path:
        raise HTTPException(404, "No optimized mesh found")

    file_path = Path(output_path)
    if not file_path.exists():
        raise HTTPException(404, "No optimized mesh found")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@router.delete("/job/{job_id}")
async def delete_job(job_id: str):
    _get_job(job_id)
    cleanup_job(job_id)
    jobs.pop(job_id, None)
    return {"message": "Job deleted"}
