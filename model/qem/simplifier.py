"""qem/simplifier.py — topology-constrained staged edge-collapse simplifier (§41).

The loop is the classical lazy-deletion greedy contraction:

    seed a min-heap with every edge's cost
    pop the cheapest, skip stale entries
    validate against the hard constraints (§42)
    collapse, merge quadrics, re-push only the survivor's incident edges

Staged inference (§40): the reduction is split into ``stages`` tranches.  At
each boundary the quadrics, boundary mask and importance provider are rebuilt
against the *current* topology, because importance predicted on the original
mesh is stale once edges have gone.  ``stages=1`` is the one-shot control arm
for the §125 experiment.
"""

from __future__ import annotations

import dataclasses
import heapq
import logging
import time

import numpy as np

from ..core.config import BOUNDARY_QUADRIC_WEIGHT, STAGES
from ..geometry.halfedge import HalfEdgeMesh
from ..geometry.quadric import QuadricSet
from .constraints import CollapseValidator, ConstraintConfig
from .cost import CostConfig, CostModel, ImportanceProvider, make_provider

logger = logging.getLogger(__name__)

_ITERATION_BUDGET = 40


@dataclasses.dataclass
class SimplifyResult:
    vertices: np.ndarray
    faces: np.ndarray
    original_faces: int
    target_faces: int
    collapses: int
    stages: int
    rejected: dict
    timings: dict[str, float]
    records: list[dict]

    @property
    def face_count(self) -> int:
        return len(self.faces)

    @property
    def compression(self) -> float:
        if self.original_faces == 0:
            return 0.0
        return 1.0 - self.face_count / self.original_faces


def _boundary_mask(mesh: HalfEdgeMesh) -> np.ndarray:
    """Vectorised per-vertex boundary flag from the twin array."""
    mask = np.zeros(len(mesh.verts), dtype=bool)
    half_edges = np.flatnonzero(mesh.he_twin < 0)
    if half_edges.size == 0:
        return mask
    face = half_edges // 3
    keep = mesh.face_alive[face]
    face, corner = face[keep], (half_edges % 3)[keep]
    if face.size == 0:
        return mask
    tri = mesh.faces[face]
    rows = np.arange(len(tri))
    mask[tri[rows, corner]] = True
    mask[tri[rows, (corner + 1) % 3]] = True
    return mask


def _directions(
    edges: np.ndarray, boundary: np.ndarray, importance: np.ndarray | None
) -> tuple[np.ndarray, np.ndarray]:
    """Pick which endpoint dies, vectorised and deterministic.

    Priority: never remove a boundary vertex in favour of an interior one, then
    remove the less important endpoint, then remove the higher index.
    """
    u, v = edges[:, 0], edges[:, 1]
    remove_u = u > v
    if importance is not None:
        delta = importance[u] - importance[v]
        remove_u = np.where(delta != 0.0, delta < 0.0, remove_u)
    on_border_u, on_border_v = boundary[u], boundary[v]
    remove_u = np.where(on_border_u != on_border_v, on_border_v, remove_u)
    return np.where(remove_u, u, v), np.where(remove_u, v, u)


def _stage_targets(original: int, target: int, stages: int) -> list[int]:
    to_remove = max(original - target, 0)
    return [
        original - int(round(to_remove * (i + 1) / stages)) for i in range(stages)
    ]


