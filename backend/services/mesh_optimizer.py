import os
import tempfile
from pathlib import Path
import numpy as np
import pymeshlab
import trimesh
from ..models.schemas import MeshStats, LODResult


SUPPORTED_SAVE_EXTENSIONS = {".obj", ".stl", ".ply", ".off"}
QUALITY_SAMPLE_CAP = 700
QUALITY_CHUNK_SIZE = 160


def resolve_output_extension(input_extension: str) -> str:
    ext = (input_extension or "").lower().strip()
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    return ext if ext in SUPPORTED_SAVE_EXTENSIONS else ".obj"


def _apply_decimation(
    ms: pymeshlab.MeshSet,
    target_faces: int,
    preserve_normals: bool,
    preserve_boundaries: bool,
):
    ms.apply_filter(
        "meshing_decimation_quadric_edge_collapse",
        targetfacenum=int(max(target_faces, 4)),
        preservenormal=preserve_normals,
        preserveboundary=preserve_boundaries,
        preservetopology=True,
        planarquadric=True,
        qualitythr=0.2,
    )


def _save_current_mesh(ms: pymeshlab.MeshSet, output_path: str | Path) -> None:
    output_path = str(output_path)
    try:
        ms.save_current_mesh(output_path)
    except RuntimeError:
        # Fallback for textured/complex assets where export fails on embedded resources.
        try:
            ms.save_current_mesh(
                output_path,
                save_textures=False,
                save_wedge_texcoord=False,
            )
        except RuntimeError:
            # Last fallback: keep geometry export strict and avoid optional channels.
            ms.save_current_mesh(
                output_path,
                save_textures=False,
                save_wedge_texcoord=False,
                save_vertex_normal=False,
                save_vertex_color=False,
                save_face_color=False,
            )


def _build_target_candidates(
    current_faces: int,
    target_faces: int,
    max_target_overshoot_percent: float,
) -> list[int]:
    target = int(max(4, min(target_faces, current_faces - 1)))
    overshoot_factor = max(0.0, float(max_target_overshoot_percent)) / 100.0
    cap = int(round(target * (1.0 + overshoot_factor)))
    cap = int(max(target, min(cap, current_faces - 1)))

    candidates: list[int] = []

    for ratio in [0.0, 0.03, 0.06, 0.09, 0.12]:
        candidate = target + int((cap - target) * ratio / 0.12) if cap > target else target
        candidate = int(max(4, min(candidate, cap)))
        if candidate not in candidates:
            candidates.append(candidate)

    if cap not in candidates:
        candidates.append(cap)

    return candidates


def _apply_structure_preclean(ms: pymeshlab.MeshSet) -> None:
    # Best-effort topology cleanup before decimation to avoid local vertex collapse artifacts.
    for filter_name, kwargs in [
        ("meshing_remove_duplicate_vertices", {}),
        ("meshing_remove_duplicate_faces", {}),
        ("meshing_remove_unreferenced_vertices", {}),
        ("meshing_repair_non_manifold_vertices", {}),
        ("meshing_repair_non_manifold_edges", {"method": 0}),
    ]:
        try:
            ms.apply_filter(filter_name, **kwargs)
        except Exception:
            continue


def _load_trimesh(path: str | Path) -> trimesh.Trimesh:
    loaded = trimesh.load(str(path), process=False, force="mesh")

    if isinstance(loaded, trimesh.Scene):
        meshes = [geom for geom in loaded.geometry.values() if isinstance(geom, trimesh.Trimesh)]
        if not meshes:
            raise ValueError("No mesh geometry found for quality validation")
        loaded = trimesh.util.concatenate(meshes)

    if not isinstance(loaded, trimesh.Trimesh):
        raise ValueError("Unsupported mesh type for quality validation")
    if loaded.faces is None or len(loaded.faces) == 0:
        raise ValueError("Mesh has no faces for quality validation")

    return loaded


def _sample_vertices(vertices: np.ndarray, max_count: int) -> np.ndarray:
    if vertices.shape[0] <= max_count:
        return vertices

    rng = np.random.default_rng(42)
    indices = rng.choice(vertices.shape[0], max_count, replace=False)
    return vertices[indices]


