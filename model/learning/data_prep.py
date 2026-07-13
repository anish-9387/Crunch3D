"""
learning/data_prep.py — Self-supervised + feedback-based training data generation.

Two modes:
  1. BOOTSTRAP (default): Uses the existing importance_mapper heuristic as teacher.
     Takes any mesh → computes per-edge importance with compute_importance() →
     saves as PyG Data. No user feedback required. Works on any mesh.

  2. FEEDBACK: Reads feedback_events.jsonl, compares original vs optimized meshes,
     and generates fine-tuning data weighted by user satisfaction.

Usage:
    python -m model.learning.data_prep                     # bootstrap from uploads/
    python -m model.learning.data_prep --mode feedback      # from feedback events
    python -m model.learning.data_prep --mesh_dir /path     # custom mesh directory
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
from pathlib import Path

import numpy as np
import trimesh

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
TRAINING_DIR = BASE_DIR / "training"
FEEDBACK_FILE = TRAINING_DIR / "feedback_events.jsonl"
UPLOADS_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "processed"
TRAINING_DATA_DIR = Path(__file__).parent / "training_data"


# ── Bootstrap mode ────────────────────────────────────────────────────────────


def _load_single_trimesh(path: Path) -> trimesh.Trimesh | None:
    """Load a mesh file, merge scenes into a single Trimesh if needed."""
    try:
        loaded = trimesh.load(str(path), process=False)
        if isinstance(loaded, trimesh.Trimesh):
            return loaded
        if isinstance(loaded, trimesh.Scene):
            parts = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
            if parts:
                return trimesh.util.concatenate(parts)
        return None
    except Exception as e:
        logger.warning("Failed to load %s: %s", path, e)
        return None


def _compute_edge_importance_from_heuristic(mesh: trimesh.Trimesh) -> np.ndarray:
    """Use the existing importance_mapper as teacher to generate edge-level ground truth.

    Takes per-vertex importance from the heuristic pipeline and converts to
    per-edge importance by averaging the two endpoint vertex importances.
    """
    from ..importance.importance_mapper import compute_importance

    vertex_importance = compute_importance(mesh)  # (V,) array in [0, 1]
    edges = mesh.edges_unique  # (E, 2)

    # Edge importance = mean of endpoint vertex importances
    edge_importance = (vertex_importance[edges[:, 0]] + vertex_importance[edges[:, 1]]) / 2.0

    return edge_importance.astype(np.float32)


def bootstrap_from_directory(mesh_dir: Path, output_dir: Path) -> int:
    """Generate self-supervised training data from all meshes in a directory tree.

    For each mesh:
      1. Load it
      2. Compute per-edge importance using the heuristic pipeline (teacher)
      3. Save as a PyG Data object

    Returns the number of datasets generated.
    """
    from .dataset import mesh_to_graph_data
    import torch

    output_dir.mkdir(parents=True, exist_ok=True)

    mesh_extensions = {".obj", ".stl", ".ply", ".glb", ".gltf", ".off"}
    mesh_files = []
    for root, _, files in os.walk(mesh_dir):
        for f in files:
            if Path(f).suffix.lower() in mesh_extensions:
                mesh_files.append(Path(root) / f)

    logger.info("Found %d mesh files in %s", len(mesh_files), mesh_dir)

    count = 0
    for mesh_path in mesh_files:
        # Use a stable ID from the file path
        stable_id = mesh_path.stem + "_" + mesh_path.parent.name
        out_path = output_dir / f"bootstrap_{stable_id}.pt"

        if out_path.exists():
            logger.info("Already exists: %s, skipping.", out_path.name)
            count += 1
            continue

        mesh = _load_single_trimesh(mesh_path)
        if mesh is None or len(mesh.faces) < 10:
            logger.warning("Skipping %s (empty or too small)", mesh_path.name)
            continue

        logger.info("Processing %s (%d verts, %d faces)...",
                     mesh_path.name, len(mesh.vertices), len(mesh.faces))

        try:
            # Teacher: heuristic importance mapper
            edge_importance = _compute_edge_importance_from_heuristic(mesh)

            # Convert to graph data
            graph_data = mesh_to_graph_data(mesh, edge_importance)

            torch.save(graph_data, out_path)
            logger.info("Saved → %s (edges=%d)", out_path.name, len(edge_importance))
            count += 1

        except Exception as e:
            logger.error("Failed on %s: %s", mesh_path.name, e)

    logger.info("Bootstrap complete: %d datasets generated.", count)
    return count


# ── Feedback fine-tuning mode ─────────────────────────────────────────────────


def _get_mesh_files(job_id: str):
    """Find the original and optimized mesh files for a job_id."""
    upload_dir = UPLOADS_DIR / job_id
    processed_dir = PROCESSED_DIR / job_id

    orig_file = None
    if upload_dir.exists():
        for p in upload_dir.iterdir():
            if p.is_file() and p.suffix.lower() in {".obj", ".stl", ".ply", ".glb", ".gltf", ".off"}:
                orig_file = p
                break

    opt_file = None
    if processed_dir.exists():
        for p in processed_dir.iterdir():
            if p.is_file() and "_optimized" in p.name:
                opt_file = p
                break

    return orig_file, opt_file


def _compute_feedback_ground_truth(
    original_mesh: trimesh.Trimesh,
    optimized_mesh: trimesh.Trimesh,
    satisfied: bool,
) -> np.ndarray:
    """Compute ground truth edge importance from mesh comparison + feedback.

    Compares edge midpoints of the original against the optimized surface.
    - satisfied=True → edges that survived are important (1.0), collapsed are safe (0.0)
    - satisfied=False → collapsed edges SHOULD have been kept (1.0), rest neutral (0.5)
    """
    edges = original_mesh.edges_unique
    vertices = original_mesh.vertices
    midpoints = (vertices[edges[:, 0]] + vertices[edges[:, 1]]) / 2.0

    _, distances, _ = trimesh.proximity.closest_point(optimized_mesh, midpoints)

    diagonal = np.linalg.norm(original_mesh.bounding_box.extents)
    threshold = diagonal * 0.01
    is_collapsed = distances > threshold

    importance = np.zeros(len(edges), dtype=np.float32)

    if satisfied:
        importance[is_collapsed] = 0.0
        importance[~is_collapsed] = 1.0
    else:
        importance[is_collapsed] = 1.0
        importance[~is_collapsed] = 0.5

    return importance


def finetune_from_feedback(output_dir: Path) -> int:
    """Generate fine-tuning data from user feedback events."""
    from .dataset import mesh_to_graph_data
    import torch

    if not FEEDBACK_FILE.exists():
        logger.error("No feedback file found at %s", FEEDBACK_FILE)
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                job_id = event.get("job_id")
                feedback = event.get("feedback", {})
                satisfied = feedback.get("satisfied", False)
                if not job_id:
                    continue

                out_path = output_dir / f"feedback_{job_id}.pt"
                if out_path.exists():
                    continue

                orig_file, opt_file = _get_mesh_files(job_id)
                if not orig_file or not opt_file:
                    logger.warning("Missing mesh files for job %s, skipping.", job_id)
                    continue

                orig_mesh = _load_single_trimesh(orig_file)
                opt_mesh = _load_single_trimesh(opt_file)
                if orig_mesh is None or opt_mesh is None:
                    continue

                logger.info("Processing feedback for job %s (satisfied=%s)", job_id, satisfied)
                gt = _compute_feedback_ground_truth(orig_mesh, opt_mesh, satisfied)
                graph_data = mesh_to_graph_data(orig_mesh, gt)

                torch.save(graph_data, out_path)
                logger.info("Saved → %s", out_path.name)
                count += 1

            except Exception as e:
                logger.error("Error on job %s: %s", job_id, e)

    logger.info("Feedback fine-tuning: %d datasets generated.", count)
    return count


# ── CLI ───────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate GNN training data")
    parser.add_argument(
        "--mode", choices=["bootstrap", "feedback", "both"], default="both",
        help="Data generation mode (default: both)",
    )
    parser.add_argument(
        "--mesh_dir", type=str, default=None,
        help="Directory containing mesh files for bootstrap (default: model/uploads/)",
    )
    parser.add_argument(
        "--output_dir", type=str, default=None,
        help="Output directory for .pt files (default: model/learning/training_data/)",
    )
    args = parser.parse_args()

    mesh_dir = Path(args.mesh_dir) if args.mesh_dir else UPLOADS_DIR
    output_dir = Path(args.output_dir) if args.output_dir else TRAINING_DATA_DIR

    total = 0

    if args.mode in ("bootstrap", "both"):
        logger.info("=== Bootstrap mode: generating from %s ===", mesh_dir)
        total += bootstrap_from_directory(mesh_dir, output_dir)

    if args.mode in ("feedback", "both"):
        logger.info("=== Feedback mode: generating from feedback events ===")
        total += finetune_from_feedback(output_dir)

    logger.info("=== Total datasets: %d ===", total)
