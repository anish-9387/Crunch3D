"""evaluation/benchmark.py — the central benchmark API (§92).

    python -m model.evaluation.benchmark --input mesh.obj --target-ratio 0.1 --method qem

Emits one JSON object with compression, Chamfer, normal error, wrong adjacency,
Laplacian spectrum error, feature recall and the runtime breakdown of §58.  The
same protocol (sampling seed, sample count, feature tolerance, spectrum size) is
used for every method so the numbers are directly comparable.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

from ..geometry.validation import validate
from ..qem.baselines import METHODS, simplify_mesh
from .chamfer import SAMPLE_COUNT, SAMPLE_SEED, bbox_diagonal, chamfer_distance, sample_surface
from .features import feature_metrics
from .laplacian import SPECTRUM_SIZE, spectrum_error
from .normals import normal_error
from .topology import topology_metrics

logger = logging.getLogger(__name__)


def load_mesh(path: str | Path):
    """Load any supported asset as a single concatenated Trimesh."""
    import trimesh

    loaded = trimesh.load(str(path), process=False)
    if isinstance(loaded, trimesh.Scene):
        parts = [
            g for g in loaded.geometry.values()
            if isinstance(g, trimesh.Trimesh) and len(g.faces) > 0
        ]
        if not parts:
            raise ValueError(f"No triangle geometry in {path}")
        return parts[0] if len(parts) == 1 else trimesh.util.concatenate(parts)
    if not isinstance(loaded, trimesh.Trimesh) or len(loaded.faces) == 0:
        raise ValueError(f"No triangle geometry in {path}")
    return loaded


def evaluate(
    original,
    simplified,
    rejected: dict | None = None,
    *,
    samples: int = SAMPLE_COUNT,
    seed: int = SAMPLE_SEED,
    spectrum_size: int = SPECTRUM_SIZE,
) -> dict:
    """Every §52-59 metric for one (original, simplified) pair."""
    original_verts = np.asarray(original.vertices, dtype=np.float64)
    original_faces = np.asarray(original.faces, dtype=np.int64)
    simplified_verts = np.asarray(simplified.vertices, dtype=np.float64)
    simplified_faces = np.asarray(simplified.faces, dtype=np.int64)

    diagonal = bbox_diagonal(original_verts)
    ref_points, ref_normals = sample_surface(original_verts, original_faces, samples, seed)
    cand_points, cand_normals = sample_surface(simplified_verts, simplified_faces, samples, seed)

    metrics: dict = {
        "faces_original": int(len(original_faces)),
        "faces_simplified": int(len(simplified_faces)),
        "vertices_original": int(len(original_verts)),
        "vertices_simplified": int(len(simplified_verts)),
        "compression": round(
            1.0 - len(simplified_faces) / max(len(original_faces), 1), 6
        ),
    }
    metrics.update(chamfer_distance(ref_points, cand_points, diagonal))
    metrics.update(normal_error(ref_points, ref_normals, cand_points, cand_normals))
    metrics.update(
        topology_metrics(
            original_verts, original_faces, simplified_verts, simplified_faces, rejected
        )
    )
    metrics.update(
        spectrum_error(
            original_verts, original_faces, simplified_verts, simplified_faces, spectrum_size
        )
    )
    metrics.update(feature_metrics(original, simplified))
    return metrics


def run_benchmark(
    input_path: str | Path,
    target_ratio: float,
    method: str = "qem",
    *,
    stages: int | None = None,
    model_path=None,
    samples: int = SAMPLE_COUNT,
    record: bool = False,
) -> dict:
    started = time.perf_counter()

    mark = time.perf_counter()
    original = load_mesh(input_path)
    report = validate(np.asarray(original.vertices), np.asarray(original.faces))
    load_seconds = time.perf_counter() - mark

    original_faces = len(original.faces)
    target = max(4, int(round(original_faces * float(target_ratio))))

    result = simplify_mesh(
        original, target, method, stages=stages, model_path=model_path, record=record
    )

    import trimesh

    simplified = trimesh.Trimesh(
        vertices=result.vertices, faces=result.faces, process=False
    )

    mark = time.perf_counter()
    metrics = evaluate(original, simplified, result.rejected, samples=samples)
    evaluation_seconds = time.perf_counter() - mark

    total = time.perf_counter() - started
    timings = dict(result.timings)
    triangles_per_second = (
        original_faces / timings["total"] if timings.get("total", 0.0) > 0 else None
    )

    output = {
        "input": str(input_path),
        "method": method,
        "target_ratio": float(target_ratio),
        "target_faces": target,
        "stages": result.stages,
        "collapses": result.collapses,
        **metrics,
        "time_ms": round(1000.0 * timings["total"], 3),
        "runtime": {
            "load_ms": round(1000.0 * load_seconds, 3),
            "preprocessing_ms": round(1000.0 * timings["preprocessing"], 3),
            "feature_ms": round(1000.0 * timings["importance"], 3),
            "gnn_inference_ms": round(1000.0 * timings["importance"], 3),
            "qem_ms": round(1000.0 * timings["qem"], 3),
            "total_ms": round(1000.0 * timings["total"], 3),
            "evaluation_ms": round(1000.0 * evaluation_seconds, 3),
            "triangles_per_second": (
                round(triangles_per_second, 1) if triangles_per_second else None
            ),
        },
        "validation": report.to_dict(),
        "protocol": {
            "surface_samples": samples,
            "sample_seed": SAMPLE_SEED,
            "spectrum_size": SPECTRUM_SIZE,
        },
    }
    if record:
        output["collapse_records"] = result.records[:200]
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crunch3D simplification benchmark")
    parser.add_argument("--input", required=True)
    parser.add_argument("--target-ratio", type=float, required=True)
    parser.add_argument("--method", default="qem", choices=list(METHODS))
    parser.add_argument("--stages", type=int, default=None)
    parser.add_argument("--model-path", default=None)
    parser.add_argument("--samples", type=int, default=SAMPLE_COUNT)
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--out", default=None, help="write the JSON here as well")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    result = run_benchmark(
        args.input,
        args.target_ratio,
        args.method,
        stages=args.stages,
        model_path=args.model_path,
        samples=args.samples,
        record=args.record,
    )
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
