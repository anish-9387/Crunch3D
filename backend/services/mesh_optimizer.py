"""
mesh_optimizer.py — Crunch3D / OptiMesh
Clean rewrite with proper multi-component mesh handling.

Architecture:
  input_file
    → Trimesh  (split into N components)
    → PyMeshLab per component  (QEM decimation)
    → Trimesh  (merge all components back)
    → output_file

All function signatures are identical to the original so nothing
else in the codebase needs to change.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time as _time
from pathlib import Path

import numpy as np
import pymeshlab
import trimesh
import trimesh.util

logger = logging.getLogger(__name__)

from ..models.schemas import MeshStats, LODResult
from .importance_mapper import compute_importance


# ---------------------------------------------------------------------------
# Timing instrumentation (temporary — left in place for profiling)
# ---------------------------------------------------------------------------

_TIMING: dict[str, float] = {}
_TIMING_COUNT: dict[str, int] = {}


class _t:
    """Context manager that records elapsed seconds into ``_TIMING``."""
    __slots__ = ('label', '_t0')

    def __init__(self, label: str) -> None:
        self.label = label

    def __enter__(self) -> None:
        self._t0 = _time.perf_counter()

    def __exit__(self, *args: object) -> None:
        dt = _time.perf_counter() - self._t0
        _TIMING[self.label] = _TIMING.get(self.label, 0.0) + dt
        _TIMING_COUNT[self.label] = _TIMING_COUNT.get(self.label, 0) + 1


def _timing_reset() -> None:
    _TIMING.clear()
    _TIMING_COUNT.clear()


def _timing_report() -> None:
    """Print the full timing report to stdout."""
    from .importance_mapper import TIMING as _IMP_T, TIMING_COUNT as _IMP_C

    # Merge importance_mapper timing into the local dict
    for k, v in _IMP_T.items():
        _TIMING.setdefault(k, 0.0)
        _TIMING[k] += v
        _TIMING_COUNT.setdefault(k, 0)
        _TIMING_COUNT[k] += _IMP_C.get(k, 0)

    _SEC_TO_MS = 1000.0

    # Display order
    top_level = ["Mesh loading", "Component extraction",
                 "Scene reconstruction", "Export"]
    per_comp   = ["Adjacency build", "Curvature", "Normal variation",
                  "Boundary detection", "Feature density",
                  "Normalization", "Laplacian smoothing",
                  "Quality injection", "QEM decimation"]

    lines: list[str] = []
    lines.append("")
    lines.append("=== TIMING REPORT ===")

    for label in top_level:
        total_s = _TIMING.get(label, 0.0)
        lines.append(f"{label:<25s} {total_s * _SEC_TO_MS:>12.1f} ms")

    lines.append("Per-component (avg / total):")
    for label in per_comp:
        total_s = _TIMING.get(label, 0.0)
        count   = _TIMING_COUNT.get(label, 0)
        avg_ms  = (total_s / count * _SEC_TO_MS) if count else 0.0
        lines.append(
            f"  {label:<23s} {avg_ms:>8.2f} ms / {total_s:>6.3f} s"
        )

    total_all = sum(_TIMING.values())
    lines.append(f"Total:{'':>20s} {total_all:>8.3f} s")
    lines.append("=====================")
    print("\n".join(lines))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_SAVE_EXTENSIONS = {".obj", ".stl", ".ply", ".off"}
QUALITY_SAMPLE_CAP = 700
QUALITY_CHUNK_SIZE = 160


# ---------------------------------------------------------------------------
# Helpers — format
# ---------------------------------------------------------------------------

def resolve_output_extension(input_extension: str) -> str:
    ext = (input_extension or "").lower().strip()
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    return ext if ext in SUPPORTED_SAVE_EXTENSIONS else ".obj"


# ---------------------------------------------------------------------------
# Helpers — component loading / saving
# ---------------------------------------------------------------------------

def _load_components(path: str | Path) -> list[trimesh.Trimesh]:
    """
    Load a mesh file and return a flat list of Trimesh components.

    Handles:
      - Single Trimesh  (already one piece)
      - trimesh.Scene   (GLB / GLTF / FBX / multi-group OBJ)
      - Disconnected geometry inside a single Trimesh (split by body)

    Always returns at least one component or raises ValueError.
    """
    with _t("Mesh loading"):
        loaded = trimesh.load(str(path), process=False)

    meshes: list[trimesh.Trimesh] = []

    with _t("Component extraction"):
        if isinstance(loaded, trimesh.Scene):
            for node_name in loaded.graph.nodes_geometry:
                val = loaded.graph[node_name]
                transform = val[0]
                geom_name = val[1] if len(val) >= 2 else node_name
                geom = loaded.geometry.get(geom_name)
                if not isinstance(geom, trimesh.Trimesh) or len(geom.faces) == 0:
                    continue
                verts = trimesh.transformations.transform_points(
                    geom.vertices.copy(), transform
                )
                transformed = trimesh.Trimesh(
                    vertices=verts,
                    faces=geom.faces.copy(),
                    process=False,
                )
                meshes.append(transformed)

        elif isinstance(loaded, trimesh.Trimesh):
            parts = loaded.split(only_watertight=False)
            for p in parts:
                if isinstance(p, trimesh.Trimesh) and len(p.faces) > 0:
                    meshes.append(p)
            if not meshes and len(loaded.faces) > 0:
                meshes.append(loaded)

    if not meshes:
        raise ValueError(f"No usable mesh geometry found in: {path}")

    return meshes


def _component_to_pymeshlab(mesh: trimesh.Trimesh) -> pymeshlab.MeshSet:
    """Export a Trimesh component to a temp OBJ, load it into a fresh MeshSet."""
    tmp = tempfile.NamedTemporaryFile(suffix=".obj", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        mesh.export(tmp_path)
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(tmp_path)
    finally:
        _safe_remove(tmp_path)
    return ms


def _pymeshlab_to_trimesh(ms: pymeshlab.MeshSet) -> trimesh.Trimesh | None:
    """Save the current MeshSet mesh to a temp OBJ, reload as Trimesh."""
    tmp = tempfile.NamedTemporaryFile(suffix=".obj", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        _save_current_mesh(ms, tmp_path)
        result = trimesh.load(tmp_path, process=False)
        if isinstance(result, trimesh.Scene):
            parts = [g for g in result.geometry.values()
                     if isinstance(g, trimesh.Trimesh) and len(g.faces) > 0]
            return trimesh.util.concatenate(parts) if parts else None
        if isinstance(result, trimesh.Trimesh) and len(result.faces) > 0:
            return result
        return None
    finally:
        _safe_remove(tmp_path)


def _safe_remove(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helpers — PyMeshLab save (unchanged from original, kept for compatibility)
# ---------------------------------------------------------------------------

def _save_current_mesh(ms: pymeshlab.MeshSet, output_path: str | Path) -> None:
    output_path = str(output_path)
    save_attempts = [
        {},
        {"save_textures": False},
        {"save_textures": False, "save_wedge_texcoord": False},
        {
            "save_textures": False,
            "save_wedge_texcoord": False,
            "save_vertex_normal": False,
            "save_vertex_color": False,
            "save_face_color": False,
        },
    ]

    last_error: Exception | None = None
    for kwargs in save_attempts:
        try:
            ms.save_current_mesh(output_path, **kwargs)
            return
        except Exception as exc:
            last_error = exc

    # Final fallback: export pure geometry through trimesh.
    try:
        mesh = ms.current_mesh()
        vertices = np.asarray(mesh.vertex_matrix(), dtype=np.float64)
        faces = np.asarray(mesh.face_matrix(), dtype=np.int64)
        if vertices.size > 0 and faces.size > 0:
            tri_mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
            tri_mesh.export(output_path)
            return
    except Exception as exc:
        last_error = exc

    raise RuntimeError(f"Could not save mesh output: {last_error}")


# ---------------------------------------------------------------------------
# Helpers — topology cleanup
# ---------------------------------------------------------------------------

def _apply_structure_preclean(ms: pymeshlab.MeshSet) -> None:
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


# ---------------------------------------------------------------------------
# Core — per-component QEM decimation
# ---------------------------------------------------------------------------

def _apply_decimation(
    ms: pymeshlab.MeshSet,
    target_faces: int,
    preserve_normals: bool,
    preserve_boundaries: bool,
) -> None:
    """
    Run importance-weighted (quality-weighted) QEM on the current mesh.

    The per-vertex quality scalar must have been injected beforehand (see
    ``_inject_importance_as_quality``).  When ``qualityweight=True``
    the quadric error metric penalises collapsing high-quality (high-importance)
    vertices, biasing decimation toward low-importance regions.
    """
    ms.apply_filter(
        "meshing_decimation_quadric_edge_collapse",
        targetfacenum=int(max(target_faces, 4)),
        preservenormal=preserve_normals,
        preserveboundary=preserve_boundaries,
        preservetopology=False,       # True breaks disconnected components
        planarquadric=False,          # Distorts curved/organic surfaces
        qualitythr=0.3,
        qualityweight=True,
        selected=False,
    )


def _inject_importance_as_quality(ms: pymeshlab.MeshSet, importance: np.ndarray) -> bool:
    """
    Write per-vertex importance scores into PyMeshLab's quality field.

    PyMeshLab's weighted QEM reads from this field when qualityweight=True.
    Higher quality = protected from collapse.

    PyMeshLab 2025.7's Python API does not expose a setter for the main
    vertex-scalar (quality) array.  We work around this via a PLY round-trip:

      1. Save the current mesh as an ASCII PLY  (no vertex colors).
      2. Inject vertex-color properties that encode importance as grey-scale
         (R=G=B=importance*255, A=255).
      3. Reload the edited PLY, replacing the original mesh in *ms*.
      4. Derive the quality field from the colour channel: q = (r+g+b)/(3*255).

    Returns True if the injection succeeded, False if decimation will run
    without the quality scalar.
    """
    n_verts = ms.current_mesh().vertex_number()
    if len(importance) != n_verts:
        logger.warning(
            "Importance length %d ≠ vertex count %d", len(importance), n_verts
        )
        return False

    # High importance → high quality → protected from collapse
    # (qualityweight penalises LOW quality, making those edges more
    #  likely to collapse, so we pass importance directly).
    quality = np.clip(importance.astype(np.float64), 0.0, 1.0)

    colour_byte = (quality * 255.0).astype(np.uint8)

    # ── 1. Save current mesh as ASCII PLY (no colours) ────────────
    fd_plain, path_plain = tempfile.mkstemp(suffix=".ply")
    os.close(fd_plain)
    fd_colour, path_colour = tempfile.mkstemp(suffix="_clr.ply")
    os.close(fd_colour)

    try:
        ms.save_current_mesh(path_plain, binary=False, save_vertex_color=False)

        # ── 2. Read + modify PLY ──────────────────────────────────
        with open(path_plain, encoding="ascii") as f:
            content = f.read()
        lines = content.rstrip("\n").split("\n")

        header_end = -1
        for i, line in enumerate(lines):
            if line == "end_header":
                header_end = i
                break
        if header_end == -1:
            return False

        num_vertices = 0
        for line in lines[:header_end]:
            if line.startswith("element vertex"):
                num_vertices = int(line.split()[-1])
                break

        if num_vertices != n_verts:
            return False

        # Build new header with vertex-color properties.
        # Insert colour properties just BEFORE `element face`.
        new_lines: list[str] = []
        for line in lines:
            if line.startswith("element face"):
                new_lines.extend([
                    "property uchar red",
                    "property uchar green",
                    "property uchar blue",
                    "property uchar alpha",
                ])
            new_lines.append(line)

        shift = 4
        new_header_end = header_end + shift

        # Inject colour values into vertex-data lines.
        # Original vertex lines have form: x y z quality
        # We append 4 colour values, overwriting the line.
        for v_idx in range(num_vertices):
            orig_idx = header_end + 1 + v_idx
            new_idx = new_header_end + 1 + v_idx
            coords = lines[orig_idx].strip()
            c = int(colour_byte[v_idx])
            new_lines[new_idx] = f"{coords} {c} {c} {c} 255"

        with open(path_colour, "w", encoding="ascii") as f:
            f.write("\n".join(new_lines) + "\n")

        # ── 3. Load colour PLY into the SAME MeshSet ─────────────
        old_id = ms.current_mesh_id()
        ms.load_new_mesh(path_colour)            # becomes current

        # ── 4. Derive quality (= scalar) from RGB ────────────────
        ms.apply_filter(
            "compute_scalar_by_function_per_vertex",
            q="(r+g+b)/(3*255)",
            normalize=False,
        )

        # ── 5. Delete the original (uncoloured) mesh ─────────────
        ms.set_current_mesh(old_id)
        ms.delete_current_mesh()

        return True

    except Exception as exc:
        logger.warning("Importance injection failed: %s. Falling back to plain QEM.", exc)
        return False

    finally:
        for p in (path_plain, path_colour):
            try:
                os.unlink(p)
            except OSError:
                pass


def _decimate_component(
    mesh: trimesh.Trimesh,
    target_faces: int,
    preserve_normals: bool,
    preserve_boundaries: bool,
    use_importance: bool = True,
    precomputed_importance: np.ndarray | None = None,
    cache: dict[int, np.ndarray] | None = None,
) -> trimesh.Trimesh | None:
    """
    Run QEM decimation on a single Trimesh component.

    When *use_importance* is True the importance map is computed and
    injected into the mesh's quality field, and ``qualityweight=True``
    causes the decimation to preferentially collapse low-importance
    edges.

    If *precomputed_importance* is provided and its length matches the
    vertex count after PyMeshLab preclean, it is used directly —
    skipping the expensive ``compute_importance()`` call.

    If *cache* is provided, importance computed on the post-preclean
    mesh is stored keyed by ``id(mesh)``, so subsequent retries that
    pass the same component object hit the cache regardless of whether
    *precomputed_importance* matched.
    """
    logger.info("Trimesh before conversion: %d", len(mesh.vertices))

    ms = _component_to_pymeshlab(mesh)
    logger.info("PyMeshLab after load: %d", ms.current_mesh().vertex_number())

    _apply_structure_preclean(ms)
    pml_verts = ms.current_mesh().vertex_number()
    logger.info("PyMeshLab after preclean: %d", pml_verts)

    current_faces = ms.current_mesh().face_number()
    if target_faces >= current_faces:
        return _pymeshlab_to_trimesh(ms)

    # ── Resolve importance: cache → precomputed → fresh compute ──
    importance: np.ndarray | None = None
    if use_importance:
        cache_key = id(mesh)
        if cache is not None and cache_key in cache:
            importance = cache[cache_key]
            logger.info("Using inter-retry cached importance (%d)", len(importance))
        elif (
            precomputed_importance is not None
            and len(precomputed_importance) == pml_verts
        ):
            importance = precomputed_importance
            logger.info("Using precomputed importance (%d)", len(importance))
        else:
            pml_mesh = ms.current_mesh()
            verts = np.asarray(pml_mesh.vertex_matrix(), dtype=np.float64)
            faces = np.asarray(pml_mesh.face_matrix(), dtype=np.int64)
            tmp_trimesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
            importance = compute_importance(tmp_trimesh)
            logger.info("Importance array: %d", len(importance))
            assert len(importance) == pml_verts, (
                f"Importance len {len(importance)} != vertex count {pml_verts}"
            )
            if cache is not None:
                cache[cache_key] = importance
                logger.info("Stored in inter-retry cache (%d)", len(importance))

    if importance is not None:
        with _t("Quality injection"):
            injection_ok = _inject_importance_as_quality(ms, importance)
        logger.info("Injection success: %s", injection_ok)

    with _t("QEM decimation"):
        _apply_decimation(
            ms=ms,
            target_faces=target_faces,
            preserve_normals=preserve_normals,
            preserve_boundaries=preserve_boundaries,
        )

    with _t("Scene reconstruction"):
        result = _pymeshlab_to_trimesh(ms)
    return result


def _decimate_all_components(
    components: list[trimesh.Trimesh],
    target_faces: int,
    preserve_normals: bool,
    preserve_boundaries: bool,
    use_importance: bool = True,
    component_importance: list[np.ndarray] | None = None,
    cache: dict[int, np.ndarray] | None = None,
) -> trimesh.Trimesh:
    """
    Decimate each component proportionally with importance weighting,
    then merge back into one mesh.

    If *component_importance* is provided it must be the same length as
    *components*; each entry is the precomputed importance array for the
    corresponding component.

    If *cache* is provided it is forwarded to ``_decimate_component``
    for inter-retry importance caching.
    """
    total_faces = sum(len(c.faces) for c in components)
    output_parts: list[trimesh.Trimesh] = []

    for idx, component in enumerate(components):
        if len(component.faces) == 0:
            continue

        ratio = len(component.faces) / total_faces if total_faces > 0 else 1.0
        component_target = max(4, int(target_faces * ratio))

        precomputed = (
            component_importance[idx]
            if component_importance is not None and idx < len(component_importance)
            else None
        )

        result = _decimate_component(
            mesh=component,
            target_faces=component_target,
            preserve_normals=preserve_normals,
            preserve_boundaries=preserve_boundaries,
            use_importance=use_importance,
            precomputed_importance=precomputed,
            cache=cache,
        )
        if result is not None:
            output_parts.append(result)

    if not output_parts:
        raise RuntimeError("All mesh components failed decimation")

    if len(output_parts) == 1:
        return output_parts[0]

    return trimesh.util.concatenate(output_parts)


# ---------------------------------------------------------------------------
# Helpers — quality guard
# ---------------------------------------------------------------------------

def _sample_vertices(vertices: np.ndarray, max_count: int) -> np.ndarray:
    if vertices.shape[0] <= max_count:
        return vertices
    rng = np.random.default_rng(42)
    indices = rng.choice(vertices.shape[0], max_count, replace=False)
    return vertices[indices]


def _build_quality_reference(components: list[trimesh.Trimesh]) -> dict | None:
    all_vertices = np.vstack([np.asarray(c.vertices, dtype=np.float64)
                               for c in components if len(c.vertices) > 0])
    if len(all_vertices) == 0:
        return None

    all_faces = sum(len(c.faces) for c in components)
    if all_faces == 0:
        return None

    combined = trimesh.util.concatenate(components)
    diagonal = float(np.linalg.norm(combined.bounding_box.extents))
    if diagonal <= 1e-9:
        return None

    sampled = _sample_vertices(all_vertices, QUALITY_SAMPLE_CAP)
    return {"points": sampled, "diagonal": diagonal}


def _nearest_neighbor_distances(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    count = source.shape[0]
    min_dist_sq = np.full(count, np.inf, dtype=np.float64)

    for start in range(0, count, QUALITY_CHUNK_SIZE):
        chunk = source[start:start + QUALITY_CHUNK_SIZE]
        delta = chunk[:, None, :] - target[None, :, :]
        dist_sq = np.sum(delta * delta, axis=2)
        min_dist_sq[start:start + len(chunk)] = np.min(dist_sq, axis=1)

    return np.sqrt(min_dist_sq)


def _surface_deviation_percent(
    quality_ref: dict,
    result_mesh: trimesh.Trimesh,
) -> float | None:
    optimized_points = np.asarray(result_mesh.vertices, dtype=np.float64)
    if optimized_points.shape[0] == 0:
        return None

    optimized_points = _sample_vertices(optimized_points, QUALITY_SAMPLE_CAP)
    reference_points = quality_ref["points"]

    src_to_dst = _nearest_neighbor_distances(reference_points, optimized_points)
    dst_to_src = _nearest_neighbor_distances(optimized_points, reference_points)

    p95 = float(max(np.percentile(src_to_dst, 95), np.percentile(dst_to_src, 95)))
    return round((p95 / quality_ref["diagonal"]) * 100, 4)


def _build_target_candidates(
    current_faces: int,
    target_faces: int,
    max_target_overshoot_percent: float,
) -> list[int]:
    target = int(max(4, min(target_faces, current_faces - 1)))
    overshoot_factor = max(0.0, float(max_target_overshoot_percent)) / 100.0
    cap = int(max(target, min(int(round(target * (1.0 + overshoot_factor))), current_faces - 1)))

    candidates: list[int] = []
    for ratio in [0.0, 0.03, 0.06, 0.09, 0.12]:
        candidate = target + int((cap - target) * ratio / 0.12) if cap > target else target
        candidate = int(max(4, min(candidate, cap)))
        if candidate not in candidates:
            candidates.append(candidate)

    if cap not in candidates:
        candidates.append(cap)

    return candidates


# ---------------------------------------------------------------------------
# Helpers — stats
# ---------------------------------------------------------------------------

def _stats_from_trimesh(mesh: trimesh.Trimesh, output_path: str) -> MeshStats:
    file_size = os.path.getsize(output_path)
    bb = mesh.bounding_box
    extents = bb.extents.tolist()
    bounds = mesh.bounds  # shape (2, 3)
    bounding_box = {
        "min": bounds[0].tolist(),
        "max": bounds[1].tolist(),
        "diagonal": float(np.linalg.norm(extents)),
    }
    return MeshStats(
        vertex_count=len(mesh.vertices),
        face_count=len(mesh.faces),
        file_size_bytes=file_size,
        file_size_mb=round(file_size / (1024 * 1024), 3),
        has_uvs=hasattr(mesh, "visual") and hasattr(mesh.visual, "uv") and mesh.visual.uv is not None,
        has_normals=mesh.vertex_normals is not None and len(mesh.vertex_normals) > 0,
        bounding_box=bounding_box,
    )


# ---------------------------------------------------------------------------
# Public API — decimate_mesh  (signature unchanged)
# ---------------------------------------------------------------------------

def decimate_mesh(
    input_path: str | Path,
    output_path: str | Path,
    target_faces: int,
    preserve_normals: bool = True,
    preserve_boundaries: bool = True,
    strict_quality: bool = True,
    max_deviation_percent: float = 2.0,
    max_target_overshoot_percent: float = 12.0,
    use_importance: bool = True,       # v1.1: importance-weighted QEM
) -> tuple[MeshStats, dict]:
    input_path = str(input_path)
    output_path = str(output_path)

    _timing_reset()

    # ── 1. Load all components ──────────────────────────────────────────────
    components = _load_components(input_path)
    total_faces = sum(len(c.faces) for c in components)

    # ── 2. Skip decimation if mesh is already at or below target ───────────
    if total_faces <= 4 or target_faces >= total_faces:
        combined = (trimesh.util.concatenate(components)
                    if len(components) > 1 else components[0])
        with _t("Export"):
            combined.export(output_path)
        stats = _stats_from_trimesh(combined, output_path)
        _timing_report()
        return stats, {
            "target_faces_used": total_faces,
            "quality_deviation_percent": 0.0,
            "quality_guard_relaxed": False,
            "quality_guard_satisfied": True,
            "importance_scores": importance_scores,
        }

    requested_target = int(max(4, min(target_faces, total_faces - 1)))

    # ── 3. Precompute importance once per component (cached for retries) ──
    component_importance: list[np.ndarray] | None = None
    flat_importance: list[float] = []
    if use_importance:
        component_importance = []
        for c in components:
            if len(c.faces) == 0:
                component_importance.append(np.array([], dtype=np.float64))
            else:
                imp = compute_importance(c)
                component_importance.append(imp)
                flat_importance.extend(imp.tolist())
    importance_scores = flat_importance if flat_importance else None

    # ── 4. Inter-retry importance cache (post-preclean, keyed by id) ────
    _importance_cache: dict[int, np.ndarray] = {}

    # ── 5. Build quality reference from original components ────────────────
    quality_ref = _build_quality_reference(components) if strict_quality else None

    # ── 6. Build candidate targets for quality-guard retry loop ───────────
    candidate_targets = (
        _build_target_candidates(
            current_faces=total_faces,
            target_faces=requested_target,
            max_target_overshoot_percent=max_target_overshoot_percent,
        )
        if strict_quality
        else [requested_target]
    )

    last_stats: MeshStats | None = None
    last_deviation: float | None = None
    last_target = requested_target
    last_result: trimesh.Trimesh | None = None

    # ── 7. Retry loop — tighten target until quality guard is satisfied ────
    for candidate_target in candidate_targets:
        result = _decimate_all_components(
            components=components,
            target_faces=candidate_target,
            preserve_normals=preserve_normals,
            preserve_boundaries=preserve_boundaries,
            use_importance=use_importance,
            component_importance=component_importance,
            cache=_importance_cache,
        )

        with _t("Export"):
            result.export(output_path)
        stats = _stats_from_trimesh(result, output_path)
        deviation = _surface_deviation_percent(quality_ref, result) if quality_ref else None

        last_stats = stats
        last_deviation = deviation
        last_target = candidate_target
        last_result = result

        if not strict_quality or quality_ref is None:
            break

        if deviation is not None and deviation <= max_deviation_percent:
            _timing_report()
            return stats, {
                "target_faces_used": stats.face_count,
                "quality_deviation_percent": deviation,
                "quality_guard_relaxed": candidate_target != requested_target,
                "quality_guard_satisfied": True,
                "importance_scores": importance_scores,
            }

    if last_stats is None:
        raise RuntimeError("Decimation failed to produce an output mesh")

    quality_guard_satisfied = True
    if strict_quality and quality_ref is not None and last_deviation is not None:
        quality_guard_satisfied = last_deviation <= max_deviation_percent

    _timing_report()
    return last_stats, {
        "target_faces_used": last_stats.face_count,
        "quality_deviation_percent": last_deviation,
        "quality_guard_relaxed": last_target != requested_target,
        "quality_guard_satisfied": quality_guard_satisfied,
        "importance_scores": importance_scores,
    }


# ---------------------------------------------------------------------------
# Public API — generate_lods  (signature unchanged)
# ---------------------------------------------------------------------------

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

    ext = resolve_output_extension(output_extension or Path(input_path).suffix)
    components = _load_components(input_path)
    total_faces = sum(len(c.faces) for c in components)

    # Precompute importance once for all LOD levels
    component_importance: list[np.ndarray] | None = None
    if any(ratio < 1.0 for ratio in lod_ratios.values()):
        component_importance = []
        for c in components:
            if len(c.faces) == 0:
                component_importance.append(np.array([], dtype=np.float64))
            else:
                component_importance.append(compute_importance(c))

    # Inter-retry cache shared across LOD levels
    _importance_cache: dict[int, np.ndarray] = {}
    results: list[LODResult] = []

    for level, ratio in lod_ratios.items():
        target = max(int(total_faces * ratio), 100)
        output_file = output_dir / f"{base_name}_{level}{ext}"

        if ratio >= 1.0:
            # LOD0 — just re-export the original without touching it
            combined = (trimesh.util.concatenate(components)
                        if len(components) > 1 else components[0])
            combined.export(str(output_file))
            result_mesh = combined
        else:
            result_mesh = _decimate_all_components(
                components=components,
                target_faces=target,
                preserve_normals=preserve_normals,
                preserve_boundaries=preserve_boundaries,
                component_importance=component_importance,
                cache=_importance_cache,
            )
            result_mesh.export(str(output_file))

        file_size = os.path.getsize(output_file)
        face_count = len(result_mesh.faces)
        reduction = round((1 - face_count / original_faces) * 100, 1) if original_faces > 0 else 0.0

        results.append(LODResult(
            level=level,
            face_count=face_count,
            vertex_count=len(result_mesh.vertices),
            filename=output_file.name,
            file_size_mb=round(file_size / (1024 * 1024), 3),
            reduction_percent=reduction,
        ))

    return results