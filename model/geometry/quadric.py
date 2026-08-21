"""geometry/quadric.py — Garland-Heckbert quadric error metric (§37).

Per-vertex 4x4 symmetric quadrics are stored as the 10 upper-triangular
entries in a ``(V, 10)`` float64 array:

    [a00, a01, a02, a03, a11, a12, a13, a22, a23, a33]

Reference: Garland & Heckbert, "Surface Simplification Using Quadric Error
Metrics", SIGGRAPH 1997 (https://doi.org/10.1145/258734.258849).
"""

from __future__ import annotations

import numpy as np

_EPS = 1e-12
_SINGULAR_TOL = 1e-9

BOUNDARY_WEIGHT = 1000.0
"""Weight of the virtual perpendicular plane added along boundary edges.

Without it QEM freely shrinks open borders, because a boundary edge has only
one incident face constraining it."""


def quadric_error(q: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Evaluate ``pᵀ Q p`` for packed quadrics ``q`` at points ``p``."""
    q = np.atleast_2d(q)
    p = np.atleast_2d(p)
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    return (
        q[:, 0] * x * x + 2.0 * q[:, 1] * x * y + 2.0 * q[:, 2] * x * z + 2.0 * q[:, 3] * x
        + q[:, 4] * y * y + 2.0 * q[:, 5] * y * z + 2.0 * q[:, 6] * y
        + q[:, 7] * z * z + 2.0 * q[:, 8] * z
        + q[:, 9]
    )


def _pack_planes(planes: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Outer product of each plane with itself, packed upper-triangular."""
    a, b, c, d = planes[:, 0], planes[:, 1], planes[:, 2], planes[:, 3]
    return weights[:, None] * np.column_stack([
        a * a, a * b, a * c, a * d,
        b * b, b * c, b * d,
        c * c, c * d,
        d * d,
    ])


def _unpack_system(q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Split packed quadrics into the 3x3 normal matrix and the rhs vector."""
    n = len(q)
    a = np.empty((n, 3, 3), dtype=np.float64)
    a[:, 0, 0] = q[:, 0]
    a[:, 0, 1] = a[:, 1, 0] = q[:, 1]
    a[:, 0, 2] = a[:, 2, 0] = q[:, 2]
    a[:, 1, 1] = q[:, 4]
    a[:, 1, 2] = a[:, 2, 1] = q[:, 5]
    a[:, 2, 2] = q[:, 7]
    return a, -q[:, [3, 6, 8]]


class QuadricSet:
    """Accumulated per-vertex quadrics with edge cost / optimal placement."""

    __slots__ = ("q", "verts")

    def __init__(self, q: np.ndarray, verts: np.ndarray):
        self.q = q
        self.verts = verts

    # ── construction ────────────────────────────────────────────────────────

    @classmethod
    def from_mesh(cls, mesh, boundary_weight: float = BOUNDARY_WEIGHT) -> "QuadricSet":
        """Build quadrics from a ``HalfEdgeMesh`` (area-weighted face planes)."""
        verts = mesh.verts
        faces = mesh.alive_faces()
        q = np.zeros((len(verts), 10), dtype=np.float64)
        if len(faces) == 0:
            return cls(q, verts)

        p0, p1, p2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
        cross = np.cross(p1 - p0, p2 - p0)
        length = np.linalg.norm(cross, axis=1)
        normals = cross / (length[:, None] + _EPS)
        planes = np.column_stack([normals, -np.einsum("ij,ij->i", normals, p0)])
        packed = _pack_planes(planes, 0.5 * length)

        for col in range(3):
            np.add.at(q, faces[:, col], packed)

        obj = cls(q, verts)
        if boundary_weight > 0.0:
            obj._add_boundary_constraints(mesh, boundary_weight)
        return obj

    def _add_boundary_constraints(self, mesh, weight: float) -> None:
        """Add a plane through each boundary edge, perpendicular to its face."""
        boundary = np.flatnonzero(mesh.he_twin < 0)
        if boundary.size == 0:
            return

        f_idx = boundary // 3
        keep = mesh.face_alive[f_idx]
        f_idx = f_idx[keep]
        corner = (boundary % 3)[keep]
        if f_idx.size == 0:
            return

        tri = mesh.faces[f_idx]
        rows = np.arange(len(tri))
        u = tri[rows, corner]
        v = tri[rows, (corner + 1) % 3]

        face_n = np.cross(
            self.verts[tri[:, 1]] - self.verts[tri[:, 0]],
            self.verts[tri[:, 2]] - self.verts[tri[:, 0]],
        )
        face_n /= np.linalg.norm(face_n, axis=1)[:, None] + _EPS

        edge = self.verts[v] - self.verts[u]
        plane_n = np.cross(edge, face_n)
        norm = np.linalg.norm(plane_n, axis=1)
        valid = norm > _EPS
        if not np.any(valid):
            return

        plane_n = plane_n[valid] / norm[valid, None]
        u, v, edge = u[valid], v[valid], edge[valid]
        planes = np.column_stack([
            plane_n, -np.einsum("ij,ij->i", plane_n, self.verts[u])
        ])
        packed = _pack_planes(planes, weight * np.einsum("ij,ij->i", edge, edge))
        np.add.at(self.q, u, packed)
        np.add.at(self.q, v, packed)

    # ── queries ─────────────────────────────────────────────────────────────

    def edge_costs(self, edges: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Vectorised ``(cost, optimal_position)`` for many edges at once."""
        edges = np.asarray(edges, dtype=np.int64)
        if len(edges) == 0:
            return np.zeros(0), np.zeros((0, 3))

        u, v = edges[:, 0], edges[:, 1]
        q = self.q[u] + self.q[v]
        matrix, rhs = _unpack_system(q)

        scale = np.maximum(np.abs(matrix).reshape(len(q), -1).max(axis=1), _EPS)
        solvable = np.abs(np.linalg.det(matrix / scale[:, None, None])) > _SINGULAR_TOL

        pos = 0.5 * (self.verts[u] + self.verts[v])
        if np.any(solvable):
            rhs_s = rhs[solvable]
            mat_s = matrix[solvable]
            try:
                sol = np.linalg.solve(mat_s, rhs_s[:, :, None]).squeeze(-1)
            except ValueError:
                sol = np.stack([np.linalg.solve(mat_s[i], rhs_s[i]) for i in range(len(rhs_s))])
            pos[solvable] = sol

        fallback = ~solvable
        if np.any(fallback):
            idx = np.flatnonzero(fallback)
            options = np.stack(
                [pos[idx], self.verts[u[idx]], self.verts[v[idx]]], axis=1
            )
            errors = np.stack(
                [quadric_error(q[idx], options[:, k]) for k in range(3)], axis=1
            )
            pos[idx] = options[np.arange(len(idx)), np.argmin(errors, axis=1)]

        return np.maximum(quadric_error(q, pos), 0.0), pos

    def edge_cost(self, u: int, v: int) -> tuple[float, np.ndarray]:
        cost, pos = self.edge_costs(np.array([[u, v]], dtype=np.int64))
        return float(cost[0]), pos[0]

    def merge(self, removed: int, survivor: int) -> None:
        """Fold ``removed``'s quadric into ``survivor`` after a collapse (§41)."""
        self.q[survivor] += self.q[removed]
        self.q[removed] = 0.0
