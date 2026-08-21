from __future__ import annotations

import argparse
import logging
from pathlib import Path

import trimesh

from .cache import cache_one
from .split import split_dataset

logger = logging.getLogger(__name__)


def prepare(raw_dir: Path, processed_dir: Path, tiers=("A", "B"), split=True):
    raw_dir = Path(raw_dir)
    processed_dir = Path(processed_dir)
    cache_dir = processed_dir / "all"
    cache_dir.mkdir(parents=True, exist_ok=True)
    exts = {".obj", ".stl", ".ply", ".glb", ".gltf", ".off"}
    count = 0
    for p in raw_dir.rglob("*"):
        if p.suffix.lower() not in exts:
            continue
        try:
            m = trimesh.load(str(p), process=False)
            if isinstance(m, trimesh.Scene):
                parts = [g for g in m.geometry.values() if isinstance(g, trimesh.Trimesh) and len(g.faces) > 0]
                if not parts:
                    continue
                m = trimesh.util.concatenate(parts) if len(parts) > 1 else parts[0]
            if not isinstance(m, trimesh.Trimesh) or len(m.faces) < 10:
                continue
            out = cache_dir / f"{p.stem}.pt"
            cache_one(m, out, tiers=tiers)
            count += 1
        except Exception as e:
            logger.warning("Skip %s: %s", p, e)
    if split:
        stats = split_dataset(cache_dir, processed_dir)
        logger.info("Split: %s", stats)
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True)
    parser.add_argument("--processed", required=True)
    parser.add_argument("--no-split", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    n = prepare(Path(args.raw), Path(args.processed), split=not args.no_split)
    print(f"Cached {n} meshes")
