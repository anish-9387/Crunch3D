"""geometry/halfedge.py — array-backed half-edge triangle mesh with local collapse.

Half-edge ``h`` is corner ``h % 3`` of face ``h // 3`` and runs from
``faces[f, i]`` to ``faces[f, (i + 1) % 3]``.  ``next``, ``prev`` and ``face``
are therefore arithmetic and only ``twin`` needs storage.

Collapses mutate in place: the 1-2 link faces are marked dead, the surviving
faces of the removed vertex are retargeted, and twins are repaired over the
touched neighbourhood only.  Cost is O(valence), never O(V).
"""

from __future__ import annotations

import numpy as np

_AREA_EPS = 1e-14


def _pair_twins(keys: np.ndarray, n_half_edges: int) -> np.ndarray:
    """Mutually pair half-edges sharing an undirected key; -1 when unpaired."""
    twin = np.full(n_half_edges, -1, dtype=np.int64)
    if n_half_edges == 0:
        return twin

    order = np.argsort(keys, kind="stable")
    sorted_keys = keys[order]
    group_start = np.flatnonzero(
        np.concatenate(([True], sorted_keys[1:] != sorted_keys[:-1]))
    )
    group_len = np.diff(np.concatenate((group_start, [len(sorted_keys)])))

    offset = 0
    while True:
        pairable = group_len > offset + 1
        if not np.any(pairable):
            break
        starts = group_start[pairable] + offset
        a = order[starts]
        b = order[starts + 1]
        twin[a] = b
        twin[b] = a
        offset += 2
    return twin