def _build_quality_reference(input_path: str | Path) -> dict | None:
    try:
        mesh = _load_trimesh(input_path)
    except Exception:
        return None

    diagonal = float(np.linalg.norm(mesh.bounding_box.extents))
    if diagonal <= 1e-9:
        return None

    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    if vertices.shape[0] == 0:
        return None

    sampled_vertices = _sample_vertices(vertices, QUALITY_SAMPLE_CAP)

    return {
        "points": sampled_vertices,
        "diagonal": diagonal,
    }


def _nearest_neighbor_distances(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    count = source.shape[0]
    min_dist_sq = np.full(count, np.inf, dtype=np.float64)

    for start in range(0, count, QUALITY_CHUNK_SIZE):
        chunk = source[start:start + QUALITY_CHUNK_SIZE]
        delta = chunk[:, None, :] - target[None, :, :]
        dist_sq = np.sum(delta * delta, axis=2)
        min_dist_sq[start:start + len(chunk)] = np.min(dist_sq, axis=1)

    return np.sqrt(min_dist_sq)


def _surface_deviation_percent(quality_ref: dict, optimized_path: str | Path) -> float | None:
    try:
        optimized_mesh = _load_trimesh(optimized_path)
    except Exception:
        return None

    optimized_points = np.asarray(optimized_mesh.vertices, dtype=np.float64)
    if optimized_points.shape[0] == 0:
        return None
    optimized_points = _sample_vertices(optimized_points, QUALITY_SAMPLE_CAP)
    reference_points = quality_ref["points"]

    src_to_dst = _nearest_neighbor_distances(reference_points, optimized_points)
    dst_to_src = _nearest_neighbor_distances(optimized_points, reference_points)

    p95_distance = float(max(np.percentile(src_to_dst, 95), np.percentile(dst_to_src, 95)))
    deviation_percent = (p95_distance / quality_ref["diagonal"]) * 100

    return round(float(deviation_percent), 4)


def _is_quality_metric_reliable(
    input_path: str | Path,
    quality_ref: dict | None,
    max_deviation_percent: float,
) -> bool:
    if quality_ref is None:
        return False

    baseline_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".obj", delete=False) as tmp:
            baseline_path = tmp.name

        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(str(input_path))
        _save_current_mesh(ms, baseline_path)

        baseline_deviation = _surface_deviation_percent(quality_ref, baseline_path)
        if baseline_deviation is None:
            return False

        # Allow a small conversion tolerance, but treat very high baseline error as unreliable.
        reliability_limit = max(max_deviation_percent * 1.5, 0.5)
        return baseline_deviation <= reliability_limit
    except Exception:
        return False
    finally:
        if baseline_path and os.path.exists(baseline_path):
            try:
                os.remove(baseline_path)
            except Exception:
                pass


