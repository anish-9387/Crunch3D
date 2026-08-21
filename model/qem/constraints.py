"""qem/constraints.py — deterministic collapse validation (§42, §43).

The validator is the hard safety layer around the learned score: a high-scoring
model cannot rescue a broken collapse, so every candidate passes these checks
before it is allowed to touch the mesh.  Rejections are counted by reason so
the benchmark can report "invalid collapses rejected" (§56).
"""

from __future__ import annotations

import dataclasses

import numpy as np

from ..core.config import FLIP_THRESHOLD, MAX_ASPECT_RATIO, MIN_AREA_RATIO

_EPS = 1e-12

REASONS = (
    "dead_vertex",
    "protected",
    "boundary_drag",
    "boundary_pinch",
    "link_condition",
    "normal_flip",
    "degenerate_face",
    "aspect_ratio",
    "valence",
)


@dataclasses.dataclass
class ConstraintConfig:
    link_condition: bool = True
    preserve_boundary: bool = True
    normal_flip: bool = True
    flip_threshold: float = FLIP_THRESHOLD
    min_area_ratio: float = MIN_AREA_RATIO
    max_aspect_ratio: float = MAX_ASPECT_RATIO
    max_valence: int = 0
    """0 disables the valence guard."""


class CollapseValidator:
    """Validates ``collapse(removed → survivor)`` against a live HalfEdgeMesh."""

    __slots__ = ("mesh", "config", "protected", "area_floor", "rejected", "boundary")

    def __init__(
        self,
        mesh,
        config: ConstraintConfig | None = None,
        protected: set[tuple[int, int]] | None = None,
    ):
        self.mesh = mesh
        self.config = config or ConstraintConfig()
        self.protected = set(protected) if protected else set()
        self.rejected = {reason: 0 for reason in REASONS}
        self.boundary: np.ndarray | None = None
        """Optional cached per-vertex boundary mask, kept fresh by the caller."""

        faces = mesh.alive_faces()
        if len(faces):
            p0, p1, p2 = mesh.verts[faces[:, 0]], mesh.verts[faces[:, 1]], mesh.verts[faces[:, 2]]
            mean_area = float(
                np.mean(0.5 * np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1))
            )
        else:
            mean_area = 0.0
        self.area_floor = self.config.min_area_ratio * mean_area

    # ── public API ──────────────────────────────────────────────────────────

    def check(self, removed: int, survivor: int, new_pos: np.ndarray) -> tuple[bool, str]:
        mesh = self.mesh
        cfg = self.config

        if not (mesh.vert_alive[removed] and mesh.vert_alive[survivor]):
            return self._reject("dead_vertex")

        key = (min(removed, survivor), max(removed, survivor))
        if key in self.protected:
            return self._reject("protected")

        link_faces = mesh.edge_faces(removed, survivor)
        if not link_faces:
            return self._reject("dead_vertex")

        if cfg.preserve_boundary:
            removed_on_border = self._on_border(removed)
            survivor_on_border = self._on_border(survivor)
            if removed_on_border and not survivor_on_border:
                return self._reject("boundary_drag")
            if removed_on_border and survivor_on_border and len(link_faces) >= 2:
                return self._reject("boundary_pinch")

        ring_removed = mesh.one_ring(removed)
        ring_survivor = mesh.one_ring(survivor)

        if cfg.link_condition:
            shared = ring_removed & ring_survivor
            opposite = {
                int(w)
                for f in link_faces
                for w in mesh.faces[f]
                if int(w) not in (removed, survivor)
            }
            if shared != opposite:
                return self._reject("link_condition")

        if cfg.max_valence:
            new_valence = len((ring_removed | ring_survivor) - {removed, survivor})
            if new_valence > cfg.max_valence:
                return self._reject("valence")

        ok, reason = self._check_geometry(removed, survivor, new_pos, set(link_faces))
        if not ok:
            return self._reject(reason)

        return True, ""

    def _reject(self, reason: str) -> tuple[bool, str]:
        self.rejected[reason] = self.rejected.get(reason, 0) + 1
        return False, reason

    def _on_border(self, v: int) -> bool:
        if self.boundary is not None:
            return bool(self.boundary[v])
        return self.mesh.is_boundary_vertex(v)

    # ── geometric checks (§43) ──────────────────────────────────────────────

    def _check_geometry(
        self, removed: int, survivor: int, new_pos: np.ndarray, link_faces: set[int]
    ) -> tuple[bool, str]:
        mesh = self.mesh
        cfg = self.config

        affected = [
            f
            for f in (mesh.vertex_faces[removed] | mesh.vertex_faces[survivor])
            if mesh.face_alive[f] and f not in link_faces
        ]
        if not affected:
            return True, ""

        tri = mesh.faces[affected]
        old_pts = mesh.verts[tri]

        new_tri = np.where(tri == removed, survivor, tri)
        new_pts = mesh.verts[new_tri]
        new_pts = np.where((new_tri == survivor)[:, :, None], new_pos, new_pts)

        old_cross = np.cross(old_pts[:, 1] - old_pts[:, 0], old_pts[:, 2] - old_pts[:, 0])
        new_cross = np.cross(new_pts[:, 1] - new_pts[:, 0], new_pts[:, 2] - new_pts[:, 0])
        new_area = 0.5 * np.linalg.norm(new_cross, axis=1)

        if np.any(new_area <= self.area_floor):
            return False, "degenerate_face"

        if cfg.normal_flip:
            old_norm = np.linalg.norm(old_cross, axis=1)
            valid = old_norm > _EPS
            if np.any(valid):
                dots = np.einsum(
                    "ij,ij->i",
                    old_cross[valid] / old_norm[valid, None],
                    new_cross[valid] / (2.0 * new_area[valid, None]),
                )
                if np.any(dots < cfg.flip_threshold):
                    return False, "normal_flip"

        if cfg.max_aspect_ratio > 0.0:
            sides = np.stack([
                np.linalg.norm(new_pts[:, 1] - new_pts[:, 0], axis=1),
                np.linalg.norm(new_pts[:, 2] - new_pts[:, 1], axis=1),
                np.linalg.norm(new_pts[:, 0] - new_pts[:, 2], axis=1),
            ], axis=1)
            longest = sides.max(axis=1)
            aspect = (longest * longest) / (2.0 * new_area + _EPS)
            if np.any(aspect > cfg.max_aspect_ratio):
                return False, "aspect_ratio"

        return True, ""

    # ── reporting ───────────────────────────────────────────────────────────

    def summary(self) -> dict:
        total = int(sum(self.rejected.values()))
        return {
            "total": total,
            "by_reason": {k: int(v) for k, v in self.rejected.items() if v},
        }
