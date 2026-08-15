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

from ..api.schemas import MeshStats, LODResult
from ..importance.importance_mapper import compute_importance
from ..importance.uv_density import has_uvs as _detect_uvs
from ..importance.animation_awareness import has_animation_data
from ..importance.edge_features import (
    FEATURE_NAMES,
    compute_edge_feature_importance,
    scatter_to_vertices,
)

from ..core.config import (
    ENABLE_EDGE_FEATURES,
    ENABLE_GNN_IMPORTANCE,
    ENABLE_PERSISTENCE_GATE,
    KAPPA,
    KAPPA_EDGE,
)
from ..learning.inference import predict_edge_importance
from ..topology.persistence import compute_edge_persistence
from ..topology.gate import admissible_edges


# ---------------------------------------------------------------------------
# Timing instrumentation (temporary — left in place for profiling)
# ---------------------------------------------------------------------------

def _timing_reset() -> None:
    pass

def _timing_report() -> None:
    pass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

QUALITY_SAMPLE_CAP = 700
QUALITY_CHUNK_SIZE = 160

SUPPORTED_SAVE_EXTENSIONS = {".obj", ".stl", ".ply", ".off", ".glb", ".gltf"}

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

    Materials, textures and UV visuals are carried through so downstream
    decimation/export never loses them.
    """
    loaded = trimesh.load(str(path), process=False)
    if isinstance(loaded, trimesh.Scene):
        dumped = loaded.dump(concatenate=False)
        # `dump()` can sometimes return a single mesh or a numpy array of meshes
        if isinstance(dumped, trimesh.Trimesh):
            dumped = [dumped]
        meshes = []
        for geom in dumped:
            if not isinstance(geom, trimesh.Trimesh) or len(geom.faces) == 0:
                continue
            # Re-attach original visuals (texture/vertex-colour materials) — the
            # scene dump path can strip them.
            visual = getattr(geom, "visual", None)
            if visual is not None and getattr(visual, "kind", None) == "none":
                original = loaded.geometry.get(geom.name) if hasattr(geom, "name") else None
                if original is not None and getattr(original, "visual", None) is not None:
                    try:
                        visual = original.visual
                    except Exception:
                        visual = None
            if visual is not None:
                try:
                    geom = trimesh.Trimesh(
                        vertices=geom.vertices.copy(),
                        faces=geom.faces.copy(),
                        visual=visual,
                        process=False,
                    )
                except Exception:
                    pass
            meshes.append(geom)
    elif isinstance(loaded, trimesh.Trimesh):
        meshes = [loaded]
    else:
        meshes = []

    if not meshes:
        raise ValueError(f"No usable mesh geometry found in: {path}")

    return meshes


def _component_to_pymeshlab(mesh: trimesh.Trimesh) -> pymeshlab.MeshSet:
    """Export a Trimesh component to a temp OBJ, load it into a fresh MeshSet."""
    _ensure_uv_material(mesh)
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


def _pymeshlab_to_trimesh(ms: pymeshlab.MeshSet, _export_info: dict | None = None) -> trimesh.Trimesh | None:
    """Save the current MeshSet mesh to a temp OBJ, reload as Trimesh.
    
    If *_export_info* is provided, it is updated with the export metadata.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".obj", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        info = _save_current_mesh(ms, tmp_path)
        if _export_info is not None:
            _export_info.update(info)
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


