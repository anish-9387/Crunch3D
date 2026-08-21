"""geometry/normalize.py — scale normalization for feature computation (§5.3).

Features are computed on a copy whose centroid sits at the origin and whose
bounding-box diagonal is 1.  Without this the network learns "large object =
important" instead of actual structure.  The original placement is returned
separately so any result can be mapped back exactly.
"""

from __future__ import annotations

import dataclasses

import numpy as np

_EPS = 1e-12


@dataclasses.dataclass(frozen=True)
class Normalization:
    """Invertible similarity transform: ``p_norm = (p - centroid) / scale``."""

    centroid: np.ndarray
    scale: float

    def apply(self, points: np.ndarray) -> np.ndarray:
        return (np.asarray(points, dtype=np.float64) - self.centroid) / self.scale

    def invert(self, points: np.ndarray) -> np.ndarray:
        return np.asarray(points, dtype=np.float64) * self.scale + self.centroid

    def to_dict(self) -> dict:
        return {"centroid": self.centroid.tolist(), "scale": float(self.scale)}


def normalize_points(points: np.ndarray) -> tuple[np.ndarray, Normalization]:
    points = np.asarray(points, dtype=np.float64)
    if len(points) == 0:
        return points.copy(), Normalization(np.zeros(3), 1.0)

    centroid = points.mean(axis=0)
    diagonal = float(np.linalg.norm(points.max(axis=0) - points.min(axis=0)))
    scale = diagonal if diagonal > _EPS else 1.0
    transform = Normalization(centroid, scale)
    return transform.apply(points), transform


def normalize_mesh(mesh):
    """Return a scale-normalized copy of a Trimesh plus its transform."""
    import trimesh

    verts, transform = normalize_points(np.asarray(mesh.vertices))
    copy = trimesh.Trimesh(
        vertices=verts,
        faces=np.asarray(mesh.faces, dtype=np.int64),
        process=False,
    )
    visual = getattr(mesh, "visual", None)
    if visual is not None:
        try:
            copy.visual = visual.copy()
        except Exception:
            pass
    return copy, transform
