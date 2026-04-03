import time
import zipfile
import io
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from ..models.schemas import (
    UploadResponse, OptimizeRequest, OptimizeResponse, JobStatus,
)
from ..services.file_handler import (
    generate_job_id, get_upload_path, get_processed_path,
    validate_extension, cleanup_job,
)
from ..services.mesh_analyzer import analyze_mesh
from ..services.mesh_optimizer import decimate_mesh, generate_lods, resolve_output_extension

router = APIRouter(prefix="/api", tags=["mesh"])

# In-memory job store (replace with Redis for production)
jobs: dict[str, dict] = {}

MAX_FILE_SIZE_MB = 50


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

    return UploadResponse(
        job_id=job_id,
        filename=file.filename,
        original_stats=stats,
        message="File uploaded and analyzed successfully",
    )


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_mesh(request: OptimizeRequest):
    job = jobs.get(request.job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    # Platform presets
    presets = {
        "web": 15000,
        "mobile": 8000,
        "pc": 40000,
        "vr": 5000,
    }

    target_faces = request.target_faces
    if request.preset and request.preset in presets:
        target_faces = presets[request.preset]

    original_stats = job["original_stats"]
    if target_faces >= original_stats.face_count:
        target_faces = int(original_stats.face_count * 0.5)

    jobs[request.job_id]["status"] = "processing"
    jobs[request.job_id]["progress"] = 10
    jobs[request.job_id]["stage"] = "Starting decimation"

    start_time = time.time()
    input_path = job["filepath"]
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
            message=message,
        )

    except Exception as e:
        jobs[request.job_id]["status"] = "failed"
        jobs[request.job_id]["stage"] = "Error"
        jobs[request.job_id]["error"] = str(e)
        raise HTTPException(500, f"Optimization failed: {str(e)}")


@router.get("/status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    return JobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        stage=job.get("stage"),
        error=job.get("error"),
    )


@router.get("/download/{job_id}")
async def download_result(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
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
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
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
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    cleanup_job(job_id)
    del jobs[job_id]
    return {"message": "Job deleted"}