def simplify(
    vertices: np.ndarray,
    faces: np.ndarray,
    target_faces: int,
    *,
    method: str = "qem",
    provider: ImportanceProvider | None = None,
    cost_config: CostConfig | None = None,
    constraint_config: ConstraintConfig | None = None,
    stages: int | None = None,
    protected: set[tuple[int, int]] | None = None,
    record: bool = False,
    model_path=None,
) -> SimplifyResult:
    """Reduce a triangle mesh to ``target_faces`` under hard topology constraints."""
    started = time.perf_counter()
    timings = {"preprocessing": 0.0, "importance": 0.0, "qem": 0.0, "total": 0.0}

    mesh = HalfEdgeMesh(vertices, faces)
    original_faces = mesh.n_faces
    target = int(max(4, min(int(target_faces), original_faces)))

    if provider is None:
        provider = make_provider(method, len(mesh.verts), model_path=model_path)
    if cost_config is None:
        cost_config = CostConfig(random_cost=(method == "random"))
    constraint_config = constraint_config or ConstraintConfig()
    stages = max(1, int(STAGES if stages is None else stages))
    if provider is None:
        stages = 1

    validator = CollapseValidator(mesh, constraint_config, protected)
    collapses = 0
    records: list[dict] = []

    for stage_index, stage_target in enumerate(_stage_targets(original_faces, target, stages)):
        if mesh.n_faces <= stage_target:
            continue

        mark = time.perf_counter()
        quadrics = QuadricSet.from_mesh(mesh, BOUNDARY_QUADRIC_WEIGHT)
        boundary = _boundary_mask(mesh)
        validator.boundary = boundary
        edges = mesh.unique_edges()
        timings["preprocessing"] += time.perf_counter() - mark

        if provider is not None:
            mark = time.perf_counter()
            provider.refresh(mesh)
            validator.protected |= provider.protected_edges(mesh)
            timings["importance"] += time.perf_counter() - mark

        mark = time.perf_counter()
        cost_model = CostModel(quadrics, provider, cost_config)
        cost_model.calibrate(edges)
        heap, version, stamp = _seed_heap(edges, cost_model, boundary, provider)

        budget = _ITERATION_BUDGET * max(len(edges), 1)
        iterations = 0

        while mesh.n_faces > stage_target and heap:
            iterations += 1
            if iterations > budget:
                logger.warning(
                    "Stage %d hit the iteration budget at %d faces (target %d)",
                    stage_index, mesh.n_faces, stage_target,
                )
                break

            entry = heapq.heappop(heap)
            final_cost, entry_stamp, removed, survivor = entry[:4]
            key = (min(removed, survivor), max(removed, survivor))
            if version.get(key) != entry_stamp:
                continue
            if not (mesh.vert_alive[removed] and mesh.vert_alive[survivor]):
                version.pop(key, None)
                continue

            position = np.array(entry[4:7], dtype=np.float64)
            ok, reason = validator.check(removed, survivor, position)
            if not ok:
                version.pop(key, None)
                continue

            if record:
                records.append(
                    _record(mesh, removed, survivor, final_cost, entry[7], entry[8], stage_index)
                )

            mesh.collapse(removed, survivor, position)
            quadrics.merge(removed, survivor)
            collapses += 1
            version.pop(key, None)

            stamp = _repush(
                mesh, survivor, boundary, cost_model, provider, heap, version, stamp
            )

        timings["qem"] += time.perf_counter() - mark

    if provider is not None:
        timings["importance"] = max(timings["importance"], provider.inference_seconds)

    out_verts, out_faces, _ = mesh.compact()
    timings["total"] = time.perf_counter() - started

    return SimplifyResult(
        vertices=out_verts,
        faces=out_faces,
        original_faces=original_faces,
        target_faces=target,
        collapses=collapses,
        stages=stages,
        rejected=validator.summary(),
        timings={k: round(v, 6) for k, v in timings.items()},
        records=records,
    )


def _seed_heap(
    edges: np.ndarray,
    cost_model: CostModel,
    boundary: np.ndarray,
    provider: ImportanceProvider | None,
) -> tuple[list, dict, int]:
    """Build the initial heap; entries carry their cached placement and terms."""
    if len(edges) == 0:
        return [], {}, 0

    costs, positions, qem, importance = cost_model.evaluate(edges)
    removed, survivor = _directions(
        edges, boundary, provider.vertex_importance if provider else None
    )
    stamps = np.arange(1, len(edges) + 1, dtype=np.int64)

    heap = list(zip(
        costs.tolist(), stamps.tolist(), removed.tolist(), survivor.tolist(),
        positions[:, 0].tolist(), positions[:, 1].tolist(), positions[:, 2].tolist(),
        qem.tolist(), importance.tolist(),
    ))
    heapq.heapify(heap)
    version = dict(zip(map(tuple, edges.tolist()), stamps.tolist()))
    return heap, version, int(stamps[-1])


def _repush(
    mesh: HalfEdgeMesh,
    survivor: int,
    boundary: np.ndarray,
    cost_model: CostModel,
    provider: ImportanceProvider | None,
    heap: list,
    version: dict,
    stamp: int,
) -> int:
    """Refresh only the edges the collapse actually invalidated (§41)."""
    ring = sorted(mesh.one_ring(survivor))
    if not ring:
        return stamp

    boundary[survivor] = mesh.is_boundary_vertex(survivor)
    for w in ring:
        boundary[w] = mesh.is_boundary_vertex(w)

    edges = np.column_stack([
        np.minimum(survivor, ring), np.maximum(survivor, ring)
    ]).astype(np.int64)
    costs, positions, qem, importance = cost_model.evaluate(edges)
    removed, keep = _directions(
        edges, boundary, provider.vertex_importance if provider else None
    )

    for i in range(len(edges)):
        stamp += 1
        version[(int(edges[i, 0]), int(edges[i, 1]))] = stamp
        heapq.heappush(heap, (
            float(costs[i]), stamp, int(removed[i]), int(keep[i]),
            float(positions[i, 0]), float(positions[i, 1]), float(positions[i, 2]),
            float(qem[i]), float(importance[i]),
        ))
    return stamp


def _record(
    mesh: HalfEdgeMesh,
    removed: int,
    survivor: int,
    final_cost: float,
    qem: float,
    importance: float,
    stage: int,
) -> dict:
    """Explainability row for one collapse (§78)."""
    link = mesh.edge_faces(removed, survivor)
    dihedral = 0.0
    if len(link) >= 2:
        n1 = mesh.face_normal(link[0])
        n2 = mesh.face_normal(link[1])
        dihedral = float(np.arccos(np.clip(np.dot(n1, n2), -1.0, 1.0)))
    return {
        "edge": [int(removed), int(survivor)],
        "stage": int(stage),
        "qem_cost": round(float(qem), 8),
        "predicted_importance": round(float(importance), 6),
        "final_cost": round(float(final_cost), 8),
        "dihedral": round(dihedral, 6),
        "boundary": bool(len(link) < 2),
        "reason": "low structural importance" if importance < 0.5 else "geometrically cheap",
    }
