"""
brush_refine.py — Crunch3D / OptiMesh

Region-local optimization pass driven by the viewer's refactor brush.

The main pipeline (``engine/mesh_optimizer.py``) decimates a whole model toward
a face budget.  On some models it leaves a patch under-optimized — a flat panel
the importance map rated as detail, a dense region the global budget never got
around to.  This module is the manual override for exactly that case: the user
paints the patch in the viewer, and the same importance stack runs again with
its collapse budget confined to what they painted.

Two properties are load-bearing:

* **Geometry outside the painted region is left alone.**  The pass selects the
  region's faces in PyMeshLab and runs QEM with ``selected=True``, so no edge
  outside the selection is a collapse candidate.  Components the brush never
  touched are passed straight through without a decimation round at all.
* **Nothing in the existing pipeline changes.**  This is an additive module:
  it reuses ``mesh_optimizer``'s loaders, exporters and importance helpers but
  does not modify them, so ``/api/optimize`` behaves exactly as before whether
  or not the brush is ever used.

Public API — one function::

    refine_region(input_path, output_path, stamps, ...) -> (MeshStats, meta)
"""

from __future__ import annotations

import logging
from itertools import count
from pathlib import Path

import numpy as np
import trimesh

from ..api.schemas import MeshStats
from ..core.config import (
    ENABLE_EDGE_FEATURES,
    ENABLE_GNN_IMPORTANCE,
    ENABLE_PERSISTENCE_GATE,
    KAPPA,
)
from ..importance.importance_mapper import compute_importance
from . import brush_selection as bsel
from .mesh_optimizer import (
    _apply_edge_feature_protection,
    _component_to_pymeshlab,
    _components_has_animation,
    _components_have_textures,
    _ensure_uv_material,
    _export_mesh_with_texture_tracking,
    _load_components,
    _pymeshlab_to_trimesh,
    _scene_merge,
    _stats_from_trimesh,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_REGION_FACES = 12
"""Smallest painted region worth running a decimation round on.

Below this the collapse budget rounds to a face or two, so the round costs a
full PyMeshLab conversion to change nothing visible.  Such a component is
passed through untouched instead.
"""

MAX_REGION_REMOVAL_FRACTION = 0.92
"""Cap on how much of the painted region one pass may remove.

Left uncapped, a 100 % request would ask QEM to collapse the region to nothing
and take the surrounding ring with it.  Users can run the brush again for more.
"""

DEFAULT_REDUCTION_PERCENT = 40.0

ESCALATION_SHORTFALL = 0.5
"""Fraction of the requested removal below which the pass retries unweighted.

Importance weighting is a preference, not a promise: if the region's importance
map happens to sit uniformly high, ``qualityweight=True`` protects the whole
selection and the reduction the user asked for silently does not happen.  Coming
in under half the request is the signal to run the region again on geometric
error alone.  Set close to 1.0 this would throw the learned weighting away over
ordinary rounding; set at 0 the feature never recovers from a flat map.
"""

FRAME_AGREEMENT_TOLERANCE = 0.04
"""How far the viewer's normalised bbox extents may drift from the engine's.

Decimation nudges a bounding box by a fraction of a percent, so the tolerance
only has to cover that; anything larger means the two sides disagree about the
model's axes, not about its detail.
"""


class BrushSelectionError(ValueError):
    """The brush strokes did not resolve to a usable region on this mesh."""


# ---------------------------------------------------------------------------
# Importance for the painted region
# ---------------------------------------------------------------------------

def _region_importance(mesh: trimesh.Trimesh) -> np.ndarray:
    """Run the full importance stack on *mesh* and return scores in ``[0, 1]``.

    Mirrors the stages ``mesh_optimizer._decimate_component`` applies — base
    heuristics, GNN edge prediction, the 19-cue edge descriptor, the
    persistence gate — under the same feature flags, so a brushed region is
    judged by the same model as a normal pass.  Every optional stage is
    individually guarded: if one fails the region still gets decimated using
    whatever importance was computed up to that point, because a failed cue is
    not a reason to refuse the user's edit.

    Locked vertices come back as ``1.0`` rather than the sentinel ``999.0`` the
    main path uses, since the brush blend in
    ``brush_selection.blend_importance`` needs a genuine ``[0, 1]`` scale.  The
    two are equivalent by the time PyMeshLab sees them — quality injection
    clips to ``[0, 1]`` regardless.

    The composed map is finally spread across the full range by
    :func:`_spread_importance`; see there for why a narrow band would otherwise
    stall the decimation.
    """
    importance = compute_importance(mesh)

    if ENABLE_GNN_IMPORTANCE:
        try:
            from ..learning.inference import predict_edge_importance

            edge_scores = np.asarray(predict_edge_importance(mesh), dtype=np.float64)
            edges = np.asarray(mesh.edges_unique, dtype=np.int64)
            per_vertex = np.zeros(len(mesh.vertices), dtype=np.float64)
            np.maximum.at(per_vertex, edges[:, 0], edge_scores)
            np.maximum.at(per_vertex, edges[:, 1], edge_scores)
            importance = importance * (1.0 + KAPPA * per_vertex)
        except Exception as exc:
            logger.warning("Brush region: GNN importance skipped (%s)", exc)

    if ENABLE_EDGE_FEATURES:
        importance, _ = _apply_edge_feature_protection(mesh, importance)

    locked: list[int] = []
    if ENABLE_PERSISTENCE_GATE:
        try:
            from ..topology.gate import admissible_edges
            from ..topology.persistence import compute_edge_persistence

            persistence = compute_edge_persistence(mesh, importance)
            admissible = admissible_edges(persistence)
            locked = [v for edge in persistence if edge not in admissible for v in edge]
        except Exception as exc:
            logger.warning("Brush region: persistence gate skipped (%s)", exc)

    importance = _spread_importance(importance)

    # Hard locks are re-applied *after* the spread so a gated vertex stays at
    # full protection instead of being rescaled back down into the pack.
    if locked:
        importance[np.asarray(locked, dtype=np.int64)] = 1.0
        logger.info("Brush region: persistence gate locked %d vertices", len(locked))

    return np.clip(importance, 0.0, 1.0)


def _spread_importance(importance: np.ndarray) -> np.ndarray:
    """Stretch importance across the full ``[0, 1]`` range, order preserved.

    The composed stack is a product of near-one factors, so on a typical mesh it
    lands in a narrow high band — measured at ``[0.90, 1.00]`` on a subdivided
    icosphere.  PyMeshLab reads that field as a QEM weight, and a field where
    every vertex is ~0.95 says "protect everything equally", which is how a
    request to remove 70 % of a region ends up removing 0.3 % of it.

    Only the *ordering* of importance carries the feature-preservation signal —
    which edges are more worth keeping than their neighbours — so rescaling the
    band back onto the full range keeps the meaning and restores the contrast
    QEM needs.  Robust percentiles rather than min/max, so a single extreme
    vertex cannot squash everything else back into a sliver.  A genuinely
    uniform map carries no signal at all and becomes flat zero, which lets QEM
    fall back to pure geometric error inside the region.
    """
    # No clipping on the way in: the GNN stage multiplies importance by up to
    # (1 + KAPPA), so the raw map runs past 1.0 and clipping first would flatten
    # exactly the peaks the rescale is meant to spread apart.
    imp = np.nan_to_num(
        np.asarray(importance, dtype=np.float64).reshape(-1),
        nan=0.0, posinf=1.0, neginf=0.0,
    )
    if imp.size == 0:
        return imp

    lo, hi = (float(v) for v in np.percentile(imp, (2.0, 98.0)))
    if hi - lo < 1e-6:
        lo, hi = float(imp.min()), float(imp.max())
    if hi - lo < 1e-6:
        return np.zeros_like(imp)

    return np.clip((imp - lo) / (hi - lo), 0.0, 1.0)

# ---------------------------------------------------------------------------
# PyMeshLab per-vertex scalar injection
# ---------------------------------------------------------------------------

WEIGHT_ATTRIBUTE = "crunch3d_brush_weight"
QUALITY_ATTRIBUTE = "crunch3d_brush_quality"

_ATTRIBUTE_SERIAL = count(1)
"""Suffix source for injected attribute names.

PyMeshLab refuses to add a custom attribute whose name is already on the mesh
("The mesh already has a custom attribute with the name ..."), and it offers no
way to overwrite one.  A pass injects the same two fields more than once — once
per attempt — so the name has to be fresh each time or the second attempt loses
both its selection and its quality field and falls back to decimating the whole
component.  The attributes never reach disk: the mesh leaves this module through
``vertex_matrix``/``face_matrix``, so the extras are dropped with the MeshSet.
"""


def _inject_vertex_quality(ms, values: np.ndarray, attribute: str) -> bool:
    """Write *values* into PyMeshLab's per-vertex quality scalar.

    Goes through a named custom vertex attribute and then evaluates that
    attribute as the quality function.  The obvious shortcut — assigning into
    ``current_mesh().vertex_color_matrix()`` and deriving quality from the
    colour channels — does not work on PyMeshLab 2025.7: that accessor hands
    back a detached array (``owndata=False`` but with a temporary base), so the
    assignment is dropped and every vertex silently keeps quality ``1.0``.
    A custom attribute is copied into the mesh by value, so it survives.

    Nothing is written to disk, so UVs, materials and texture maps are
    untouched.  Returns False if PyMeshLab rejected the injection, in which
    case the caller must not assume the quality field means anything.
    """
    mesh = ms.current_mesh()
    if len(values) != mesh.vertex_number():
        logger.warning(
            "Brush quality injection skipped: %d values vs %d vertices",
            len(values), mesh.vertex_number(),
        )
        return False

    scalars = np.clip(np.asarray(values, dtype=np.float64), 0.0, 1.0)
    name = f"{attribute}_{next(_ATTRIBUTE_SERIAL)}"
    try:
        mesh.add_vertex_custom_scalar_attribute(scalars, name)
        ms.apply_filter(
            "compute_scalar_by_function_per_vertex", q=name, normalize=False
        )
        return True
    except Exception as exc:
        logger.warning("Brush quality injection failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# PyMeshLab face selection
# ---------------------------------------------------------------------------

def _selected_face_count(ms) -> int:
    """Faces PyMeshLab currently has selected, or ``-1`` if it will not say."""
    try:
        return int(ms.current_mesh().selected_face_number())
    except Exception:
        return -1


def _select_region_faces(ms, threshold: float, expected_faces: int) -> int:
    """Select the faces of the painted region; return how many got selected.

    Expects the raw brush weight to be sitting in the per-vertex quality
    scalar, so the condition ``(q0+q1+q2)/3 >= threshold`` is literally
    ``brush_selection.face_weights(...) >= threshold`` evaluated inside
    PyMeshLab.  The caller overwrites quality with the blended importance
    afterwards; selection flags live separately and survive that.

    *expected_faces* is the count this module computed for the same condition,
    and a selection materially larger than it is rejected.  That check is what
    stops the pass from silently going global: if the quality injection had not
    landed, every face would satisfy the condition and the whole component
    would become a collapse candidate.

    MeshLab has renamed these filters across releases, so each candidate is
    tried in turn and the first plausible result wins.  Returns ``0`` when none
    worked, telling the caller to fall back to the weight-only path.
    """
    ceiling = int(expected_faces * 1.05) + 2
    condition = f"(q0+q1+q2)/3 >= {float(threshold):.6f}"
    per_vertex_condition = f"q >= {float(threshold):.6f}"
    candidates = (
        ("compute_selection_by_condition_per_face", {"condselect": condition}, None),
        ("conditional_face_selection", {"condselect": condition}, None),
        (
            "compute_selection_by_condition_per_vertex",
            {"condselect": per_vertex_condition},
            "compute_selection_transfer_vertex_to_face",
        ),
    )

    for filter_name, kwargs, transfer in candidates:
        try:
            ms.apply_filter("set_selection_none")
        except Exception:
            pass
        try:
            ms.apply_filter(filter_name, **kwargs)
            if transfer:
                ms.apply_filter(transfer, inclusive=True)
        except Exception as exc:
            logger.debug("Brush selection via %s unavailable: %s", filter_name, exc)
            continue

        count = _selected_face_count(ms)
        if count <= 0:
            continue
        if count > ceiling:
            logger.warning(
                "Brush selection via %s returned %d faces for an expected %d; "
                "ignoring it", filter_name, count, expected_faces,
            )
            continue

        logger.info("Brush region: %d faces selected via %s", count, filter_name)
        return count

    try:
        ms.apply_filter("set_selection_none")
    except Exception:
        pass
    logger.warning("Brush region: no PyMeshLab face-selection filter worked")
    return 0

# ---------------------------------------------------------------------------
# Per-component region pass
# ---------------------------------------------------------------------------

def _pymeshlab_arrays(ms) -> tuple[np.ndarray, np.ndarray]:
    mesh = ms.current_mesh()
    return (
        np.asarray(mesh.vertex_matrix(), dtype=np.float64),
        np.asarray(mesh.face_matrix(), dtype=np.int64),
    )


def _decimate_selection(
    ms,
    total_faces: int,
    region_faces: int,
    removal: int,
    selection_count: int,
    preserve_normals: bool,
    preserve_boundaries: bool,
) -> int:
    """Run QEM confined to the current selection.  Returns faces removed.

    With ``selected=True``, PyMeshLab 2025.7 measures ``targetfacenum`` against
    the *selected* face count, not the whole mesh — asking for
    ``total - removal`` there is above the selection size and the filter returns
    immediately having collapsed nothing.  The selected-relative target is
    therefore tried first, with the whole-mesh reading kept as the second
    attempt so the unselected fallback path (and any build that reads the
    parameter the other way) still reduces.  Each attempt is verified against
    the face count because the wrong reading fails silently rather than raising.

    ``preservetopology=False`` and ``planarquadric=False`` match what the main
    pipeline already ships, so a brushed region decimates like any other.
    """
    if selection_count > 0:
        targets = (max(4, region_faces - removal), max(4, total_faces - removal))
    else:
        targets = (max(4, total_faces - removal),)

    for target in targets:
        before = ms.current_mesh().face_number()
        try:
            ms.apply_filter(
                "meshing_decimation_quadric_edge_collapse",
                targetfacenum=int(target),
                preservenormal=preserve_normals,
                preserveboundary=preserve_boundaries,
                preservetopology=False,
                planarquadric=False,
                qualitythr=0.3,
                qualityweight=True,
                selected=selection_count > 0,
            )
        except Exception as exc:
            logger.warning("Brush region: decimation call failed (%s)", exc)
            return 0

        removed = before - ms.current_mesh().face_number()
        if removed > 0:
            return removed

    return 0


def _region_attempt(
    ms,
    stamps: list[bsel.BrushStamp],
    origin: np.ndarray,
    scale: float,
    falloff: str,
    threshold: float,
    quality_of,
    removal: int,
    preserve_normals: bool,
    preserve_boundaries: bool,
    require_selection: bool = False,
) -> tuple[int, int]:
    """One select-then-decimate attempt on the mesh as it currently stands.

    Returns ``(faces_removed, selection_count)``.

    Weights are rebuilt here rather than passed in, because an attempt may run
    on a mesh a previous attempt already changed: ``build_vertex_weights`` works
    off vertex *positions*, so re-deriving them is both correct after a collapse
    and cheap next to the decimation itself.  ``quality_of`` maps those weights
    to the field QEM weighs edges by, which lets the caller change protection
    strategy between attempts without recomputing the importance stack.

    With *require_selection* the attempt does nothing at all unless PyMeshLab
    genuinely confined it to the painted faces.  Quality weighting alone biases
    collapses towards the stroke but does not forbid them elsewhere, so an
    attempt that has given up its importance term has to be fenced in by the
    selection or not run.
    """
    vertices, faces = _pymeshlab_arrays(ms)
    if len(vertices) == 0 or len(faces) == 0:
        return 0, 0

    weights = bsel.build_vertex_weights(vertices, stamps, origin, scale, falloff)
    _, region_faces = bsel.selection_counts(faces, weights, threshold)
    if region_faces < 1:
        return 0, 0

    selection_count = 0
    if _inject_vertex_quality(ms, weights, WEIGHT_ATTRIBUTE):
        selection_count = _select_region_faces(ms, threshold, region_faces)

    if require_selection and selection_count <= 0:
        logger.warning(
            "Brush region: skipping the unweighted retry because the region "
            "could not be selected; the stroke's own weighting stands"
        )
        return 0, 0

    _inject_vertex_quality(ms, quality_of(weights), QUALITY_ATTRIBUTE)

    capped = max(1, min(removal, int(region_faces * MAX_REGION_REMOVAL_FRACTION)))
    removed = _decimate_selection(
        ms=ms,
        total_faces=len(faces),
        region_faces=region_faces,
        removal=capped,
        selection_count=selection_count,
        preserve_normals=preserve_normals,
        preserve_boundaries=preserve_boundaries,
    )
    return removed, selection_count


def _refine_component(
    mesh: trimesh.Trimesh,
    stamps: list[bsel.BrushStamp],
    origin: np.ndarray,
    scale: float,
    falloff: str,
    reduction_percent: float,
    preserve_normals: bool,
    preserve_boundaries: bool,
    threshold: float,
    min_region_faces: int,
) -> tuple[trimesh.Trimesh | None, dict]:
    """Decimate one component inside the painted region.

    Returns ``(result, report)``.  ``result`` is ``None`` when the component
    should be kept as-is — either the brush missed it, the region is too small
    to be worth a pass, or the decimation produced nothing usable.  The report
    always describes what was found, so the caller can total up the numbers the
    API reports back.

    Deliberately does **not** run ``_apply_structure_preclean``: welding
    duplicate vertices and repairing non-manifold edges rewrites topology
    across the entire component, which is exactly the collateral change a
    region-local edit must not make.
    """
    report = {
        "selected_vertices": 0,
        "selected_faces": 0,
        "mode": "untouched",
        "refined": False,
        "escalated": False,
        "faces_removed": 0,
    }

    ms = _component_to_pymeshlab(mesh)
    vertices, faces = _pymeshlab_arrays(ms)
    if len(vertices) == 0 or len(faces) == 0:
        return None, report

    # Weights are rebuilt from PyMeshLab's own vertex positions rather than
    # carried over by index: the OBJ round-trip in _component_to_pymeshlab may
    # reorder or weld vertices, and position-based lookup is immune to that.
    weights = bsel.build_vertex_weights(vertices, stamps, origin, scale, falloff)
    selected_vertices, region_faces = bsel.selection_counts(faces, weights, threshold)
    report["selected_vertices"] = selected_vertices
    report["selected_faces"] = region_faces

    if region_faces < max(1, min_region_faces):
        return None, report

    removal = int(round(region_faces * float(reduction_percent) / 100.0))
    removal = min(removal, int(region_faces * MAX_REGION_REMOVAL_FRACTION))
    if removal < 1:
        return None, report

    try:
        importance = _region_importance(
            trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        )
    except Exception as exc:
        logger.warning("Brush region: importance failed, using flat map (%s)", exc)
        importance = np.zeros(len(vertices), dtype=np.float64)

    if len(importance) != len(vertices):
        logger.warning(
            "Brush region: importance length %d != %d vertices; using flat map",
            len(importance), len(vertices),
        )
        importance = np.zeros(len(vertices), dtype=np.float64)

    # Attempt 1 — the importance blend: inside the stroke the learned model
    # decides which edges go, outside it every vertex is pinned to full
    # protection.  The importance array is indexed against the mesh exactly as it
    # stands now, so this is the only attempt that can use it.
    removed, selection_count = _region_attempt(
        ms, stamps, origin, scale, falloff, threshold,
        lambda w: bsel.blend_importance(importance, w),
        removal, preserve_normals, preserve_boundaries,
    )

    report["mode"] = "selected_faces" if selection_count > 0 else "weighted_region"
    if selection_count <= 0:
        # No usable selection: the blend still pins every unpainted vertex to
        # full protection, so collapses concentrate inside the stroke even
        # though PyMeshLab is free to consider the whole component.
        logger.info("Brush region: falling back to weight-only protection")

    # Attempt 2 — geometric error alone.  A region whose importance happens to
    # be uniformly high protects itself out of ever being decimated: measured on
    # a merged 116k-face mesh, a request to drop 2,606 faces took only 12 off.
    # The user asked for a reduction, not for an explanation.  Dropping the
    # importance term leaves the brush weight alone in the quality field, so
    # unpainted geometry stays exactly as protected as before and only the
    # *choice* of which edges collapse inside the stroke gives up its learned
    # bias.
    if removed < removal * ESCALATION_SHORTFALL:
        logger.info(
            "Brush region: %d of %d faces came off under importance weighting; "
            "retrying the region on geometric error alone", removed, removal,
        )
        extra, escalated_selection = _region_attempt(
            ms, stamps, origin, scale, falloff, threshold,
            lambda w: bsel.blend_importance(np.zeros_like(w), w),
            removal - removed, preserve_normals, preserve_boundaries,
            require_selection=True,
        )
        if extra > 0:
            removed += extra
            report["escalated"] = True
            if escalated_selection > 0 and selection_count <= 0:
                report["mode"] = "selected_faces"

    report["faces_removed"] = removed
    if removed <= 0:
        logger.info("Brush region: decimation removed no faces; keeping component")
        return None, report

    result = _pymeshlab_to_trimesh(ms)
    if result is None or len(result.faces) == 0:
        logger.warning("Brush region: decimation produced no geometry; keeping component")
        return None, report

    report["refined"] = True
    return result, report

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _components_frame(
    components: list[trimesh.Trimesh],
) -> tuple[np.ndarray, float, np.ndarray]:
    """Normalised brush frame spanning every component.

    Returns ``(origin, scale, extents)`` where *extents* is the bounding box
    measured in the frame's own units, i.e. divided by the diagonal.  Must match
    what the viewer computed over the same geometry, which is why it is taken
    across *all* components at once rather than per component: the user painted
    one model, not a set of independently placed parts.
    """
    lows, highs = [], []
    for component in components:
        if len(component.vertices) == 0:
            continue
        verts = np.asarray(component.vertices, dtype=np.float64)
        lows.append(verts.min(axis=0))
        highs.append(verts.max(axis=0))
    if not lows:
        return np.zeros(3, dtype=np.float64), 1.0, np.zeros(3, dtype=np.float64)

    low = np.min(lows, axis=0)
    high = np.max(highs, axis=0)
    origin, scale = bsel.normalized_frame(low, high)
    return origin, scale, (high - low) / scale


def _assert_frames_agree(engine_extents: np.ndarray, client_extents) -> None:
    """Reject a stroke whose viewer frame does not match the engine's.

    The two sides only agree on where a stamp lands if they agree on the model's
    axes.  Bbox normalisation already absorbs any difference in units, origin or
    overall scale, so the normalised extents are all that is left to compare —
    and if they differ, some loader has permuted or flipped an axis (an FBX
    imported Z-up on one side and Y-up on the other, say).

    Failing here is the point.  A frame mismatch does not make the pass error
    out on its own: it silently optimizes a different part of the model than the
    one the user painted, which is far worse than being told to run a normal
    optimization pass first.
    """
    if client_extents is None:
        return
    client = np.asarray(client_extents, dtype=np.float64).reshape(-1)
    if client.size != 3 or not np.all(np.isfinite(client)):
        return

    drift = float(np.max(np.abs(engine_extents - client)))
    if drift > FRAME_AGREEMENT_TOLERANCE:
        raise BrushSelectionError(
            "The viewer and the optimizer disagree about this model's "
            f"orientation (axis drift {drift:.3f}), so the painted region "
            "cannot be located reliably. Run a normal optimization pass first "
            "and paint on the optimized result."
        )


def _component_touched(
    component: trimesh.Trimesh,
    stamps: list[bsel.BrushStamp],
    origin: np.ndarray,
    scale: float,
) -> bool:
    """Cheap conservative test: could any stamp reach this component at all?

    Compares each stamp's bounding cube against the component's bounding box in
    the normalised frame, so it never rules out a component the brush actually
    touched.  Worth having because the alternative — discovering the miss inside
    ``_refine_component`` — costs a full OBJ round-trip into PyMeshLab, and a
    GLB scene routinely carries dozens of components while a stroke lands on
    two or three.
    """
    verts = np.asarray(component.vertices, dtype=np.float64)
    if verts.size == 0:
        return False

    low = (verts.min(axis=0) - origin) / scale
    high = (verts.max(axis=0) - origin) / scale
    for stamp in stamps:
        center = np.asarray(stamp.center, dtype=np.float64)
        if np.all(center >= low - stamp.radius) and np.all(center <= high + stamp.radius):
            return True
    return False


def refine_region(
    input_path: str | Path,
    output_path: str | Path,
    stamps: list[bsel.BrushStamp],
    reduction_percent: float = DEFAULT_REDUCTION_PERCENT,
    falloff: str = bsel.DEFAULT_FALLOFF,
    preserve_normals: bool = True,
    preserve_boundaries: bool = True,
    selection_threshold: float = bsel.DEFAULT_SELECTION_THRESHOLD,
    min_region_faces: int = MIN_REGION_FACES,
    client_extents: list[float] | None = None,
) -> tuple[MeshStats, dict]:
    """Optimize only the brush-painted region of the mesh at *input_path*.

    Writes the result to *output_path* and returns ``(stats, meta)`` in the same
    shape ``decimate_mesh`` uses, so the API layer can reuse its job-state and
    storage handling verbatim.

    Raises :class:`BrushSelectionError` — and writes nothing at all — when the
    strokes miss the mesh, cover too little of it to act on, or the region
    turns out to be irreducible.  Leaving the previous output in place is the
    correct outcome there: the user asked for a local edit, and no local edit
    was possible.
    """
    input_path = str(input_path)
    output_path = str(output_path)

    if not stamps:
        raise BrushSelectionError("No brush strokes were supplied.")

    components = _load_components(input_path)
    origin, scale, extents = _components_frame(components)
    _assert_frames_agree(extents, client_extents)
    faces_before = sum(len(c.faces) for c in components)

    original_has_textures = _components_have_textures(components)
    original_has_animation = _components_has_animation(components)

    parts: list[trimesh.Trimesh] = []
    reports: list[dict] = []
    refined = 0

    for component in components:
        if len(component.faces) == 0:
            continue

        if not _component_touched(component, stamps, origin, scale):
            parts.append(_ensure_uv_material(component))
            reports.append({
                "selected_vertices": 0, "selected_faces": 0,
                "mode": "untouched", "refined": False,
            })
            continue

        try:
            result, report = _refine_component(
                mesh=component,
                stamps=stamps,
                origin=origin,
                scale=scale,
                falloff=falloff,
                reduction_percent=reduction_percent,
                preserve_normals=preserve_normals,
                preserve_boundaries=preserve_boundaries,
                threshold=selection_threshold,
                min_region_faces=min_region_faces,
            )
        except Exception as exc:
            # One awkward component must not cost the user the whole edit; keep
            # it verbatim and carry on with the rest of the model.
            logger.warning("Brush region: component pass failed, keeping it (%s)", exc)
            result, report = None, {
                "selected_vertices": 0, "selected_faces": 0,
                "mode": "failed", "refined": False,
            }

        reports.append(report)
        if result is None:
            parts.append(_ensure_uv_material(component))
        else:
            parts.append(result)
            refined += 1

    selected_vertices = sum(r["selected_vertices"] for r in reports)
    selected_faces = sum(r["selected_faces"] for r in reports)

    if selected_faces == 0:
        raise BrushSelectionError(
            "The brush selection did not land on any geometry. Paint directly "
            "on the model surface, or increase the brush size, and try again."
        )
    if refined == 0:
        raise BrushSelectionError(
            f"The painted region ({selected_faces:,} faces) was too small or too "
            "sparse to reduce further. Paint a wider area or raise the region "
            "reduction strength."
        )

    merged = parts[0] if len(parts) == 1 else _scene_merge(parts)
    _ensure_uv_material(merged)

    texture_export_info = _export_mesh_with_texture_tracking(
        merged, output_path, original_has_textures
    )
    stats = _stats_from_trimesh(merged, output_path)

    faces_after = stats.face_count
    region_percent = round(100.0 * selected_faces / faces_before, 2) if faces_before else 0.0

    # Report the weakest guarantee any *refined* component actually got: if even
    # one of them fell back to weight-only protection, the "nothing outside the
    # region moved" promise no longer holds for the whole mesh, and the response
    # has to say so rather than average the answer away.
    refined_modes = {r["mode"] for r in reports if r.get("refined")}
    if "weighted_region" in refined_modes:
        region_mode = "weighted_region"
    elif "selected_faces" in refined_modes:
        region_mode = "selected_faces"
    else:
        region_mode = "untouched"

    meta = {
        "selected_vertex_count": selected_vertices,
        "selected_face_count": selected_faces,
        "region_percent": region_percent,
        "faces_before": faces_before,
        "faces_after": faces_after,
        "faces_removed": max(0, faces_before - faces_after),
        "components_total": len(reports),
        "components_refined": refined,
        "region_mode": region_mode,
        # True when at least one component only reached the requested reduction
        # after the importance term was dropped (see ESCALATION_SHORTFALL).  The
        # region confinement is unaffected; what changed is which edges inside it
        # were chosen, so the response says so rather than implying the learned
        # weighting drove the whole edit.
        "region_escalated": any(r.get("escalated") for r in reports),
        "reduction_percent_requested": round(float(reduction_percent), 2),
        "texture_export_info": texture_export_info,
        "original_has_textures": original_has_textures,
        "original_has_animation": original_has_animation,
    }

    logger.info(
        "Brush refine: %d/%d components, region %d faces (%.2f%%), %d -> %d faces",
        refined, len(reports), selected_faces, region_percent, faces_before, faces_after,
    )
    return stats, meta
