from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import trimesh

from ..graph.builder import build_graph
from .oracle import compute_oracle_labels

logger = logging.getLogger(__name__)


def generate_one(mesh: trimesh.Trimesh, out_path: Path, tiers=("A", "B"), k=None):
    g = build_graph(mesh, tiers=tiers)
    edges, labels, safety = compute_oracle_labels(mesh, k=k)
    edge_map = {tuple(e): i for i, e in enumerate(g.edges)}
    aligned_labels = np.full(len(g.edges), 0.5, dtype=np.float32)
    aligned_safety = np.zeros(len(g.edges), dtype=bool)
    for e, lab, s in zip(edges, labels, safety):
        j = edge_map.get((int(e[0]), int(e[1])), -1)
        if j >= 0:
            aligned_labels[j] = float(lab)
            aligned_safety[j] = bool(s)
    data = {
        "x": g.x,
        "edge_index": g.edge_index,
        "edge_index_2hop": g.edge_index_2hop,
        "edges": g.edges,
        "edge_features": g.edge_features,
        "labels": aligned_labels,
        "safety_mask": aligned_safety,
        "pe": g.pe,
        "metadata": g.metadata,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    import torch

    torch.save(data, out_path)
    return out_path


def generate_dataset(mesh_dir: Path, out_dir: Path, pattern="*.obj", tiers=("A", "B")):
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for p in Path(mesh_dir).rglob(pattern):
        try:
            m = trimesh.load(str(p), process=False)
            if isinstance(m, trimesh.Scene):
                parts = [g for g in m.geometry.values() if isinstance(g, trimesh.Trimesh) and len(g.faces) > 0]
                if not parts:
                    continue
                m = trimesh.util.concatenate(parts) if len(parts) > 1 else parts[0]
            if not isinstance(m, trimesh.Trimesh) or len(m.faces) < 10:
                continue
            generate_one(m, out_dir / f"{p.stem}.pt", tiers=tiers)
            count += 1
        except Exception as e:
            logger.warning("Skip %s: %s", p, e)
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh_dir", required=True)
    parser.add_argument("--out_dir", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    n = generate_dataset(Path(args.mesh_dir), Path(args.out_dir))
    print(f"Generated {n} samples")
