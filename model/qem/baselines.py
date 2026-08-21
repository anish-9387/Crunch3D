"""qem/baselines.py — the §45 baseline ladder behind one entry point.

Every method except ``pymeshlab`` runs through the *same* half-edge simplifier,
validator and heap, so a difference in the results can only come from the
collapse ordering — which is the whole point of the comparison.

    random     Baseline 1 — sanity check: random valid collapse order
    qem        Baseline 2 — pure Garland-Heckbert quadric error
    heuristic  Baseline 3 — QEM modulated by the handcrafted cue fusion
    crunch3d   Baseline 4 — QEM modulated by the learned GNN importance
    pymeshlab  the shipped production engine, for reference
"""

from __future__ import annotations

import logging
import time

import numpy as np

from ..core.config import STAGES
from .constraints import ConstraintConfig
from .cost import CostConfig
from .simplifier import SimplifyResult, simplify

logger = logging.getLogger(__name__)

METHODS = ("random", "qem", "heuristic", "crunch3d", "pymeshlab")


def simplify_mesh(
    mesh,
    target_faces: int,
    method: str = "qem",
    *,
    stages: int | None = None,
    model_path=None,
    record: bool = False,
    cost_config: CostConfig | None = None,
    constraint_config: ConstraintConfig | None = None,
) -> SimplifyResult:
    """Simplify a Trimesh with one of the §45 methods."""
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}, got {method!r}")

    if method == "pymeshlab":
        return _pymeshlab(mesh, target_faces)

    if stages is None:
        stages = STAGES if method == "crunch3d" else 1

    return simplify(
        np.asarray(mesh.vertices, dtype=np.float64),
        np.asarray(mesh.faces, dtype=np.int64),
        target_faces,
        method=method,
        stages=stages,
        model_path=model_path,
        record=record,
        cost_config=cost_config,
        constraint_config=constraint_config,
    )


def _pymeshlab(mesh, target_faces: int) -> SimplifyResult:
    """Wrap the production PyMeshLab path in the shared result shape."""
    from ..engine.mesh_optimizer import _decimate_component

    started = time.perf_counter()
    original_faces = len(mesh.faces)
    result = _decimate_component(
        mesh=mesh,
        target_faces=int(target_faces),
        preserve_normals=True,
        preserve_boundaries=True,
        use_importance=False,
    )
    elapsed = time.perf_counter() - started

    if result is None:
        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        faces = np.asarray(mesh.faces, dtype=np.int64)
    else:
        vertices = np.asarray(result.vertices, dtype=np.float64)
        faces = np.asarray(result.faces, dtype=np.int64)

    return SimplifyResult(
        vertices=vertices,
        faces=faces,
        original_faces=original_faces,
        target_faces=int(target_faces),
        collapses=max(original_faces - len(faces), 0) // 2,
        stages=1,
        rejected={"total": 0, "by_reason": {}},
        timings={
            "preprocessing": 0.0,
            "importance": 0.0,
            "qem": round(elapsed, 6),
            "total": round(elapsed, 6),
        },
        records=[],
    )
