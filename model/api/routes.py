import json
import time
import zipfile
import io
import re
import logging
import asyncio
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .schemas import (
    UploadResponse, OptimizeRequest, OptimizeResponse, JobStatus,
    OptimizationRecommendationResponse,
    MeshStats, EdgeFeatureStat, EdgeFeatureSummary,
    BrushRefineRequest, BrushRefineResponse,
)
from ..services.file_handler import (
    generate_job_id, get_upload_path, get_processed_path,
    validate_extension, cleanup_job,
)
from ..services import cloud_storage as storage
from ..services.download_quota import (
    get_quota, can_download, consume_download, prune as _prune_downloads,
)
from ..services.mesh_analyzer import analyze_mesh
from ..engine.mesh_optimizer import decimate_mesh, generate_lods, resolve_output_extension
from ..services.optimization_events import record_optimization_event
from ..learning.continuous_learning import learning_status, retrain_now
from ..importance.edge_features import FEATURE_METADATA, FEATURE_WEIGHTS

router = APIRouter(prefix="/api", tags=["mesh"])

logger = logging.getLogger(__name__)

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


def _client_id(request: Request) -> str:
    """Anonymous device id from X-Client-Id, falling back to the IP."""
    header = request.headers.get("x-client-id", "").strip()
    if header and len(header) <= 128:
        return header
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


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

    # Mirror the meta to durable cloud storage so jobs survive restarts
    # even when the local disk is ephemeral.
    if storage.is_enabled():
        try:
            with open(meta_path, "rb") as f:
                mirrored = storage.upload_bytes(storage.key_meta(job_id), f.read())
        except Exception as exc:
            mirrored = False
        if not mirrored:
            logger.error(
                "Failed to mirror job meta to cloud storage for job %s", job_id
            )


def _recover_job_from_filesystem(job_id: str) -> dict | None:
    upload_dir = UPLOAD_BASE_DIR / job_id
    if not upload_dir.exists() or not upload_dir.is_dir():
        upload_dir.mkdir(parents=True, exist_ok=True)

    mesh_files = [
        p
        for p in upload_dir.iterdir()
        if p.is_file() and p.name != JOB_META_FILENAME and validate_extension(p.name)
    ]

    # Local disk was empty (fresh container?) — pull the mesh from cloud.
    if not mesh_files and storage.is_enabled():
        for key in storage.list_prefix(f"{storage.UPLOADS_PREFIX}/{job_id}"):
            name = Path(key).name
            if not validate_extension(name):
                continue
            if storage.download_file(key, upload_dir / name):
                mesh_files.append(upload_dir / name)

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
    if not meta_path.exists() and storage.is_enabled():
        storage.download_file(storage.key_meta(job_id), meta_path)
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


def _build_edge_feature_summary(raw: dict | None) -> EdgeFeatureSummary | None:
    """Attach label/group/description/weight to the optimizer's raw cue stats.

    The optimizer only reports numbers; the presentation metadata lives in
    ``edge_features`` so the API and UI stay in step with the cue definitions.
    Unknown keys are skipped rather than guessed at, so adding a cue to the
    engine without describing it degrades to omission instead of a 500.
    """
    if not raw:
        return None

    stats: list[EdgeFeatureStat] = []
    for item in raw.get("features", []):
        key = item.get("name")
        meta = FEATURE_METADATA.get(key)
        if meta is None:
            logger.warning("Edge cue %r has no presentation metadata; omitting", key)
            continue
        stats.append(EdgeFeatureStat(
            key=key,
            label=meta["label"],
            group=meta["group"],
            description=meta["description"],
            present=bool(item.get("present", False)),
            weight=float(FEATURE_WEIGHTS.get(key, 0.0)),
            min=float(item.get("min", 0.0)),
            max=float(item.get("max", 0.0)),
            mean=float(item.get("mean", 0.0)),
        ))

    return EdgeFeatureSummary(
        enabled=bool(raw.get("enabled", False)),
        edge_count=int(raw.get("edge_count", 0)),
        features=stats,
    )


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


