"""
benchmark_caching.py — Compare fast-path vs strict-quality timing and output.

Usage (from repo root):
    source backend/venv/bin/activate
    python backend/debug/benchmark_caching.py
"""

import io
import json
import sys
import time as _time
from contextlib import redirect_stdout
from pathlib import Path

# Ensure backend package is importable
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import trimesh
import numpy as np

# Force the imports to get module references
import backend.services.mesh_optimizer as mo
import backend.services.importance_mapper as im

INPUT = Path("/Users/aashisoni/Downloads/stylized_face.glb")
TARGET_FACES = 20000


def reset_timing():
    mo._TIMING.clear()
    mo._TIMING_COUNT.clear()
    im.TIMING.clear()
    im.TIMING_COUNT.clear()


def get_mesh_info(label: str, path: str | Path) -> dict:
    m = trimesh.load(str(path))
    stats = {
        "label": label,
        "vertices": len(m.vertices) if hasattr(m, "vertices") else None,
        "faces": len(m.faces) if hasattr(m, "faces") else None,
    }
    if hasattr(m, "bounding_box") and m.bounding_box is not None:
        extents = m.bounding_box.extents
        stats["bbox_extents"] = extents.tolist()
        stats["bbox_diagonal"] = float(np.linalg.norm(extents))
    return stats


def run_benchmark(name: str, strict_quality: bool) -> dict:
    print(f"\n{'='*60}")
    print(f"  Benchmark: {name}")
    print(f"{'='*60}")

    out_path = Path(f"/tmp/bench_{name.lower().replace(' ','_')}.glb")
    reset_timing()

    buf = io.StringIO()
    with redirect_stdout(buf):
        t0 = _time.perf_counter()
        stats, extra = mo.decimate_mesh(
            input_path=str(INPUT),
            output_path=str(out_path),
            target_faces=TARGET_FACES,
            preserve_normals=True,
            preserve_boundaries=True,
            strict_quality=strict_quality,
            max_deviation_percent=2.0,
            max_target_overshoot_percent=12.0,
            use_importance=True,
        )
        wall_clock = _time.perf_counter() - t0

    timing_text = buf.getvalue()

    result = {
        "name": name,
        "wall_clock_s": round(wall_clock, 3),
        "stats": {
            "vertex_count": stats.vertex_count,
            "face_count": stats.face_count,
            "file_size_mb": stats.file_size_mb,
            "has_uvs": stats.has_uvs,
            "has_normals": stats.has_normals,
        },
        "extra": extra,
        "output_mesh": get_mesh_info(name, out_path),
        "timing_report": timing_text,
    }

    print(timing_text)
    return result


def main():
    # Warm up / verify load
    print("Input mesh info:")
    info = get_mesh_info("input", INPUT)
    print(f"  {json.dumps(info, indent=2)}")
    print(f"  Target: {TARGET_FACES} faces")

    # ── 1. Fast path ──
    fast = run_benchmark("Fast path (strict_quality=False)", strict_quality=False)

    # ── 2. Strict quality ──
    strict = run_benchmark("Strict quality (strict_quality=True)", strict_quality=True)

    # ── 3. Summary comparison ──
    print(f"\n{'='*60}")
    print("  COMPARISON SUMMARY")
    print(f"{'='*60}")

    for r in [fast, strict]:
        print(f"\n  {r['name']}:")
        print(f"    Wall clock:  {r['wall_clock_s']:.1f} s")
        print(f"    Faces:       {r['stats']['face_count']}")
        print(f"    Vertices:    {r['stats']['vertex_count']}")
        print(f"    File size:   {r['stats']['file_size_mb']} MB")
        print(f"    Target used: {r['extra']['target_faces_used']}")
        print(f"    Deviation:   {r['extra'].get('quality_deviation_percent', 'N/A')}")
        print(f"    Satisfied:   {r['extra'].get('quality_guard_satisfied', 'N/A')}")
        print(f"    Relaxed:     {r['extra'].get('quality_guard_relaxed', 'N/A')}")

    # Timing detail
    print(f"\n  Timing breakdown (fast → strict):")
    fast_lines = fast["timing_report"].split("\n")
    strict_lines = strict["timing_report"].split("\n")
    for f, s in zip(fast_lines, strict_lines):
        if f.strip().startswith("=") or f.strip() == "":
            continue
        # Align
        if f.strip().startswith("Total"):
            print(f"    {f.strip():>40s}  |  {s.strip()}")
        elif f.strip().startswith("Per-component"):
            print(f"    {f.strip():>40s}  |  {s.strip()}")
        else:
            print(f"    {f.strip():>40s}  |  {s.strip()}")

    # Output bbox comparison
    print(f"\n  Output bounding boxes:")
    for r in [fast, strict]:
        bb = r["output_mesh"]
        print(f"    {r['name']}:")
        print(f"      diagonal: {bb['bbox_diagonal']:.4f}")
        print(f"      extents:  {bb['bbox_extents']}")

    print(f"\n  Done.")


if __name__ == "__main__":
    main()
