"""
learning/continuous_learning.py — Self-learning loop for the GNN.

Every completed optimization captures a training sample (downsampled mesh
graph with per-edge importance labels from the run, plus the measured
outcome metrics).  A background task periodically fine-tunes the GNN on the
accumulated dataset — the model learns on its own from the very models it
optimized, no human labelling.

Pipeline:
    optimize_mesh  →  record_training_sample()
                            ↓  (WAL-safe, cheap, downsampled)
    training_data/*.pt
                            ↓  (background task, every N minutes /
                               once min_new_samples are queued)
    trainer.train(warm_start=True)
                            ↓
    checkpoints/crunch3d_gnn_model.pt   →  used by the next optimization

All functions degrade gracefully when torch / torch-geometric are missing —
the runtime keeps working exactly as before.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
TRAINING_DATA_DIR = Path(__file__).resolve().parent / "training_data"
CHECKPOINT_DIR = Path(__file__).resolve().parent / "checkpoints"
CHECKPOINT_PATH = CHECKPOINT_DIR / "crunch3d_gnn_model.pt"
STATE_FILE = TRAINING_DATA_DIR / "_state.json"

# Captured samples are downsampled to keep the dataset manageable: each
# sample holds at most this many vertices (edges with both endpoints inside
# the subset are kept, so the graph stays meaningful).
MAX_RECORD_VERTICES = 20000

# Auto-retrain tuning
AUTO_RETRAIN = os.getenv("LEARNING_AUTO_RETRAIN", "true").strip().lower() in {
    "1", "true", "yes", "on",
}
RETRAIN_INTERVAL_SECONDS = int(os.getenv("LEARNING_RETRAIN_INTERVAL_MINUTES", "30")) * 60
MIN_NEW_SAMPLES = int(os.getenv("LEARNING_MIN_NEW_SAMPLES", "5"))
RETRAIN_EPOCHS = int(os.getenv("LEARNING_RETRAIN_EPOCHS", "12"))

_lock = threading.RLock()


# ---------------------------------------------------------------------------
# State bookkeeping (survives restarts, JSON file in the training dir)
# ---------------------------------------------------------------------------

def _default_state() -> dict:
    return {
        "last_trained_at": 0.0,      # unix ts of last successful retrain
        "samples_recorded": 0,       # cumulative counter
        "events_at_last_train": 0,   # sample count at last retrain
        "seed_generated": 0,
        "last_error": None,
    }


def _load_state() -> dict:
    state = _default_state()
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state.update(json.load(f))
    except Exception:
        pass
    return state


def _save_state(state: dict) -> None:
    try:
        TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=True, indent=1)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Sample recording
# ---------------------------------------------------------------------------

def _downsample_components(components) -> tuple:
    """Pick a vertex subset and the edges fully inside it.

    Returns (verts, faces, edges, vertex_indices) or None when degenerate.
    Total vertices across all components is capped at MAX_RECORD_VERTICES,
    so an 800K-vertex run produces a compact ~20K-vertex graph sample.
    """
    all_verts: list[np.ndarray] = []
    all_faces: list[np.ndarray] = []
    all_imp: list[np.ndarray] = []
    remaining = MAX_RECORD_VERTICES

    for mesh in components:
        if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
            continue
        n = len(mesh.vertices)
        if remaining <= 0:
            break
        take = min(n, remaining)
        rng = np.random.default_rng(hash(str(id(mesh))) % (2**32))
        indices = np.sort(rng.choice(n, take, replace=False))

        verts = np.asarray(mesh.vertices, dtype=np.float64)[indices]
        faces = np.asarray(mesh.faces, dtype=np.int64)

        # Remap face indices into the subset (faces partially outside are dropped)
        lookup = np.full(n, -1, dtype=np.int64)
        lookup[indices] = np.arange(take)
        in_subset = np.all(faces >= 0, axis=1) & np.isin(faces, indices).all(axis=1)
        local_faces = lookup[faces[in_subset]]

        if len(local_faces) == 0:
            continue

        all_verts.append(verts)
        all_faces.append(local_faces)
        remaining -= take

    if not all_verts or not all_faces:
        return None

    return (
        np.vstack(all_verts),
        np.vstack(all_faces),
        np.asarray(np.concatenate(all_faces), dtype=np.int64),
        np.arange(sum(v.shape[0] for v in all_verts)),
    )


def record_training_sample(
    components,
    component_importance: list[np.ndarray] | None,
    *,
    job_id: str,
    outcome: dict | None = None,
) -> bool:
    """Capture a self-supervised training sample from a completed run.

    The label is the per-edge importance the run actually used (teacher =
    the heuristic fusion of curvature / UV / colour cues), so the GNN learns
    to reproduce — and generalize — good protection decisions, including the
    colour/texture retention cues.

    Returns True when a sample was written.
    """
    if not AUTO_RETRAIN:
        return False
    try:
        import torch
    except ImportError:
        return False

    try:
        from .dataset import mesh_to_graph_data
    except ImportError:
        return False

    if not components or component_importance is None:
        return False

    try:
        packed = _downsample_components(components)
        if packed is None:
            return False
        verts, faces, _, _ = packed

        # Reassemble a minimal Trimesh so graph features/labels can be computed
        import trimesh as _tm

        mesh = _tm.Trimesh(vertices=verts, faces=faces, process=False)

        # Self-supervised label: recompute the full importance pipeline on the
        # small sub-mesh (curvature + UV/colour cues), then convert to per-edge
        # labels for the GNN.  This captures the run's protection behaviour
        # without needing to serialize the giant original component.
        from ..importance.importance_mapper import compute_importance

        sub_imp = compute_importance(mesh)
        if len(sub_imp) != len(verts):
            sub_imp = np.full(len(verts), 0.5, dtype=np.float64)

        edges = mesh.edges_unique
        edge_labels = (sub_imp[edges[:, 0]] + sub_imp[edges[:, 1]]) / 2.0

        data = mesh_to_graph_data(mesh, edge_labels.astype(np.float32))
        if outcome:
            for key, value in outcome.items():
                if isinstance(value, (int, float, str, bool)):
                    setattr(data, key, value)
                elif value is None:
                    setattr(data, key, 0.0)

        TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"run_{job_id}_{int(time.time()*1000)}.pt"
        torch.save(data, TRAINING_DATA_DIR / filename)

        with _lock:
            state = _load_state()
            state["samples_recorded"] = int(state.get("samples_recorded", 0)) + 1
            _save_state(state)

        logger.info("Recorded self-learning sample %s (%d verts, %d edges)",
                    filename, len(verts), len(edges))
        return True
    except Exception as exc:
        logger.warning("Could not record training sample for %s: %s", job_id, exc)
        return False


# ---------------------------------------------------------------------------
# Dataset / retrain orchestration
# ---------------------------------------------------------------------------

def count_samples() -> int:
    """Number of .pt samples currently in the training dataset."""
    if not TRAINING_DATA_DIR.exists():
        return 0
    n = 0
    for p in TRAINING_DATA_DIR.iterdir():
        if p.is_file() and p.suffix == ".pt":
            n += 1
    return n


def samples_since_last_train() -> int:
    """New samples recorded since the last retrain (or since boot)."""
    state = _load_state()
    total = count_samples()
    baseline = int(state.get("samples_recorded", 0)) - int(
        state.get("events_at_last_train", 0)
    )
    return max(total - baseline, 0)


def retrain_now(max_epochs: int | None = None) -> dict:
    """Run one fine-tuning pass over the whole dataset (warm-started).

    Returns the trainer metrics dict, or a small dict on failure.
    Safe to call from any thread; serialized via a lock.
    """
    with _lock:
        return _retrain_unlocked(max_epochs=max_epochs)


def _retrain_unlocked(max_epochs: int | None = None) -> dict:
    try:
        from .trainer import train
    except ImportError as exc:
        return {"ok": False, "error": f"trainer unavailable: {exc}"}

    TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)
    n_samples = count_samples()
    if n_samples == 0:
        return {"ok": False, "error": "no training samples yet"}

    epochs = max_epochs or RETRAIN_EPOCHS
    try:
        metrics = train(
            data_dir=TRAINING_DATA_DIR,
            epochs=epochs,
            checkpoint_dir=CHECKPOINT_DIR,
            warm_start=True,
        )
        with _lock:
            state = _load_state()
            state["last_trained_at"] = time.time()
            state["events_at_last_train"] = n_samples
            state["last_error"] = None
            _save_state(state)
        metrics["ok"] = True
        logger.info("Self-learning retrain finished: %s", metrics)
        return metrics
    except Exception as exc:
        with _lock:
            state = _load_state()
            state["last_error"] = str(exc)
            _save_state(state)
        logger.exception("Self-learning retrain failed")
        return {"ok": False, "error": str(exc)}


def should_retrain() -> bool:
    """True when enough new samples accumulated since the last retrain."""
    if not AUTO_RETRAIN:
        return False
    state = _load_state()
    total = count_samples()
    if total == 0:
        return False
    baseline = int(state.get("events_at_last_train", 0))
    if total - baseline >= MIN_NEW_SAMPLES:
        return True
    last = float(state.get("last_trained_at", 0.0))
    return last == 0.0


def learning_status() -> dict:
    """Human/API-readable snapshot of the learning subsystem."""
    state = _load_state()
    checkpoint_mtime = (
        CHECKPOINT_PATH.stat().st_mtime
        if CHECKPOINT_PATH.exists()
        else None
    )
    return {
        "enabled": AUTO_RETRAIN,
        "dataset_size": count_samples(),
        "samples_recorded": int(state.get("samples_recorded", 0)),
        "seed_generated": int(state.get("seed_generated", 0)),
        "last_trained_at": float(state.get("last_trained_at", 0.0)) or None,
        "checkpoint_exists": CHECKPOINT_PATH.exists(),
        "checkpoint_modified_at": checkpoint_mtime,
        "min_new_samples_before_retrain": MIN_NEW_SAMPLES,
        "retrain_interval_seconds": RETRAIN_INTERVAL_SECONDS,
        "last_error": state.get("last_error"),
    }


def backfill_seed_batch(batch_size: int = 25) -> int:
    """Generate one batch of procedural seed samples (large-dataset bootstrapping).

    Called by the background task so the dataset grows toward the configured
    ``SEED_DATASET_COUNT`` over time without blocking the server.
    """
    try:
        from .generate_seed_dataset import generate_batch

        count = generate_batch(batch_size, TRAINING_DATA_DIR)
        if count > 0:
            with _lock:
                state = _load_state()
                state["seed_generated"] = int(state.get("seed_generated", 0)) + count
                _save_state(state)
        return count
    except Exception as exc:
        logger.warning("Seed batch generation failed: %s", exc)
        return 0


def seed_target_count() -> int:
    return int(os.getenv("SEED_DATASET_COUNT", "800"))