@router.post("/upload", response_model=UploadResponse)
async def upload_model(file: UploadFile = File(...)):
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

    # Raw upload must be durable in the bucket in cloud mode — the local
    # copy is only a working cache.
    if not storage.upload_file(storage.key_upload(job_id, file.filename), filepath):
        if storage.is_enabled():
            cleanup_job(job_id)
            raise HTTPException(
                500, f"Failed to store upload in cloud storage (job {job_id})"
            )

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


def _run_decimation(
    input_path: str,
    output_path: str,
    target_faces: int,
    preserve_normals: bool,
    preserve_boundaries: bool,
    strict_quality: bool,
    max_deviation_percent: float,
    max_target_overshoot_percent: float,
    generate_lods: bool,
    out_dir: str,
    base_name: str,
    out_ext: str,
    original_faces: int,
    job_id: str | None,
) -> tuple:
    from ..engine.mesh_optimizer import decimate_mesh, generate_lods as _gen_lods
    optimized_stats, quality_meta = decimate_mesh(
        input_path=input_path,
        output_path=output_path,
        target_faces=target_faces,
        preserve_normals=preserve_normals,
        preserve_boundaries=preserve_boundaries,
        strict_quality=strict_quality,
        max_deviation_percent=max_deviation_percent,
        max_target_overshoot_percent=max_target_overshoot_percent,
        job_id=job_id,
    )
    lod_results = None
    if generate_lods:
        lod_results = _gen_lods(
            input_path=input_path,
            output_dir=out_dir,
            base_name=base_name,
            original_faces=original_faces,
            output_extension=out_ext,
            preserve_normals=preserve_normals,
            preserve_boundaries=preserve_boundaries,
        )
    return optimized_stats, quality_meta, lod_results


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
    input_path = Path(job["output_path"] if using_latest_output else job["filepath"])
    if storage.is_enabled() and not input_path.exists():
        # Local working cache was cleared (restart / ephemeral disk) — the
        # durable copy lives in the bucket, so pull it back for processing.
        input_key = (
            storage.key_processed(request.job_id, input_path.name)
            if using_latest_output
            else storage.key_upload(request.job_id, input_path.name)
        )
        if not storage.download_file(input_key, input_path):
            raise HTTPException(500, "Input mesh is unavailable in cloud storage")
    output_dir = get_processed_path(request.job_id)
    base_name = input_path.stem
    input_ext = input_path.suffix.lower()
    output_ext = resolve_output_extension(input_ext)
    output_filename = f"{base_name}_optimized{output_ext}"
    output_path = output_dir / output_filename

    try:
        import functools
        loop = asyncio.get_running_loop()

        # Run the synchronous decimation in a thread pool to avoid blocking the event loop.
        # This also isolates any segfault-prone C++ library crashes to the thread.
        logger.info("Starting inline decimation (thread pool)")

        from .schemas import TextureExportInfo

        from concurrent.futures import ProcessPoolExecutor
        import multiprocessing
        with ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context('spawn')) as executor:
            optimized_stats, quality_meta, lod_results = await loop.run_in_executor(
                executor,
            functools.partial(
                _run_decimation,
                input_path=str(input_path),
                output_path=str(output_path),
                target_faces=target_faces,
                preserve_normals=request.preserve_normals,
                preserve_boundaries=request.preserve_boundaries,
                strict_quality=request.strict_quality,
                max_deviation_percent=request.max_deviation_percent,
                max_target_overshoot_percent=request.max_target_overshoot_percent,
                generate_lods=request.generate_lods,
                out_dir=str(output_dir),
                base_name=base_name,
                out_ext=output_ext,
                original_faces=original_stats.face_count,
                job_id=request.job_id,
            ),
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
        jobs[request.job_id]["edge_features"] = quality_meta.get("edge_features")

        texture_export_info = quality_meta.get("texture_export_info")
        if texture_export_info is not None:
            jobs[request.job_id]["texture_export"] = texture_export_info
        jobs[request.job_id]["original_has_textures"] = quality_meta.get("original_has_textures", False)
        jobs[request.job_id]["original_has_animation"] = quality_meta.get("original_has_animation", False)
        _save_job(request.job_id)

        # Processed outputs + LODs become durable in the bucket.  In cloud
        # mode every produced file must reach the bucket — the local disk is
        # only a working cache.
        processed_dir = get_processed_path(request.job_id)
        missing_uploads: list[str] = []
        for f in processed_dir.iterdir():
            if f.is_file():
                if not storage.upload_file(storage.key_processed(request.job_id, f.name), f):
                    missing_uploads.append(f.name)
        if storage.is_enabled() and missing_uploads:
            raise RuntimeError(
                f"Failed to upload processed outputs to cloud storage: {missing_uploads}"
            )

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
                message += " | Quality lock adjusted target to preserve structure"
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

        texture_export_info = quality_meta.get("texture_export_info")
        if isinstance(texture_export_info, dict):
            texture_export_info = TextureExportInfo(**texture_export_info)

        has_uv_density = bool(
            quality_meta.get("original_has_textures", False)
            and quality_meta.get("importance_scores") is not None
        )

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
            has_uv_density_map=has_uv_density,
            has_animation_map=quality_meta.get("original_has_animation", False),
            is_animated=quality_meta.get("original_has_animation", False),
            texture_export=texture_export_info,
            edge_features=_build_edge_feature_summary(quality_meta.get("edge_features")),
            message=message,
        )

    except Exception as e:
        import traceback as _tb
        tb_str = _tb.format_exc()
        error_detail = str(e) or tb_str or "Unknown error (empty exception)"
        logger.error(f"Optimization failed: {error_detail}")
        jobs[request.job_id]["status"] = "failed"
        jobs[request.job_id]["stage"] = "Error"
        jobs[request.job_id]["error"] = error_detail
        _save_job(request.job_id)
        raise HTTPException(422, f"Optimization failed: {error_detail}")