class HalfEdgeMesh:
    """Mutable triangle mesh with O(1)-style local adjacency queries."""

    __slots__ = (
        "verts", "faces", "face_alive", "vert_alive", "vertex_faces",
        "he_twin", "_faces_alive", "_verts_alive",
    )

    # ── construction ────────────────────────────────────────────────────────

    def __init__(self, verts: np.ndarray, faces: np.ndarray):
        self.verts = np.array(verts, dtype=np.float64, copy=True, order="C")
        self.faces = np.array(faces, dtype=np.int64, copy=True, order="C")
        n_verts = len(self.verts)
        n_faces = len(self.faces)

        self.face_alive = np.ones(n_faces, dtype=bool)
        self.vert_alive = np.zeros(n_verts, dtype=bool)
        if n_faces:
            self.vert_alive[np.unique(self.faces)] = True

        self.vertex_faces = self._build_vertex_faces(self.faces, n_verts)
        self.he_twin = _pair_twins(self._edge_keys(self.faces, n_verts), 3 * n_faces)
        self._faces_alive = int(n_faces)
        self._verts_alive = int(self.vert_alive.sum())

    @classmethod
    def from_trimesh(cls, mesh) -> "HalfEdgeMesh":
        return cls(np.asarray(mesh.vertices), np.asarray(mesh.faces))

    @staticmethod
    def _build_vertex_faces(faces: np.ndarray, n_verts: int) -> list[set[int]]:
        if len(faces) == 0:
            return [set() for _ in range(n_verts)]
        flat_v = faces.ravel()
        flat_f = np.repeat(np.arange(len(faces), dtype=np.int64), 3)
        order = np.argsort(flat_v, kind="stable")
        sorted_v = flat_v[order]
        sorted_f = flat_f[order]
        lo = np.searchsorted(sorted_v, np.arange(n_verts), side="left")
        hi = np.searchsorted(sorted_v, np.arange(n_verts), side="right")
        return [set(sorted_f[a:b].tolist()) for a, b in zip(lo, hi)]

    @staticmethod
    def _edge_keys(faces: np.ndarray, n_verts: int) -> np.ndarray:
        """Undirected key per half-edge, in half-edge index order."""
        if len(faces) == 0:
            return np.zeros(0, dtype=np.int64)
        src = faces
        dst = faces[:, [1, 2, 0]]
        lo = np.minimum(src, dst).ravel()
        hi = np.maximum(src, dst).ravel()
        return lo * np.int64(n_verts) + hi

    # ── half-edge navigation (§6) ───────────────────────────────────────────

    @staticmethod
    def next_he(h: int) -> int:
        f, i = divmod(h, 3)
        return 3 * f + (i + 1) % 3

    @staticmethod
    def prev_he(h: int) -> int:
        f, i = divmod(h, 3)
        return 3 * f + (i + 2) % 3

    @staticmethod
    def face_of(h: int) -> int:
        return h // 3

    def twin(self, h: int) -> int:
        return int(self.he_twin[h])

    def origin(self, h: int) -> int:
        f, i = divmod(h, 3)
        return int(self.faces[f, i])

    def dest(self, h: int) -> int:
        f, i = divmod(h, 3)
        return int(self.faces[f, (i + 1) % 3])

    # ── local adjacency ─────────────────────────────────────────────────────

    def vertex_face_list(self, v: int) -> list[int]:
        return [f for f in self.vertex_faces[v] if self.face_alive[f]]

    def one_ring(self, v: int) -> set[int]:
        ring: set[int] = set()
        for f in self.vertex_faces[v]:
            if self.face_alive[f]:
                ring.update(int(x) for x in self.faces[f])
        ring.discard(v)
        return ring

    def edge_faces(self, u: int, v: int) -> list[int]:
        smaller, larger = (
            (self.vertex_faces[u], v) if len(self.vertex_faces[u]) <= len(self.vertex_faces[v])
            else (self.vertex_faces[v], u)
        )
        return [
            f for f in smaller
            if self.face_alive[f] and larger in self.faces[f]
        ]

    def valence(self, v: int) -> int:
        return len(self.one_ring(v))

    def is_boundary_edge(self, u: int, v: int) -> bool:
        return len(self.edge_faces(u, v)) < 2

    def is_boundary_vertex(self, v: int) -> bool:
        for w in self.one_ring(v):
            if len(self.edge_faces(v, w)) < 2:
                return True
        return False

    # ── geometry of alive faces ─────────────────────────────────────────────

    def face_normal(self, f: int, override: dict[int, np.ndarray] | None = None) -> np.ndarray:
        a, b, c = (int(x) for x in self.faces[f])
        get = (lambda i: override[i] if override and i in override else self.verts[i])
        n = np.cross(get(b) - get(a), get(c) - get(a))
        norm = float(np.linalg.norm(n))
        return n / norm if norm > _AREA_EPS else np.zeros(3)

    def face_area(self, f: int, override: dict[int, np.ndarray] | None = None) -> float:
        a, b, c = (int(x) for x in self.faces[f])
        get = (lambda i: override[i] if override and i in override else self.verts[i])
        return 0.5 * float(np.linalg.norm(np.cross(get(b) - get(a), get(c) - get(a))))

    def alive_faces(self) -> np.ndarray:
        return self.faces[self.face_alive]

    def unique_edges(self) -> np.ndarray:
        """Sorted ``(E, 2)`` unique undirected edges over alive faces."""
        faces = self.alive_faces()
        if len(faces) == 0:
            return np.zeros((0, 2), dtype=np.int64)
        src = faces.ravel()
        dst = faces[:, [1, 2, 0]].ravel()
        lo = np.minimum(src, dst)
        hi = np.maximum(src, dst)
        return np.unique(np.column_stack((lo, hi)), axis=0)

    @property
    def n_faces(self) -> int:
        return self._faces_alive

    @property
    def n_verts(self) -> int:
        return self._verts_alive

    def bbox_diagonal(self) -> float:
        if not np.any(self.vert_alive):
            return 0.0
        live = self.verts[self.vert_alive]
        return float(np.linalg.norm(live.max(axis=0) - live.min(axis=0)))

    # ── mutation ────────────────────────────────────────────────────────────

    def collapse(self, u: int, v: int, new_pos: np.ndarray) -> bool:
        """Collapse ``u`` into ``v``, placing ``v`` at ``new_pos``.

        Returns False when the edge is already gone.  Callers are expected to
        have validated the collapse (see ``qem.constraints``); this method only
        guards against structurally impossible input.
        """
        u, v = int(u), int(v)
        if u == v or not (self.vert_alive[u] and self.vert_alive[v]):
            return False

        link = self.edge_faces(u, v)
        if not link:
            return False

        for f in link:
            self._kill_face(f)

        for f in list(self.vertex_faces[u]):
            if not self.face_alive[f]:
                continue
            tri = self.faces[f]
            tri[tri == u] = v
            if len(np.unique(tri)) < 3:
                self._kill_face(f)
            else:
                self.vertex_faces[v].add(f)

        self.vertex_faces[u].clear()
        self.vert_alive[u] = False
        self._verts_alive -= 1
        self.verts[v] = new_pos

        if not self.vertex_face_list(v):
            self.vert_alive[v] = False
            self._verts_alive -= 1
            return True

        self._repair_twins_around(v)
        return True

    def _kill_face(self, f: int) -> None:
        if not self.face_alive[f]:
            return
        self.face_alive[f] = False
        self._faces_alive -= 1
        for w in self.faces[f]:
            self.vertex_faces[int(w)].discard(f)

    def _repair_twins_around(self, v: int) -> None:
        """Rebuild twins for every half-edge of a face incident to ``v``.

        The candidate set (faces of ``v`` plus faces of its 1-ring) is closed
        under the twin relation for those half-edges, so no stale pointer can
        survive outside it.
        """
        faces_v = self.vertex_face_list(v)
        if not faces_v:
            return

        ring: set[int] = {v}
        for f in faces_v:
            ring.update(int(x) for x in self.faces[f])

        candidates: set[int] = set()
        for w in ring:
            candidates.update(f for f in self.vertex_faces[w] if self.face_alive[f])

        lookup: dict[tuple[int, int], list[int]] = {}
        for f in candidates:
            tri = self.faces[f]
            for i in range(3):
                a, b = int(tri[i]), int(tri[(i + 1) % 3])
                lookup.setdefault((min(a, b), max(a, b)), []).append(3 * f + i)

        for f in faces_v:
            tri = self.faces[f]
            for i in range(3):
                h = 3 * f + i
                a, b = int(tri[i]), int(tri[(i + 1) % 3])
                partners = [g for g in lookup[(min(a, b), max(a, b))] if g != h]
                partner = partners[0] if partners else -1
                self.he_twin[h] = partner
                if partner >= 0:
                    self.he_twin[partner] = h

    # ── export ──────────────────────────────────────────────────────────────

    def compact(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return ``(verts, faces, vertex_map)`` with dead elements dropped."""
        faces = self.alive_faces()
        if len(faces) == 0:
            return (
                np.zeros((0, 3), dtype=np.float64),
                np.zeros((0, 3), dtype=np.int64),
                np.full(len(self.verts), -1, dtype=np.int64),
            )
        used = np.unique(faces)
        remap = np.full(len(self.verts), -1, dtype=np.int64)
        remap[used] = np.arange(len(used), dtype=np.int64)
        return self.verts[used].copy(), remap[faces], remap

    def to_trimesh(self):
        import trimesh

        verts, faces, _ = self.compact()
        return trimesh.Trimesh(vertices=verts, faces=faces, process=False)
