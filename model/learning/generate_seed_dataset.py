"""
learning/generate_seed_dataset.py — Large procedural dataset for the GNN.

Creates thousands of synthetic meshes (primitives with randomized
parameters, noise-warped surfaces and baked vertex colours) and labels each
one with the heuristic importance pipeline (the "teacher"), so the GNN can
be trained on a large, varied dataset without any internet download or
manual labelling.

Usage:
    python -m model.learning.generate_seed_dataset --count 2000           # full run
    python -m model.learning.generate_seed_dataset --count 200 --batch    # append
"""

from __future__ import annotations

import argparse
import logging
import random
from pathlib import Path

import numpy as np
import trimesh

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path(__file__).parent / "training_data"

# Deterministic RNG seeds so re-runs are reproducible
_rng = random.Random(42)


def _random_primitive() -> trimesh.Trimesh:
    """One randomized primitive mesh."""
    kind = _rng.choice(["box", "sphere", "cylinder", "cone", "torus", "capsule", "icosphere", "prism"])
    scale = _rng.uniform(0.3, 2.0)
    if kind == "box":
        mesh = trimesh.creation.box(
            extents=[scale * _rng.uniform(0.5, 2.0) for _ in range(3)]
        )
    elif kind == "sphere":
        mesh = trimesh.creation.icosphere(
            subdivisions=_rng.choice([2, 3, 4]),
            radius=scale,
        )
    elif kind == "cylinder":
        mesh = trimesh.creation.cylinder(
            radius=scale * _rng.uniform(0.3, 1.5),
            height=scale * _rng.uniform(0.5, 3.0),
            sections=_rng.choice([12, 24, 48]),
        )
    elif kind == "cone":
        mesh = trimesh.creation.cone(
            radius=scale * _rng.uniform(0.5, 1.5),
            height=scale * _rng.uniform(0.5, 3.0),
            sections=_rng.choice([12, 24, 48]),
        )
    elif kind == "torus":
        mesh = trimesh.creation.torus(
            major_radius=scale * _rng.uniform(0.5, 1.5),
            minor_radius=scale * _rng.uniform(0.1, 0.5),
            major_sections=_rng.choice([16, 32, 64]),
            minor_sections=_rng.choice([8, 16, 32]),
        )
    elif kind == "capsule":
        mesh = trimesh.creation.capsule(
            radius=scale * _rng.uniform(0.2, 0.8),
            height=scale * _rng.uniform(0.5, 2.0),
            count=_rng.choice([8, 16, 32]),
        )
    elif kind == "prism":
        mesh = trimesh.creation.prism(
            width=scale * _rng.uniform(0.5, 1.5),
            length=scale * _rng.uniform(0.5, 1.5),
            height=scale * _rng.uniform(0.5, 2.0),
            sections=_rng.choice([3, 4, 6, 8]),
        )
    else:  # icosphere fallback
        mesh = trimesh.creation.icosphere(
            subdivisions=_rng.choice([3, 4]), radius=scale
        )
    return mesh


def _warp_surface(mesh: trimesh.Trimesh, amplitude: float = 0.12) -> trimesh.Trimesh:
    """Add smooth noise displacement to mimic organic/AI-generated surfaces."""
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    n = len(verts)
    freq = _rng.uniform(1.5, 6.0)
    rng = np.random.default_rng(_rng.randint(0, 2**31))
    phase = rng.uniform(0.0, 6.28, size=3)
    noise = (
        np.sin(verts * freq + phase).sum(axis=1) * 0.5
        + np.cos(verts * freq * 1.3 + phase[::-1]).sum(axis=1) * 0.5
    ) / 3.0
    noise = (noise - noise.mean()) / (noise.std() + 1e-9)
    normals = np.asarray(mesh.vertex_normals, dtype=np.float64)
    displaced = verts + normals * noise[:, None] * amplitude
    return trimesh.Trimesh(
        vertices=displaced,
        faces=np.asarray(mesh.faces, dtype=np.int64),
        process=False,
    )


def _apply_painted_colors(mesh: trimesh.Trimesh) -> None:
    """Bake region-based vertex colours (painted-detail signal for the GNN)."""
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    if _rng.random() < 0.5:
        return  # leave uncoloured — the model must also learn the neutral case

    n = len(verts)
    colors = np.zeros((n, 4), dtype=np.uint8)
    palette = [
        (180, 70, 70), (70, 150, 180), (90, 170, 90),
        (220, 180, 60), (150, 90, 180), (70, 70, 70),
    ]
    # Paint three random bands so colour seams fall on real geometry
    for _ in range(3):
        axis = _rng.randint(0, 2)
        lo = _rng.uniform(verts[:, axis].min(), verts[:, axis].max())
        hi = lo + _rng.uniform(0.1, 0.6) * (verts[:, axis].max() - verts[:, axis].min())
        band = (verts[:, axis] >= lo) & (verts[:, axis] <= hi)
        base = np.asarray(palette[_rng.randint(0, len(palette) - 1)], dtype=np.uint8)
        colors[band, :3] = base
        colors[band, 3] = 255

    # Vertices outside bands get a light grey so the mesh is fully painted
    unpainted = colors[:, 3] == 0
    colors[unpainted, :3] = 200
    colors[unpainted, 3] = 255

    mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh, vertex_colors=colors)


def _make_one(index: int) -> trimesh.Trimesh | None:
    """One full procedural sample: primitive + warp + colours."""
    try:
        mesh = _random_primitive()
        if len(mesh.faces) < 20:
            return None
        mesh = _warp_surface(mesh)
        _apply_painted_colors(mesh)
        return mesh
    except Exception as exc:
        logger.warning("Primitive %d failed: %s", index, exc)
        return None


def generate_batch(
    count: int,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    start_index: int = 0,
) -> int:
    """Generate *count* procedural samples into *output_dir*.

    Returns the number of files actually written (skips existing names).
    """
    from .data_prep import _compute_edge_importance_from_heuristic
    from .dataset import mesh_to_graph_data
    import torch

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    index = start_index
    attempts = 0
    while written < count and attempts < count * 4:
        attempts += 1
        name = f"seed_{index:05d}.pt"
        index += 1
        if (output_dir / name).exists():
            written += 1
            continue

        mesh = _make_one(index)
        if mesh is None:
            continue
        try:
            labels = _compute_edge_importance_from_heuristic(mesh)
            data = mesh_to_graph_data(mesh, labels)
            torch.save(data, output_dir / name)
            written += 1
        except Exception as exc:
            logger.warning("Sample %s failed: %s", name, exc)

    logger.info("Seed batch: wrote %d samples to %s", written, output_dir)
    return written


def generate_full_dataset(
    count: int,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> int:
    """Generate the whole dataset in one go (used by the CLI)."""
    batch_size = 50
    written = 0
    while written < count:
        written += generate_batch(batch_size, output_dir, start_index=written)
    # Cap: the while loop stops when generate_batch can't write anymore
    # because existing files were counted, so log the final total.
    total = sum(1 for p in Path(output_dir).iterdir() if p.suffix == ".pt")
    logger.info("Total seed dataset size: %d", total)
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate procedural GNN training data")
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--output_dir", type=str, default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--batch", action="store_true",
                        help="Generate in one batch count samples, skipping existing")
    args = parser.parse_args()

    out = Path(args.output_dir)
    if args.batch:
        n = generate_batch(args.count, out)
    else:
        n = generate_full_dataset(args.count, out)
    print(f"Generated: {n} samples in {out}")