@router.get("/recommend/{job_id}", response_model=OptimizationRecommendationResponse)
async def recommend_optimization(job_id: str, from_latest: bool = False):
    job = _get_job(job_id)

    use_latest = bool(from_latest and job.get("optimized_stats") is not None)
    stats = job.get("optimized_stats") if use_latest else job.get("original_stats")
    if stats is None:
        raise HTTPException(400, "No mesh stats available for recommendation")

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


# ---------------------------------------------------------------------------
# Refactor brush — region-local optimization
# ---------------------------------------------------------------------------

def _run_brush_refine(
    input_path: str,
    output_path: str,
    stamps_payload: list[dict],
    reduction_percent: float,
    falloff: str,
    preserve_normals: bool,
    preserve_boundaries: bool,
    client_extents: list[float] | None,
) -> tuple:
    """Process-pool entry point for the brush pass (must stay importable)."""
    from ..engine.brush_refine import refine_region
    from ..engine.brush_selection import stamps_from_payload

    return refine_region(
        input_path=input_path,
        output_path=output_path,
        stamps=stamps_from_payload(stamps_payload),
        reduction_percent=reduction_percent,
        falloff=falloff,
        preserve_normals=preserve_normals,
        preserve_boundaries=preserve_boundaries,
        client_extents=client_extents,
    )


_REFINED_SUFFIX = re.compile(r"_refined(\d*)$")


def _next_refined_stem(stem: str) -> str:
    """``foo`` -> ``foo_refined`` -> ``foo_refined2`` -> ``foo_refined3`` ...

    Chained brush passes read the previous pass's output, so appending a fresh
    suffix each time would grow ``foo_refined_refined_refined`` without bound.
    Counting instead keeps the name readable and, unlike reusing the same name,
    still writes to a different file than the one being read — a failed export
    can never leave the job with no mesh at all.
    """
    match = _REFINED_SUFFIX.search(stem)
    if match is None:
        return f"{stem}_refined"
    n = int(match.group(1)) if match.group(1) else 1
    return f"{stem[:match.start()]}_refined{n + 1}"


