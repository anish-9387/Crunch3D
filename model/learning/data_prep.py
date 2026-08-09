"""
learning/data_prep.py — Self-supervised training data generation.

Uses the existing importance_mapper heuristic as teacher: takes any mesh →
computes per-edge importance with compute_importance() → saves as PyG Data.
Works on any mesh, with no labelling step.

Usage:
    python -m model.learning.data_prep                     # from uploads/
    python -m model.learning.data_prep --mesh_dir /path     # custom mesh directory
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import numpy as np
import trimesh

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
TRAINING_DIR = BASE_DIR / "training"
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


# ── CLI ───────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate GNN training data")
    parser.add_argument(
        "--mesh_dir", type=str, default=None,
        help="Directory containing mesh files (default: model/uploads/)",
    )
    parser.add_argument(
        "--output_dir", type=str, default=None,
        help="Output directory for .pt files (default: model/learning/training_data/)",
    )
    args = parser.parse_args()

    mesh_dir = Path(args.mesh_dir) if args.mesh_dir else UPLOADS_DIR
    output_dir = Path(args.output_dir) if args.output_dir else TRAINING_DATA_DIR

    logger.info("=== Bootstrap mode: generating from %s ===", mesh_dir)
    total = bootstrap_from_directory(mesh_dir, output_dir)

    logger.info("=== Total datasets: %d ===", total)