def _scene_merge(parts: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    """Merge components while keeping each part's UVs and materials.

    ``trimesh.util.concatenate`` silently drops texture visuals (and can
    raise when two parts carry different materials).  Round-tripping the
    parts through a multi-object OBJ export/import preserves per-part UVs
    and material references, which is exactly what multi-group GLB/OBJ
    uploads need.
    """
    scene = trimesh.Scene()
    for idx, part in enumerate(parts):
        _ensure_uv_material(part)
        scene.add_geometry(
            part,
            node_name=f"mesh_{idx}",
            geom_name=f"geo_{idx}",
            parent_node_name=None,
        )

    tmp = tempfile.NamedTemporaryFile(suffix=".obj", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        scene.export(tmp_path)
        loaded = trimesh.load(tmp_path, process=False)
        if isinstance(loaded, trimesh.Scene):
            geoms = [g for g in loaded.geometry.values()
                     if isinstance(g, trimesh.Trimesh) and len(g.faces) > 0]
            if not geoms:
                raise RuntimeError("Scene merge produced no geometry")
            merged = trimesh.util.concatenate(geoms)
        else:
            merged = loaded
        return _ensure_uv_material(merged)
    finally:
        # Clean up the .obj plus any sidecar .mtl / texture files
        import glob as _glob
        for side in _glob.glob(tmp_path[:-4] + ".*"):
            _safe_remove(side)


def _ensure_uv_material(mesh: trimesh.Trimesh) -> trimesh.Trimesh | None:
    """Keep UV coordinates when exporting a mesh that carries them.

    Trimesh's OBJ/GLB writers silently drop ``vt`` texture coordinates when
    the visual has UVs but no material attached (e.g. after a scene dump,
    a concatenate, or loading a UV-only mesh).  That is the root cause of
    "the texture completely changed" — the geometry survives but the UV map
    vanishes, so the model renders with a broken/untextured surface.

    When UVs exist but the material is missing, attach a minimal unnamed
    SimpleMaterial so writers emit the UV data.  Returns the same mesh.
    """
    try:
        visual = getattr(mesh, "visual", None)
        if visual is None or getattr(visual, "kind", None) != "texture":
            return mesh
        if visual.uv is None:
            return mesh
        if getattr(visual, "material", None) is None:
            from trimesh.visual.material import SimpleMaterial
            mesh.visual = trimesh.visual.TextureVisuals(
                uv=np.asarray(visual.uv, dtype=np.float64),
                material=SimpleMaterial(name="material"),
            )
    except Exception as exc:
        logger.debug("UV material guard failed: %s", exc)
    return mesh


# ---------------------------------------------------------------------------
# Helpers — texture-aware export
# ---------------------------------------------------------------------------

def _export_mesh_with_texture_tracking(
    mesh: trimesh.Trimesh,
    output_path: str,
    original_has_textures: bool,
) -> dict:
    """
    Export a Trimesh to disk and report texture preservation status.

    Tries trimesh's export (which may preserve textures via material files
    for OBJ/MTL).  If the output format does not support textures or the
    export loses them, records the reason.
    """
    output_ext = os.path.splitext(output_path)[1].lower()
    texture_loss_reason: str | None = None
    export_mode_used = "full"
    warnings: list[str] = []

    try:
        _ensure_uv_material(mesh)
        mesh.export(output_path)
    except Exception as exc:
        warnings.append(f"Standard trimesh export failed: {exc}")
        try:
            geo = trimesh.Trimesh(
                vertices=np.asarray(mesh.vertices, dtype=np.float64),
                faces=np.asarray(mesh.faces, dtype=np.int64),
                process=False,
            )
            geo.export(output_path)
            export_mode_used = "trimesh_fallback"
        except Exception as exc2:
            raise RuntimeError(f"Could not save mesh output: {exc2}")

    # Determine texture preservation
    texture_preserved = True
    if original_has_textures:
        if output_ext not in (".obj", ".glb", ".gltf"):
            texture_preserved = False
            texture_loss_reason = (
                f"Output format '{output_ext}' does not support embedded textures"
            )
            warnings.append(texture_loss_reason)
        elif export_mode_used == "trimesh_fallback":
            texture_preserved = False
            texture_loss_reason = "Fallback export mode — textures not preserved"
            warnings.append(texture_loss_reason)

    return _export_result(
        texture_preserved=texture_preserved,
        texture_loss_reason=texture_loss_reason,
        export_mode_used=export_mode_used,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Helpers — PyMeshLab save with texture-export tracking
# ---------------------------------------------------------------------------

# Export mode descriptions for the texture tracking log
_EXPORT_MODE_LABELS: dict[str, str] = {
    "full": "Full export with textures and all attributes",
    "no_textures": "Textures disabled — geometry only with vertex attributes",
    "no_texcoord": "Textures and UV coordinates disabled",
    "minimal": "Minimal export — geometry only, no normals, no colours",
    "trimesh_fallback": "Fallback trimesh export — pure geometry",
}


def _export_result(
    texture_preserved: bool,
    texture_loss_reason: str | None,
    export_mode_used: str,
    warnings: list[str] | None = None,
) -> dict:
    return {
        "texture_preserved": texture_preserved,
        "texture_loss_reason": texture_loss_reason,
        "export_mode_used": export_mode_used,
        "warnings": warnings or [],
    }


def _save_current_mesh(
    ms: pymeshlab.MeshSet,
    output_path: str | Path,
    original_has_textures: bool = False,
) -> dict:
    """
    Save the current PyMeshLab mesh to disk, tracking texture fidelity.

    Tries progressively simpler save configurations until one succeeds.
    Returns a dict with texture-preservation metadata.
    """
    output_path = str(output_path)
    save_attempts = [
        ({"save_textures": True}, "full"),
        ({"save_textures": False}, "no_textures"),
        ({"save_textures": False, "save_wedge_texcoord": False}, "no_texcoord"),
        (
            {
                "save_textures": False,
                "save_wedge_texcoord": False,
                "save_vertex_normal": False,
                "save_vertex_color": False,
                "save_face_color": False,
            },
            "minimal",
        ),
    ]

    last_error: Exception | None = None
    export_mode_used = "full"

    for kwargs, mode_name in save_attempts:
        try:
            ms.save_current_mesh(output_path, **kwargs)
            export_mode_used = mode_name
            break
        except Exception as exc:
            last_error = exc
            continue
    else:
        # Final fallback: export pure geometry through trimesh.
        try:
            mesh = ms.current_mesh()
            vertices = np.asarray(mesh.vertex_matrix(), dtype=np.float64)
            faces = np.asarray(mesh.face_matrix(), dtype=np.int64)
            if vertices.size > 0 and faces.size > 0:
                tri_mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
                tri_mesh.export(output_path)
                export_mode_used = "trimesh_fallback"
        except Exception as exc:
            last_error = exc
            raise RuntimeError(f"Could not save mesh output: {last_error}")

    # Determine texture preservation status
    texture_preserved = True
    texture_loss_reason = None
    warnings: list[str] = []

    if original_has_textures and export_mode_used != "full":
        texture_preserved = False
        texture_loss_reason = (
            f"PyMeshLab could not export with textures; "
            f"used '{export_mode_used}' mode instead"
        )
        warnings.append(texture_loss_reason)
    elif not original_has_textures and export_mode_used == "full":
        if output_path.endswith((".obj", ".ply")):
            pass  # Full mode without textures is fine for these formats

    return _export_result(
        texture_preserved=texture_preserved,
        texture_loss_reason=texture_loss_reason,
        export_mode_used=export_mode_used,
        warnings=warnings,
    )


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

    This is done fully in-memory:

      1. Write importance as grey-scale vertex colours through the writable
         ``vertex_color_matrix()`` numpy view (R=G=B=importance, A=1).
      2. Derive the quality scalar from the colour channel with
         ``compute_scalar_by_function_per_vertex``: q = (r+g+b)/(3*255).
      3. Restore the mesh's original vertex colours.

    Unlike the old PLY round-trip, the mesh is never written to disk, so UV
    coordinates, materials and texture maps are preserved exactly — a model
    with a texture keeps that texture, and a model with baked vertex colours
    keeps those colours.

    Returns True if the injection succeeded, False if decimation will run
    without the quality scalar.
    """
    n_verts = ms.current_mesh().vertex_number()
    if len(importance) != n_verts:
        logger.warning(
            "Importance length %d ≠ vertex count %d", len(importance), n_verts
        )
        return False

    quality = np.clip(importance.astype(np.float64), 0.0, 1.0)

    try:
        mesh = ms.current_mesh()
        colors = mesh.vertex_color_matrix()          # (N, 4) writable view

        original_colors = np.array(colors, copy=True)
        rgb = np.column_stack([quality, quality, quality, np.ones_like(quality)])
        colors[:] = rgb

        ms.apply_filter(
            "compute_scalar_by_function_per_vertex",
            q="(r+g+b)/(3*255)",
            normalize=False,
        )

        # Restore original colours so texture/colour output is untouched.
        colors[:] = original_colors
        return True

    except Exception as exc:
        logger.warning("Importance injection failed: %s. Falling back to plain QEM.", exc)
        return False


def _apply_edge_feature_protection(
    mesh: trimesh.Trimesh, base_importance: np.ndarray
) -> tuple[np.ndarray, dict | None]:
    """Apply the 19-cue edge-feature protection term to vertex importance.

    Computes the fused per-edge importance, collapses it onto vertices (max
    over incident edges), then applies the Eq. 2-style modulation:

        importance[v] *= (1 + KAPPA_EDGE * ī_edge_max[v])

    The result is rescaled back into ``[0, 1]`` when the boost pushes it past
    1.0. That rescale matters: ``_inject_importance_as_quality`` clips to
    ``[0, 1]`` before quantising to a colour byte, so leaving values above 1.0
    would flatten every protected vertex onto the same quality and destroy the
    very ordering this term establishes. The same array is also published as
    ``importance_scores`` for the viewer heatmap, which assumes ``[0, 1]``.
    Rescaling is a single monotonic division, so relative ordering — the only
    thing QEM consumes — is untouched.

    Returns ``(modulated_importance, edge_feature_summary)``. The summary is
    ``None`` when the feature path is disabled, the mesh is empty, the length
    of ``base_importance`` does not match the vertex count, or the descriptor
    raised — in every one of those cases ``base_importance`` is returned
    unchanged so decimation behaves exactly as it did before this stage
    existed.
    """
    if not ENABLE_EDGE_FEATURES:
        return base_importance, None
    if len(mesh.faces) == 0 or len(mesh.vertices) == 0:
        return base_importance, None
    if len(base_importance) != len(mesh.vertices):
        logger.warning("Edge-feature skip: importance %d != verts %d",
                       len(base_importance), len(mesh.vertices))
        return base_importance, None
    try:
        result = compute_edge_feature_importance(
            mesh, vertex_importance=base_importance
        )
        if result.importance.size == 0:
            return base_importance, result.summary

        vert_map = scatter_to_vertices(result, len(mesh.vertices))
        protected = base_importance * (1.0 + KAPPA_EDGE * vert_map)

        peak = float(np.max(protected)) if protected.size else 0.0
        if peak > 1.0:
            protected = protected / peak

        logger.info(
            "Applied edge-feature protection (per-edge mean %.4f, %d edges).",
            float(np.mean(result.importance)),
            len(result.edges),
        )
        return protected, result.summary
    except Exception as e:
        logger.warning("Edge-feature protection failed, continuing: %s", e)
        return base_importance, None


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
            
            # Baseline importance (curvature, uv density, etc.)
            base_importance = compute_importance(tmp_trimesh)
            
            # 1. GNN Edge Importance Predictor
            if ENABLE_GNN_IMPORTANCE:
                try:
                    gnn_edge_importance = predict_edge_importance(tmp_trimesh)
                    # Map edge importance back to vertices (max of connected edges)
                    gnn_vert_importance = np.zeros(len(verts), dtype=np.float64)
                    edges = tmp_trimesh.edges_unique
                    for i, (u, v) in enumerate(edges):
                        score = gnn_edge_importance[i]
                        gnn_vert_importance[u] = max(gnn_vert_importance[u], score)
                        gnn_vert_importance[v] = max(gnn_vert_importance[v], score)
                    
                    # Apply Equation 2: Cost = Cost_QEM * (1 + kappa * y_hat)
                    # Note: We scale importance, which in PyMeshLab dictates *quality* (protection from collapse).
                    # Higher cost in QEM means it is less likely to be collapsed.
                    # PyMeshLab penalizes collapse for vertices with higher quality.
                    # Therefore, we directly scale the vertex importance.
                    base_importance = base_importance * (1.0 + KAPPA * gnn_vert_importance)
                    logger.info("Applied GNN importance scoring.")
                except Exception as e:
                    logger.warning("GNN importance failed, falling back to base heuristics: %s", e)

            # 2. Edge-feature protection (19-cue descriptor, Eq. 2 analogue)
            if ENABLE_EDGE_FEATURES:
                base_importance, _ = _apply_edge_feature_protection(
                    tmp_trimesh, base_importance
                )

            # 3. Persistence Gate
            if ENABLE_PERSISTENCE_GATE:
                try:
                    # Use base_importance (curvature proxy) for filtration
                    edge_pers = compute_edge_persistence(tmp_trimesh, base_importance)
                    admissible = admissible_edges(edge_pers)
                    
                    # Lock vertices belonging to inadmissible edges
                    locked_verts = set()
                    for edge in edge_pers.keys():
                        if edge not in admissible:
                            locked_verts.add(edge[0])
                            locked_verts.add(edge[1])
                    
                    if locked_verts:
                        logger.info("Locking %d vertices due to persistence gate.", len(locked_verts))
                        for v in locked_verts:
                            base_importance[v] = 999.0 # Absolute protection
                except Exception as e:
                    logger.warning("Persistence gate failed, continuing without it: %s", e)
            
            # Normalize to 0-1 for PyMeshLab if it exceeded
            max_imp = np.max(base_importance)
            if max_imp > 1.0 and max_imp != 999.0:
                base_importance = base_importance / max_imp
                
            importance = base_importance
            logger.info("Importance array: %d", len(importance))
            assert len(importance) == pml_verts, (
                f"Importance len {len(importance)} != vertex count {pml_verts}"
            )
            if cache is not None:
                cache[cache_key] = importance
                logger.info("Stored in inter-retry cache (%d)", len(importance))

    if importance is not None:
        injection_ok = _inject_importance_as_quality(ms, importance)
        logger.info("Injection success: %s", injection_ok)

    _apply_decimation(
        ms=ms,
        target_faces=target_faces,
        preserve_normals=preserve_normals,
        preserve_boundaries=preserve_boundaries,
    )

    result = _pymeshlab_to_trimesh(ms)
        
    # 3. Persistence-Gated Texture Reallocation (Paper Eq. 3)
    # This computes the theoretical texel density allocation. Since we don't have SLIM
    # unwrapper built-in natively yet, we compute the target densities and log them.
    from ..core.config import ENABLE_TEXTURE_REALLOCATION
    if ENABLE_TEXTURE_REALLOCATION and result is not None and len(result.faces) > 0:
        try:
            from ..texture.reallocation import reallocate_texel_density
            
            # Reconstruct edge persistence map for the *new* mesh
            if ENABLE_PERSISTENCE_GATE:
                new_imp = compute_importance(result)
                new_edge_pers = compute_edge_persistence(result, new_imp)
                
                # Face importance is average of vertex importances
                face_importance = np.mean(new_imp[result.faces], axis=1)
                
                # Compute densities
                densities = reallocate_texel_density(
                    faces=np.asarray(result.faces, dtype=np.int64),
                    importance=face_importance,
                    edge_persistence=new_edge_pers,
                )
                logger.info("Computed texel reallocation targets for %d faces.", len(densities))
        except Exception as e:
            logger.warning("Texture reallocation failed: %s", e)
            
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
        return _ensure_uv_material(output_parts[0])

    try:
        return _scene_merge(output_parts)
    except Exception as exc:
        logger.warning("Scene merge failed (%s), falling back to concatenate.", exc)
        return trimesh.util.concatenate(output_parts)


# ---------------------------------------------------------------------------
# Helpers — texture / animation detection
# ---------------------------------------------------------------------------

def _components_have_textures(components: list[trimesh.Trimesh]) -> bool:
    """Check if any component carries texture data (UVs + material)."""
    for c in components:
        if _detect_uvs(c):
            return True
        visual = getattr(c, "visual", None)
        if visual is not None and getattr(visual, "kind", None) == "texture":
            return True
    return False


def _components_has_animation(components: list[trimesh.Trimesh]) -> bool:
    """Check if any component has rig/animation data or is deformation-sensitive."""
    for c in components:
        if has_animation_data(c):
            return True
    return False


# ---------------------------------------------------------------------------
# Helpers — quality guard
# ---------------------------------------------------------------------------

def _sample_vertices(vertices: np.ndarray, max_count: int) -> np.ndarray:
    if vertices.shape[0] <= max_count:
        return vertices
    rng = np.random.default_rng(42)
    indices = rng.choice(vertices.shape[0], max_count, replace=False)
    return vertices[indices]


def _summarize_edge_features(per_component: list[dict]) -> dict | None:
    """Merge per-component edge-feature summaries into one JSON-safe meta block.

    Cues are emitted in ``FEATURE_NAMES`` order rather than dict-insertion
    order so the API response — and therefore the UI — lists them identically
    for every mesh. A cue counts as ``present`` when *any* component had the
    data for it, since a mesh can mix UV-mapped and bare components.
    """
    if not per_component:
        return None

    by_name: dict[str, list[dict]] = {}
    for summary in per_component:
        for item in summary.get("features", []):
            by_name.setdefault(item["name"], []).append(item)

    features: list[dict] = []
    for name in FEATURE_NAMES:
        items = by_name.get(name)
        if not items:
            continue
        features.append({
            "name": name,
            "mean": round(sum(i.get("mean", 0.0) for i in items) / len(items), 4),
            "min": round(min(i.get("min", 0.0) for i in items), 4),
            "max": round(max(i.get("max", 0.0) for i in items), 4),
            "present": any(i.get("present", False) for i in items),
        })

    edge_count = int(sum(s.get("edge_count", 0) for s in per_component))
    means = [s.get("importance", {}).get("mean", 0.0) for s in per_component]
    imp_stats = {
        "mean": round(sum(means) / len(means), 4),
        "min": round(min(s.get("importance", {}).get("min", 0.0) for s in per_component), 4),
        "max": round(max(s.get("importance", {}).get("max", 0.0) for s in per_component), 4),
    }
    return {
        "enabled": bool(ENABLE_EDGE_FEATURES),
        "components": len(per_component),
        "edge_count": edge_count,
        "features": features,
        "importance": imp_stats,
    }


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
    job_id: str | None = None,         # self-learning sample tagging
) -> tuple[MeshStats, dict]:
    input_path = str(input_path)
    output_path = str(output_path)

    _timing_reset()

    # ── Self-learning capture ─────────────────────────────────────────────
    def _emit_training_sample(
        components_: list[trimesh.Trimesh],
        component_importance_: list[np.ndarray] | None,
        stats_: MeshStats,
        deviation_: float | None,
    ) -> None:
        if not job_id or component_importance_ is None:
            return
        try:
            from ..learning.continuous_learning import record_training_sample
            record_training_sample(
                components_,
                component_importance_,
                job_id=job_id,
                outcome={
                    "reduction_percent": (
                        round((1 - stats_.face_count / total_faces) * 100, 2)
                        if total_faces > 0 else 0.0
                    ),
                    "quality_deviation_percent": deviation_ or 0.0,
                    "faces_out": stats_.face_count,
                },
            )
        except Exception:
            logger.debug("Training sample capture skipped", exc_info=True)

    # ── 1. Load all components ──────────────────────────────────────────────
    components = _load_components(input_path)
    total_faces = sum(len(c.faces) for c in components)

    # ── Detect texture and animation metadata ────────────────────────────
    original_has_textures = _components_have_textures(components)
    original_has_animation = _components_has_animation(components)
    texture_export_info: dict | None = None

    # ── 2. Skip decimation if mesh is already at or below target ───────────
    if total_faces <= 4 or target_faces >= total_faces:
        combined = (
            _scene_merge(components)
            if len(components) > 1
            else _ensure_uv_material(components[0])
        )
        combined.export(output_path)
        stats = _stats_from_trimesh(combined, output_path)
        _timing_report()
        return stats, {
            "target_faces_used": total_faces,
            "quality_deviation_percent": 0.0,
            "quality_guard_relaxed": False,
            "quality_guard_satisfied": True,
            "importance_scores": None,
            # Nothing was decimated, so no cues were computed — but the key must
            # exist so every caller sees one shape of result dict.
            "edge_features": None,
            "texture_export_info": {
                "texture_preserved": original_has_textures,
                "texture_loss_reason": None,
                "export_mode_used": "full",
                "warnings": [],
            },
            "original_has_textures": original_has_textures,
            "original_has_animation": original_has_animation,
        }

    requested_target = int(max(4, min(target_faces, total_faces - 1)))

    # ── 3. Precompute importance once per component (cached for retries) ──
    component_importance: list[np.ndarray] | None = None
    edge_features_meta: list[dict] = []
    flat_importance: list[float] = []
    if use_importance:
        component_importance = []
        for c in components:
            if len(c.faces) == 0:
                component_importance.append(np.array([], dtype=np.float64))
                continue
            imp = compute_importance(c)
            if ENABLE_EDGE_FEATURES:
                imp, edge_summary = _apply_edge_feature_protection(c, imp)
                if edge_summary is not None:
                    edge_features_meta.append(edge_summary)
            component_importance.append(imp)
            flat_importance.extend(imp.tolist())
    importance_scores = flat_importance if flat_importance else None
    edge_features_summary = _summarize_edge_features(edge_features_meta)

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

        texture_export_info = _export_mesh_with_texture_tracking(
            result, output_path, original_has_textures
        )
        stats = _stats_from_trimesh(result, output_path)
        deviation = _surface_deviation_percent(quality_ref, result) if quality_ref else None

        last_stats = stats
        last_deviation = deviation
        last_target = candidate_target
        last_result = result

        if not strict_quality or quality_ref is None:
            break

        if deviation is not None and deviation <= max_deviation_percent:
            _emit_training_sample(components, component_importance, stats, deviation)
            _timing_report()
            return stats, {
                "target_faces_used": stats.face_count,
                "quality_deviation_percent": deviation,
                "quality_guard_relaxed": candidate_target != requested_target,
                "quality_guard_satisfied": True,
                "importance_scores": importance_scores,
                "edge_features": edge_features_summary,
                "texture_export_info": texture_export_info,
                "original_has_textures": original_has_textures,
                "original_has_animation": original_has_animation,
            }

    if last_stats is None:
        raise RuntimeError("Decimation failed to produce an output mesh")

    quality_guard_satisfied = True
    if strict_quality and quality_ref is not None and last_deviation is not None:
        quality_guard_satisfied = last_deviation <= max_deviation_percent

    _emit_training_sample(components, component_importance, last_stats, last_deviation)
    _timing_report()
    return last_stats, {
        "target_faces_used": last_stats.face_count,
        "quality_deviation_percent": last_deviation,
        "quality_guard_relaxed": last_target != requested_target,
        "quality_guard_satisfied": quality_guard_satisfied,
        "importance_scores": importance_scores,
        "edge_features": edge_features_summary,
        "texture_export_info": texture_export_info,
        "original_has_textures": original_has_textures,
        "original_has_animation": original_has_animation,
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
                continue
            imp = compute_importance(c)
            # Same protection the single-target path applies, so every LOD level
            # preserves the same creases, seams and silhouettes.
            if ENABLE_EDGE_FEATURES:
                imp, _ = _apply_edge_feature_protection(c, imp)
            component_importance.append(imp)

    # Inter-retry cache shared across LOD levels
    _importance_cache: dict[int, np.ndarray] = {}
    results: list[LODResult] = []

    for level, ratio in lod_ratios.items():
        target = max(int(total_faces * ratio), 100)
        output_file = output_dir / f"{base_name}_{level}{ext}"

        if ratio >= 1.0:
            # LOD0 — just re-export the original without touching it
            combined = (
                _scene_merge(components)
                if len(components) > 1
                else _ensure_uv_material(components[0])
            )
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
            _ensure_uv_material(result_mesh)
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