def _discard_superseded_output(job_id: str, path: Path, keep: Path) -> None:
    """Delete a processed mesh (and its sidecars) that a brush pass replaced.

    Only ever called for files the pass itself read out of ``processed/``, and
    never for *keep* — the output just written.  Keeping the directory to a
    single current mesh matters because ``/download`` zips everything it finds
    there, so a stale intermediate would end up in the user's archive.
    """
    stale = [
        f for f in path.parent.glob(f"{path.stem}.*")
        if f.is_file() and f.resolve() != keep.resolve()
    ]
    for f in stale:
        try:
            f.unlink()
        except OSError as exc:
            logger.warning("Could not remove superseded output %s: %s", f.name, exc)

    if stale and storage.is_enabled():
        storage.delete_objects([storage.key_processed(job_id, f.name) for f in stale])


@router.post("/brush/refine", response_model=BrushRefineResponse)
async def brush_refine(request: BrushRefineRequest):
    """Optimize only the region the user painted with the refactor brush.

    An add-on to ``/optimize`` rather than a variant of it: the whole-model
    budget pass is untouched, and this endpoint exists for the case it cannot
    serve — a patch the importance map left denser than the user wanted.  On
    failure the job keeps the output it already had, so a missed stroke costs
    nothing but the request.
    """
    from ..engine.brush_refine import BrushSelectionError
    from .schemas import TextureExportInfo

    job = _get_job(request.job_id)
    base_original_stats = job.get("original_stats")
    if base_original_stats is None:
        raise HTTPException(400, "Job has no analyzed source mesh")

    latest_stats = job.get("optimized_stats")
    using_latest = bool(
        request.from_latest
        and job.get("status") == "completed"
        and latest_stats is not None
        and job.get("output_path") is not None
    )
    source_stats = latest_stats if using_latest else base_original_stats

    input_path = Path(job["output_path"] if using_latest else job["filepath"])
    if storage.is_enabled() and not input_path.exists():
        input_key = (
            storage.key_processed(request.job_id, input_path.name)
            if using_latest
            else storage.key_upload(request.job_id, input_path.name)
        )
        if not storage.download_file(input_key, input_path):
            raise HTTPException(500, "Input mesh is unavailable in cloud storage")
    if not input_path.exists():
        raise HTTPException(404, "Input mesh for this job is no longer available")

    output_dir = get_processed_path(request.job_id)
    output_ext = resolve_output_extension(input_path.suffix.lower())
    output_filename = f"{_next_refined_stem(input_path.stem)}{output_ext}"
    output_path = output_dir / output_filename

    start_time = time.time()
    try:
        import functools
        from concurrent.futures import ProcessPoolExecutor
        import multiprocessing

        loop = asyncio.get_running_loop()
        with ProcessPoolExecutor(
            max_workers=1, mp_context=multiprocessing.get_context("spawn")
        ) as executor:
            refined_stats, meta = await loop.run_in_executor(
                executor,
                functools.partial(
                    _run_brush_refine,
                    input_path=str(input_path),
                    output_path=str(output_path),
                    stamps_payload=[s.model_dump() for s in request.stamps],
                    reduction_percent=request.reduction_percent,
                    falloff=request.falloff,
                    preserve_normals=request.preserve_normals,
                    preserve_boundaries=request.preserve_boundaries,
                    client_extents=request.client_extents,
                ),
            )
    except BrushSelectionError as exc:
        # The selection itself was the problem — nothing was written and the
        # job still points at its previous output.
        raise HTTPException(422, str(exc))
    except Exception as exc:
        import traceback as _tb

        detail = str(exc) or _tb.format_exc() or "Unknown error"
        logger.error("Brush refine failed for job %s: %s", request.job_id, detail)
        raise HTTPException(422, f"Brush refine failed: {detail}")

    processing_time = round(time.time() - start_time, 2)

    if using_latest:
        _discard_superseded_output(request.job_id, input_path, output_path)

    reduction = 0.0
    if base_original_stats.face_count > 0:
        reduction = round(
            (1 - refined_stats.face_count / base_original_stats.face_count) * 100, 1
        )

    jobs[request.job_id] = job
    job["status"] = "completed"
    job["progress"] = 100
    job["stage"] = "Brush refine complete"
    job["optimized_stats"] = refined_stats
    job["output_path"] = str(output_path)
    job["optimized_filename"] = output_filename
    job["optimized_format"] = output_ext.lstrip(".")
    job["reduction_percent"] = reduction
    job["processing_time_seconds"] = processing_time
    job["brush_refine"] = {
        "selected_vertex_count": meta["selected_vertex_count"],
        "selected_face_count": meta["selected_face_count"],
        "region_percent": meta["region_percent"],
        "faces_removed": meta["faces_removed"],
        "region_mode": meta["region_mode"],
        "region_escalated": meta.get("region_escalated", False),
        "reduction_percent_requested": meta["reduction_percent_requested"],
    }
    texture_export_info = meta.get("texture_export_info")
    if texture_export_info is not None:
        job["texture_export"] = texture_export_info
    # Keep heatmap live after brush — original's importance is still valid for
    # originalUrl (ModelViewer shows original when importanceEnabled). Don't drop.
    _save_job(request.job_id)

    missing_uploads: list[str] = []
    for f in output_dir.iterdir():
        if f.is_file():
            if not storage.upload_file(storage.key_processed(request.job_id, f.name), f):
                missing_uploads.append(f.name)
    if storage.is_enabled() and missing_uploads:
        raise HTTPException(
            500, f"Failed to upload refined output to cloud storage: {missing_uploads}"
        )

    if isinstance(texture_export_info, dict):
        texture_export_info = TextureExportInfo(**texture_export_info)

    message = (
        f"Refined {meta['selected_face_count']:,} painted faces "
        f"({meta['region_percent']}% of the mesh): "
        f"{meta['faces_before']:,} -> {meta['faces_after']:,} faces, "
        f"{meta['faces_removed']:,} removed"
    )
    if meta["region_mode"] == "weighted_region":
        message += " | region selection unavailable, used importance weighting only"
    if meta.get("region_escalated"):
        message += " | region importance was uniform, reduced on geometric error"
    if meta["components_refined"] < meta["components_total"]:
        untouched = meta["components_total"] - meta["components_refined"]
        message += f" | {untouched} unpainted part(s) left untouched"

    return BrushRefineResponse(
        job_id=request.job_id,
        source="latest_output" if using_latest else "original",
        original_stats=source_stats,
        optimized_stats=refined_stats,
        optimized_filename=output_filename,
        optimized_format=output_ext.lstrip("."),
        selected_vertex_count=meta["selected_vertex_count"],
        selected_face_count=meta["selected_face_count"],
        region_percent=meta["region_percent"],
        faces_removed=meta["faces_removed"],
        reduction_percent=reduction,
        components_refined=meta["components_refined"],
        components_total=meta["components_total"],
        region_mode=meta["region_mode"],
        region_escalated=bool(meta.get("region_escalated", False)),
        processing_time_seconds=processing_time,
        texture_export=texture_export_info,
        message=message,
    )