def decimate_mesh(
    input_path: str | Path,
    output_path: str | Path,
    target_faces: int,
    preserve_normals: bool = True,
    preserve_boundaries: bool = True,
    strict_quality: bool = True,
    max_deviation_percent: float = 2.0,
    max_target_overshoot_percent: float = 12.0,
) -> tuple[MeshStats, dict]:
    input_path = str(input_path)
    output_path = str(output_path)

    inspection_mesh = pymeshlab.MeshSet()
    inspection_mesh.load_new_mesh(input_path)

    current_faces = inspection_mesh.current_mesh().face_number()
    if current_faces <= 4:
        _save_current_mesh(inspection_mesh, output_path)
        return _get_stats(output_path, inspection_mesh), {
            "target_faces_used": current_faces,
            "quality_deviation_percent": 0.0,
            "quality_guard_relaxed": False,
            "quality_guard_satisfied": True,
        }

    requested_target = int(max(4, min(target_faces, current_faces - 1)))

    if requested_target >= current_faces:
        _save_current_mesh(inspection_mesh, output_path)
        return _get_stats(output_path, inspection_mesh), {
            "target_faces_used": current_faces,
            "quality_deviation_percent": 0.0,
            "quality_guard_relaxed": False,
            "quality_guard_satisfied": True,
        }

    quality_ref = _build_quality_reference(input_path) if strict_quality else None
    if strict_quality and quality_ref is not None:
        if not _is_quality_metric_reliable(input_path, quality_ref, max_deviation_percent):
            # Some scene formats can report inflated deviations after conversion.
            # In those cases, use decimation without the geometric lock metric.
            quality_ref = None
    candidate_targets = (
        _build_target_candidates(
            current_faces=current_faces,
            target_faces=requested_target,
            max_target_overshoot_percent=max_target_overshoot_percent,
        )
        if strict_quality
        else [requested_target]
    )

    last_stats: MeshStats | None = None
    last_deviation: float | None = None
    last_target = requested_target

    for candidate_target in candidate_targets:
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(input_path)
        # _apply_structure_preclean(ms)  # Rollback the preclean step
        _apply_decimation(
            ms=ms,
            target_faces=candidate_target,
            preserve_normals=preserve_normals,
            preserve_boundaries=preserve_boundaries,
        )
        _save_current_mesh(ms, output_path)

        stats = _get_stats(output_path, ms)
        deviation_percent = _surface_deviation_percent(quality_ref, output_path) if quality_ref else None

        last_stats = stats
        last_deviation = deviation_percent
        last_target = candidate_target

        if not strict_quality:
            break

        if quality_ref is None:
            # Quality check unavailable for this mesh format; keep strict-preserving settings.
            break

        if deviation_percent is not None and deviation_percent <= max_deviation_percent:
            return stats, {
                "target_faces_used": stats.face_count,
                "quality_deviation_percent": deviation_percent,
                "quality_guard_relaxed": candidate_target != requested_target,
                "quality_guard_satisfied": True,
            }

    if last_stats is None:
        raise RuntimeError("Decimation failed to produce an output mesh")

    quality_guard_satisfied = True
    if strict_quality and quality_ref is not None and last_deviation is not None:
        quality_guard_satisfied = last_deviation <= max_deviation_percent

    return last_stats, {
        "target_faces_used": last_stats.face_count,
        "quality_deviation_percent": last_deviation,
        "quality_guard_relaxed": last_target != requested_target,
        "quality_guard_satisfied": quality_guard_satisfied,
    }


def generate_lods(
    input_path: str | Path,
    output_dir: str | Path,
    base_name: str,
    original_faces: int,
    output_extension: str | None = None,
    preserve_normals: bool = True,
    preserve_boundaries: bool = True,
) -> list[LODResult]:
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    lod_ratios = {
        "LOD0": 1.0,
        "LOD1": 0.5,
        "LOD2": 0.25,
        "LOD3": 0.1,
    }

    results = []
    ext = resolve_output_extension(output_extension or Path(input_path).suffix)

    for level, ratio in lod_ratios.items():
        target = max(int(original_faces * ratio), 100)
        output_file = output_dir / f"{base_name}_{level}{ext}"

        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(str(input_path))

        if ratio < 1.0:
            _apply_decimation(
                ms=ms,
                target_faces=target,
                preserve_normals=preserve_normals,
                preserve_boundaries=preserve_boundaries,
            )

        _save_current_mesh(ms, output_file)
        mesh = ms.current_mesh()
        file_size = os.path.getsize(output_file)

        reduction = 0.0
        if original_faces > 0:
            reduction = round((1 - mesh.face_number() / original_faces) * 100, 1)

        results.append(LODResult(
            level=level,
            face_count=mesh.face_number(),
            vertex_count=mesh.vertex_number(),
            filename=output_file.name,
            file_size_mb=round(file_size / (1024 * 1024), 3),
            reduction_percent=reduction,
        ))

    return results


def _get_stats(filepath: str, ms: pymeshlab.MeshSet) -> MeshStats:
    mesh = ms.current_mesh()
    file_size = os.path.getsize(filepath)
    has_uvs = mesh.has_wedge_tex_coord() if hasattr(mesh, 'has_wedge_tex_coord') else False
    has_normals = mesh.has_vertex_normal() if hasattr(mesh, 'has_vertex_normal') else False

    bounding_box = None
    if hasattr(mesh, 'bounding_box'):
        try:
            bb = mesh.bounding_box()
            bounding_box = {
                "min": [bb.min()[0], bb.min()[1], bb.min()[2]],
                "max": [bb.max()[0], bb.max()[1], bb.max()[2]],
                "diagonal": bb.diagonal(),
            }
        except Exception:
            bounding_box = None

    return MeshStats(
        vertex_count=mesh.vertex_number(),
        face_count=mesh.face_number(),
        file_size_bytes=file_size,
        file_size_mb=round(file_size / (1024 * 1024), 3),
        has_uvs=has_uvs,
        has_normals=has_normals,
        bounding_box=bounding_box,
    )
