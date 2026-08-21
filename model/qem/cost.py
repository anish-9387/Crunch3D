"""qem/cost.py — AI-modulated QEM cost (§38, Eq. 2).

QEM stays responsible for geometric placement and error; the learned or
handcrafted importance only re-prioritises which admissible collapse happens
first.  Two combination forms are supported:

    multiplicative   cost = QEM(e) · (1 + κ · I(e))          crunch3d-v2 Eq. 5
    additive         cost = QEM(e)/QEM_p95 + λ · I(e)        §38 stable form

Importance is stored per *vertex*, indexed by the original vertex id, because
half-edge collapses create edges that did not exist at prediction time.  Edge
importance is then the aggregate of its endpoints (``max`` by default, matching
crunch3d-v2 Eq. 5).
"""

from __future__ import annotations

import dataclasses
import logging

import numpy as np

from ..core.config import (
    COST_LAMBDA,
    COST_MODE,
    IMPORTANCE_AGGREGATE,
    KAPPA,
)

logger = logging.getLogger(__name__)

_EPS = 1e-12


@dataclasses.dataclass
class CostConfig:
    kappa: float = KAPPA
    mode: str = COST_MODE
    lambda_add: float = COST_LAMBDA
    aggregate: str = IMPORTANCE_AGGREGATE
    random_cost: bool = False
    """Baseline 1 (§45): ignore geometry entirely and collapse at random."""
    seed: int = 42


# ---------------------------------------------------------------------------
# Importance providers
# ---------------------------------------------------------------------------


class ImportanceProvider:
    """Per-vertex importance with a staged-inference refresh hook (§40)."""

    name = "uniform"

    def __init__(self, n_verts: int):
        self.vertex_importance = np.zeros(n_verts, dtype=np.float64)
        self.inference_seconds = 0.0

    def refresh(self, mesh) -> None:
        """Recompute importance for the current topology.  Called per stage."""

    def edge_importance(self, edges: np.ndarray, aggregate: str = "max") -> np.ndarray:
        if len(edges) == 0:
            return np.zeros(0, dtype=np.float64)
        a = self.vertex_importance[edges[:, 0]]
        b = self.vertex_importance[edges[:, 1]]
        return np.maximum(a, b) if aggregate == "max" else 0.5 * (a + b)

    def protected_edges(self, mesh) -> set[tuple[int, int]]:
        """Edges the hard-constraint layer must refuse outright (§44)."""
        return set()


class HeuristicImportance(ImportanceProvider):
    """Baseline 3 (§45): handcrafted cue fusion, no learning.

    Reuses the shipped heuristics rather than re-deriving them, so the baseline
    and the production pipeline cannot silently diverge.
    """

    name = "heuristic"

    def __init__(self, n_verts: int, use_edge_features: bool = True):
        super().__init__(n_verts)
        self.use_edge_features = use_edge_features

    def refresh(self, mesh) -> None:
        import time

        from ..importance.edge_features import (
            compute_edge_feature_importance,
            scatter_to_vertices,
        )
        from ..importance.importance_mapper import compute_importance

        start = time.perf_counter()
        sub, remap = _submesh(mesh)
        if sub is None:
            return

        importance = compute_importance(sub)
        if self.use_edge_features:
            result = compute_edge_feature_importance(sub, vertex_importance=importance)
            edge_map = scatter_to_vertices(result, len(sub.vertices))
            importance = np.clip(np.maximum(importance, edge_map), 0.0, 1.0)

        self.vertex_importance[:] = 0.0
        alive = remap >= 0
        self.vertex_importance[alive] = importance[remap[alive]]
        self.inference_seconds += time.perf_counter() - start


class LearnedImportance(ImportanceProvider):
    """Baseline 4 (§45): GNN edge-importance predictor, re-run per stage."""

    name = "learned"

    def __init__(self, n_verts: int, model_path=None, tiers=("A", "B")):
        super().__init__(n_verts)
        self.model_path = model_path
        self.tiers = tiers
        self._safety_flags: dict[int, bool] = {}

    def refresh(self, mesh) -> None:
        import time

        start = time.perf_counter()
        sub, remap = _submesh(mesh)
        if sub is None:
            return

        try:
            from ..ml.model import predict_edge_importance

            edges, scores = predict_edge_importance(
                sub, model_path=self.model_path, tiers=self.tiers
            )
        except Exception:
            try:
                from ..learning.inference import predict_edge_importance as _legacy

                scores = _legacy(sub, model_path=self.model_path)
                edges = sub.edges_unique if hasattr(sub, "edges_unique") else np.zeros((0, 2), dtype=np.int64)
                if len(scores) != len(edges) and len(edges):
                    scores = np.full(len(edges), 0.5, dtype=np.float64)
            except Exception:
                return

        local = np.zeros(len(sub.vertices), dtype=np.float64)
        if len(edges):
            scores = np.asarray(scores, dtype=np.float64)
            np.maximum.at(local, np.asarray(edges, dtype=np.int64)[:, 0], scores)
            np.maximum.at(local, np.asarray(edges, dtype=np.int64)[:, 1], scores)

        self.vertex_importance[:] = 0.0
        alive = remap >= 0
        self.vertex_importance[alive] = local[remap[alive]]
        self.inference_seconds += time.perf_counter() - start


def _submesh(mesh):
    """Compact a HalfEdgeMesh into a Trimesh plus an original→local index map."""
    import trimesh

    verts, faces, remap = mesh.compact()
    if len(faces) == 0:
        return None, remap
    return trimesh.Trimesh(vertices=verts, faces=faces, process=False), remap


# ---------------------------------------------------------------------------
# Cost model
# ---------------------------------------------------------------------------


class CostModel:
    """Combines quadric error with importance into the collapse priority."""

    __slots__ = ("quadrics", "provider", "config", "_qem_scale", "_rng")

    def __init__(self, quadrics, provider: ImportanceProvider | None, config: CostConfig):
        self.quadrics = quadrics
        self.provider = provider
        self.config = config
        self._qem_scale = 1.0
        self._rng = np.random.default_rng(config.seed)

    def calibrate(self, edges: np.ndarray) -> None:
        """Fix the QEM normaliser once per stage so additive mode is stable."""
        if self.config.mode != "additive" or len(edges) == 0:
            return
        qem, _ = self.quadrics.edge_costs(edges)
        self._qem_scale = max(float(np.percentile(qem, 95)), _EPS)

    def evaluate(self, edges: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return ``(cost, position, qem, importance)`` for each edge."""
        edges = np.asarray(edges, dtype=np.int64).reshape(-1, 2)
        if len(edges) == 0:
            empty = np.zeros(0, dtype=np.float64)
            return empty, np.zeros((0, 3)), empty, empty

        qem, pos = self.quadrics.edge_costs(edges)

        if self.provider is None:
            importance = np.zeros(len(edges), dtype=np.float64)
        else:
            importance = self.provider.edge_importance(edges, self.config.aggregate)

        if self.config.random_cost:
            return self._rng.random(len(edges)), pos, qem, importance

        if self.config.mode == "additive":
            cost = qem / self._qem_scale + self.config.lambda_add * importance
        else:
            cost = qem * (1.0 + self.config.kappa * importance)

        return cost, pos, qem, importance


def make_provider(method: str, n_verts: int, model_path=None) -> ImportanceProvider | None:
    """Provider for one of the §45 baseline methods."""
    if method in ("qem", "random"):
        return None
    if method == "heuristic":
        return HeuristicImportance(n_verts)
    if method in ("crunch3d", "learned"):
        return LearnedImportance(n_verts, model_path=model_path)
    raise ValueError(f"Unknown method: {method!r}")