def _stream_from_cloud(job_id: str) -> StreamingResponse | None:
    """Stream a processed job directly from the bucket (mirrors local logic)."""
    if not storage.is_enabled():
        return None

    keys = storage.list_prefix(f"{storage.PROCESSED_PREFIX}/{job_id}")
    if not keys:
        return None
    keys = sorted(keys)

    if len(keys) == 1:
        reader = storage.open_stream(keys[0])
        if reader is None:
            return None
        body, size = reader
        return StreamingResponse(
            body,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={Path(keys[0]).name}",
                "Content-Length": str(size),
            },
        )

    # Multiple files (LODs) — zip them
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for key in keys:
            data = storage.read_bytes(key)
            if data is not None:
                zf.writestr(Path(key).name, data)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=optimesh_{job_id}.zip",
            "Content-Length": str(buffer.getbuffer().nbytes),
        },
    )


@router.get("/download/quota")
async def download_quota(request: Request):
    """Remaining daily downloads for the calling client."""
    client_id = _client_id(request)
    _prune_downloads()
    return get_quota(client_id)


@router.get("/download/{job_id}")
async def download_result(job_id: str, request: Request):
    job = _get_job(job_id)
    if job["status"] != "completed":
        raise HTTPException(400, "Job not yet completed")

    client_id = _client_id(request)
    if not can_download(client_id):
        quota = get_quota(client_id)
        raise HTTPException(
            429,
            "Daily download limit reached. You can download up to "
            f"{quota['daily_limit']} optimized models per 24h — the window "
            "resets automatically.",
            headers={
                "X-RateLimit-Limit": str(quota["daily_limit"]),
                "X-RateLimit-Remaining": "0",
                "Retry-After": str(quota["resets_in_seconds"]),
            },
        )

    # Cloud mode: the bucket is the only store that matters — downloads
    # always stream from it, never from the (ephemeral) local disk.
    if storage.is_enabled():
        cloud_keys = storage.list_prefix(f"{storage.PROCESSED_PREFIX}/{job_id}")
        if not cloud_keys:
            raise HTTPException(404, "No output files found")
        _prune_downloads()
        consume_download(client_id, job_id)
        response = _stream_from_cloud(job_id)
        if response is not None:
            return response
        raise HTTPException(404, "No output files found")

    output_dir = get_processed_path(job_id)
    files = sorted(output_dir.iterdir()) if output_dir.exists() else []

    if not files:
        raise HTTPException(404, "No output files found")

    if len(files) == 1:
        _prune_downloads()
        consume_download(client_id, job_id)
        quota = get_quota(client_id)
        return FileResponse(
            path=str(files[0]),
            filename=files[0].name,
            media_type="application/octet-stream",
            headers={
                "X-RateLimit-Remaining": str(quota["downloads_remaining"]),
                "X-RateLimit-Limit": str(quota["daily_limit"]),
            },
        )

    # Multiple files (LODs) — zip them
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, f.name)
    buffer.seek(0)

    _prune_downloads()
    consume_download(client_id, job_id)
    quota = get_quota(client_id)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=optimesh_{job_id}.zip",
            "X-RateLimit-Remaining": str(quota["downloads_remaining"]),
            "X-RateLimit-Limit": str(quota["daily_limit"]),
        },
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

    # Cloud mode: previews always stream from the bucket.
    if storage.is_enabled():
        reader = storage.open_stream(storage.key_processed(job_id, file_path.name))
        if reader is not None:
            body, size = reader
            return StreamingResponse(
                body,
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": f"attachment; filename={file_path.name}",
                    "Content-Length": str(size),
                },
            )
        raise HTTPException(404, "No optimized mesh found in cloud storage")

    if file_path.exists():
        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type="application/octet-stream",
        )

    raise HTTPException(404, "No optimized mesh found")


