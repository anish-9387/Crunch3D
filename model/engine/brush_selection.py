"""
brush_selection.py — Crunch3D / OptiMesh

Turns the viewer's brush strokes into a per-vertex selection weight.

A stroke arrives as a list of *stamps* — one dab of the brush each — expressed
in a **bbox-normalised frame** rather than raw model units::

    u = (p - bbox_min) / ||bbox_max - bbox_min||

Both ends of the wire derive that frame from the same geometry, so it cancels
out any difference in units, centring or overall scale between the three.js
scene the user painted on and the trimesh components the engine loads.  The
weights are rebuilt from vertex *positions* every time they are needed, so
nothing here depends on vertex order or vertex count — which is what lets a
selection survive the OBJ round-trips and topology cleanups that sit between
the upload and the decimation pass.

Pure numpy on purpose (scipy is only an optional accelerator): this is the one
piece of brush maths the API layer and the engine share, and it stays testable
without trimesh or pymeshlab installed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FALLOFF_KERNELS = ("smooth", "linear", "hard")
DEFAULT_FALLOFF = "smooth"

DEFAULT_SELECTION_THRESHOLD = 0.5
"""Weight at which a vertex counts as *inside* the painted region.

The continuous weight also drives the importance blend, but this hard
threshold is what decides which faces the region pass may touch.  Kept at the
midpoint so a stamp's own radius is the selection radius.
"""

MIN_STAMP_RADIUS = 1e-5
MAX_STAMP_RADIUS = 4.0
"""Radii are fractions of the bbox diagonal; >4 would swallow any mesh."""

MAX_STAMPS = 4000
"""Upper bound on stamps per request.  The viewer thins a stroke to roughly
one stamp per third of a brush width, so this is many long strokes — far more
than a hand-painted selection needs — and it keeps both the request body and
the per-stamp neighbour queries bounded.
"""


# ---------------------------------------------------------------------------
# Stamps
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BrushStamp:
    """One dab of the brush, in bbox-normalised coordinates."""

    center: tuple[float, float, float]
    radius: float
    erase: bool = False
    strength: float = 1.0


def _finite_vec3(value) -> tuple[float, float, float] | None:
    try:
        x, y, z = (float(v) for v in value)
    except (TypeError, ValueError):
        return None
    if not all(np.isfinite(v) for v in (x, y, z)):
        return None
    return (x, y, z)


def stamps_from_payload(items) -> list[BrushStamp]:
    """Build stamps from the wire payload, dropping entries that cannot be used.

    Malformed stamps are skipped rather than rejected: one bad dab in a long
    stroke should not throw away the rest of the user's painting.  An entirely
    unusable payload yields an empty list, which callers treat as "nothing
    selected" and report back as such.  Anything past :data:`MAX_STAMPS` is
    dropped, so a runaway client cannot turn one request into an unbounded
    number of neighbour queries.
    """
    stamps: list[BrushStamp] = []
    for item in items or []:
        if len(stamps) >= MAX_STAMPS:
            logger.warning("Brush payload exceeded %d stamps; ignoring the rest", MAX_STAMPS)
            break
        if isinstance(item, dict):
            center = _finite_vec3(item.get("center", item.get("c")))
            radius = item.get("radius", item.get("r"))
            erase = bool(item.get("erase", item.get("op") == "erase"))
            strength = item.get("strength", item.get("f", 1.0))
        else:
            center = _finite_vec3(getattr(item, "center", None))
            radius = getattr(item, "radius", None)
            erase = bool(getattr(item, "erase", False))
            strength = getattr(item, "strength", 1.0)

        if center is None:
            continue
        try:
            radius = float(radius)
            strength = float(strength)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(radius) or not np.isfinite(strength):
            continue
        if radius < MIN_STAMP_RADIUS:
            continue

        stamps.append(BrushStamp(
            center=center,
            radius=float(min(radius, MAX_STAMP_RADIUS)),
            erase=erase,
            strength=float(np.clip(strength, 0.0, 1.0)),
        ))

    return stamps

# ---------------------------------------------------------------------------
# Normalised frame
# ---------------------------------------------------------------------------

def normalized_frame(bounds_min, bounds_max) -> tuple[np.ndarray, float]:
    """Return ``(origin, scale)`` for the bbox-normalised brush frame.

    ``scale`` is the bbox diagonal length, so a stamp radius of 0.05 means
    "5 % of the model's diagonal" on any model in any unit.  Degenerate boxes
    (a single point, a zero-length strip) fall back to a unit scale so the
    caller still gets a usable — if useless — frame instead of a divide by zero.
    """
    lo = np.asarray(bounds_min, dtype=np.float64).reshape(3)
    hi = np.asarray(bounds_max, dtype=np.float64).reshape(3)
    diagonal = float(np.linalg.norm(hi - lo))
    if not np.isfinite(diagonal) or diagonal <= 1e-12:
        diagonal = 1.0
    return lo, diagonal


def frame_from_vertices(vertices) -> tuple[np.ndarray, float]:
    """Normalised frame of a single vertex array (convenience for tests)."""
    verts = np.asarray(vertices, dtype=np.float64).reshape(-1, 3)
    if verts.size == 0:
        return np.zeros(3, dtype=np.float64), 1.0
    return normalized_frame(verts.min(axis=0), verts.max(axis=0))


# ---------------------------------------------------------------------------
# Weight accumulation
# ---------------------------------------------------------------------------

def _kernel(distance_ratio: np.ndarray, falloff: str) -> np.ndarray:
    """Brush profile as a function of ``distance / radius``."""
    if falloff == "hard":
        return (distance_ratio <= 1.0).astype(np.float64)
    t = np.clip(1.0 - distance_ratio, 0.0, 1.0)
    if falloff == "linear":
        return t
    return t * t * (3.0 - 2.0 * t)      # smoothstep — matches the viewer


def _neighbour_query(points: np.ndarray):
    """Return a ``(center, radius) -> indices`` callable for *points*.

    Uses a KD-tree when scipy is importable and the mesh is big enough to pay
    for building one, otherwise an axis-aligned numpy prefilter.  Both return
    exactly the indices inside the sphere, so the caller's maths is identical
    either way and the KD-tree stays a pure speed-up.
    """
    if len(points) >= 4096:
        try:
            from scipy.spatial import cKDTree

            tree = cKDTree(points)

            def query_tree(center: np.ndarray, radius: float) -> np.ndarray:
                return np.asarray(
                    tree.query_ball_point(center, radius), dtype=np.int64
                )

            return query_tree
        except Exception as exc:      # scipy missing, or the tree build failed
            logger.debug("Brush KD-tree unavailable (%s); using numpy prefilter", exc)

    def query_numpy(center: np.ndarray, radius: float) -> np.ndarray:
        candidates = np.flatnonzero(np.all(np.abs(points - center) <= radius, axis=1))
        if candidates.size == 0:
            return candidates
        delta = points[candidates] - center
        return candidates[np.einsum("ij,ij->i", delta, delta) <= radius * radius]

    return query_numpy

def build_vertex_weights(
    vertices,
    stamps: list[BrushStamp],
    origin: np.ndarray,
    scale: float,
    falloff: str = DEFAULT_FALLOFF,
) -> np.ndarray:
    """Per-vertex selection weight in ``[0, 1]`` for the given stamps.

    Stamps are applied in order: an ``add`` stamp raises the weight it covers to
    at least its own profile (``max``), an ``erase`` stamp subtracts its profile
    from whatever is there.  Add uses max rather than a sum so overlapping dabs
    inside one stroke do not pile up into a harder-edged selection than the
    brush the user dragged; erase subtracts so that dragging the eraser back
    over a stroke takes exactly as much away as the stroke put down — the
    behaviour anyone who has used a paint tool expects.
    """
    verts = np.asarray(vertices, dtype=np.float64).reshape(-1, 3)
    weights = np.zeros(len(verts), dtype=np.float64)
    if len(verts) == 0 or not stamps:
        return weights

    if falloff not in FALLOFF_KERNELS:
        falloff = DEFAULT_FALLOFF

    unit = (verts - np.asarray(origin, dtype=np.float64).reshape(3)) / float(scale)
    query = _neighbour_query(unit)

    for stamp in stamps:
        center = np.asarray(stamp.center, dtype=np.float64)
        radius = float(stamp.radius)
        indices = query(center, radius)
        if indices.size == 0:
            continue

        delta = unit[indices] - center
        ratio = np.sqrt(np.einsum("ij,ij->i", delta, delta)) / radius
        profile = _kernel(ratio, falloff) * stamp.strength

        if stamp.erase:
            weights[indices] = np.maximum(weights[indices] - profile, 0.0)
        else:
            weights[indices] = np.maximum(weights[indices], profile)

    return np.clip(weights, 0.0, 1.0)


def face_weights(faces, vertex_weights: np.ndarray) -> np.ndarray:
    """Mean vertex weight per face.

    The mean (rather than min or max) is deliberate: it is exactly the
    ``(q0+q1+q2)/3`` expression the PyMeshLab face-selection condition
    evaluates, so the region the engine decimates is the region this module
    reports and the viewer highlighted.
    """
    tris = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    if tris.size == 0 or vertex_weights.size == 0:
        return np.zeros(len(tris), dtype=np.float64)
    return vertex_weights[tris].mean(axis=1)


def selection_counts(
    faces,
    vertex_weights: np.ndarray,
    threshold: float = DEFAULT_SELECTION_THRESHOLD,
) -> tuple[int, int]:
    """``(selected_vertices, selected_faces)`` at the given threshold."""
    vertices_in = int(np.count_nonzero(vertex_weights >= threshold))
    faces_in = int(np.count_nonzero(face_weights(faces, vertex_weights) >= threshold))
    return vertices_in, faces_in


def blend_importance(importance: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Fold the brush weight into an importance map for the region pass::

        q = 1 - w · (1 - importance)

    Deep inside the painted region (``w = 1``) a vertex keeps its predicted
    importance, so the normal feature-preserving behaviour still decides which
    edges collapse *within* the selection.  Outside it (``w = 0``) the vertex is
    pinned to full protection, which keeps untouched geometry untouched and —
    because the transition is the brush's own smooth falloff — stops the
    selection boundary from turning into a visible crease.
    """
    imp = np.clip(np.asarray(importance, dtype=np.float64).reshape(-1), 0.0, 1.0)
    w = np.clip(np.asarray(weights, dtype=np.float64).reshape(-1), 0.0, 1.0)
    if imp.size != w.size:
        raise ValueError(f"importance/weight length mismatch: {imp.size} vs {w.size}")
    return np.clip(1.0 - w * (1.0 - imp), 0.0, 1.0)