@router.delete("/job/{job_id}")
async def delete_job(job_id: str):
    _get_job(job_id)
    cleanup_job(job_id)
    jobs.pop(job_id, None)
    # Remove cloud copies too
    if storage.is_enabled():
        storage.delete_prefix(f"{storage.UPLOADS_PREFIX}/{job_id}")
        storage.delete_prefix(f"{storage.PROCESSED_PREFIX}/{job_id}")
        storage.delete_prefix(f"{storage.META_PREFIX}/{job_id}")
    return {"message": "Job deleted"}


class LearningStatusResponse(BaseModel):
    enabled: bool
    dataset_size: int
    samples_recorded: int
    seed_generated: int
    last_trained_at: Optional[float] = None
    checkpoint_exists: bool
    checkpoint_modified_at: Optional[float] = None
    min_new_samples_before_retrain: int
    retrain_interval_seconds: int
    last_error: Optional[str] = None


@router.get("/learning/status", response_model=LearningStatusResponse)
async def get_learning_status():
    """Snapshot of the self-learning subsystem (dataset size, last retrain)."""
    return LearningStatusResponse(**learning_status())


@router.post("/learning/retrain")
async def trigger_retrain(epochs: Optional[int] = None):
    """Manually trigger one fine-tuning pass of the GNN on the dataset."""
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: retrain_now(max_epochs=epochs))
    if not result.get("ok"):
        raise HTTPException(422, result.get("error", "Retrain failed"))
    return result
