"""tests/test_brush_refine.py — refactor-brush region pass.

Checks the two properties the feature rests on:

1. the painted region is the region that loses faces, and
2. geometry outside it comes through the pass byte-identical.

Plus the pure-maths contracts of ``engine/brush_selection`` (falloff, erase,
frame invariance), which need neither trimesh nor pymeshlab.

Run:  python -m model.tests.test_brush_refine
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from model.tests._harness import Checks, run          # noqa: E402
from model.engine import brush_selection as bsel      # noqa: E402


def _grid(n: int = 41):
    """Flat n×n plane in the unit square — dense, uniform, easy to reason about."""
    import trimesh

    xs, ys = np.meshgrid(np.linspace(0, 1, n), np.linspace(0, 1, n))
    verts = np.column_stack([xs.ravel(), ys.ravel(), np.zeros(n * n)])
    faces = []
    for r in range(n - 1):
        for c in range(n - 1):
            a = r * n + c
            faces.append([a, a + 1, a + n])
            faces.append([a + 1, a + n + 1, a + n])
    return trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=False)


def _stamps_covering_left_half(radius: float = 0.12):
    """Dabs down the x < 0.4 band of the grid, in bbox-normalised space.

    The grid spans the unit square in x/y with zero depth, so its diagonal is
    sqrt(2) and a normalised x of 0.4/sqrt(2) ≈ 0.283 is the model's x = 0.4.
    """
    scale = float(np.sqrt(2.0))
    stamps = []
    for t in np.linspace(0.05, 0.95, 14):
        stamps.append({"center": [0.18 / scale, t / scale, 0.0], "radius": radius})
    return stamps

def check_selection_maths(checks: Checks) -> None:
    checks.section("brush_selection — falloff and frame")

    verts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]], dtype=np.float64)
    origin, scale = bsel.frame_from_vertices(verts)
    checks.close(scale, float(np.sqrt(2.0)), 1e-9, "frame scale is the bbox diagonal")

    # A stamp centred on vertex 0 with a radius that cannot reach the others.
    stamps = bsel.stamps_from_payload([{"center": [0.0, 0.0, 0.0], "radius": 0.2}])
    weights = bsel.build_vertex_weights(verts, stamps, origin, scale)
    checks.close(weights[0], 1.0, 1e-12, "stamp centre reaches full weight")
    checks.ok(bool(np.all(weights[1:] == 0.0)), "vertices outside the radius stay at zero")

    # Frame invariance: the same stamps on a mesh scaled 100x and shifted must
    # select the same vertices, because both ends normalise by the bbox.
    moved = verts * 100.0 + np.array([37.0, -12.0, 5.0])
    origin2, scale2 = bsel.frame_from_vertices(moved)
    weights2 = bsel.build_vertex_weights(moved, stamps, origin2, scale2)
    checks.ok(
        bool(np.allclose(weights, weights2)),
        "selection is invariant to model scale and translation",
    )

    # Erase must undo an add over the area it covers.
    erased = bsel.build_vertex_weights(
        verts,
        bsel.stamps_from_payload([
            {"center": [0.0, 0.0, 0.0], "radius": 0.9},
            {"center": [0.0, 0.0, 0.0], "radius": 0.9, "op": "erase"},
        ]),
        origin, scale,
    )
    checks.close(float(erased.max()), 0.0, 1e-12, "erase stamp clears an add stamp")

    # Falloff kernels: smooth and linear taper, hard does not.
    ring = np.array([[0.5, 0.0, 0.0]], dtype=np.float64)
    half = bsel.stamps_from_payload([{"center": [0.0, 0.0, 0.0], "radius": 1.0}])
    frame = (np.zeros(3), 1.0)
    smooth = bsel.build_vertex_weights(ring, half, *frame, falloff="smooth")[0]
    linear = bsel.build_vertex_weights(ring, half, *frame, falloff="linear")[0]
    hard = bsel.build_vertex_weights(ring, half, *frame, falloff="hard")[0]
    checks.close(linear, 0.5, 1e-12, "linear falloff is 1 - d/r at half radius")
    checks.close(hard, 1.0, 1e-12, "hard falloff is flat inside the radius")
    checks.ok(0.0 < smooth < 1.0, f"smooth falloff tapers ({smooth:.4f})")

    # Malformed stamps are dropped, not fatal.
    salvaged = bsel.stamps_from_payload([
        {"center": [0.0, 0.0], "radius": 0.1},               # short vector
        {"center": [0.0, 0.0, float("nan")], "radius": 0.1},  # non-finite
        {"center": [0.0, 0.0, 0.0], "radius": 0.0},           # zero radius
        {"center": [0.0, 0.0, 0.0], "radius": 0.1},           # the good one
    ])
    checks.ok(len(salvaged) == 1, f"malformed stamps are skipped ({len(salvaged)} kept)")

    # blend_importance pins unpainted vertices and passes painted ones through.
    blended = bsel.blend_importance(
        np.array([0.2, 0.2, 0.2]), np.array([0.0, 0.5, 1.0])
    )
    checks.close(blended[0], 1.0, 1e-12, "unpainted vertex is fully protected")
    checks.close(blended[2], 0.2, 1e-12, "fully painted vertex keeps its importance")
    checks.ok(blended[1] > blended[2], "partially painted vertex sits in between")


def check_face_weights(checks: Checks) -> None:
    checks.section("brush_selection — face aggregation")

    faces = np.array([[0, 1, 2], [1, 2, 3]], dtype=np.int64)
    weights = np.array([1.0, 1.0, 1.0, 0.0])
    fw = bsel.face_weights(faces, weights)
    checks.close(fw[0], 1.0, 1e-12, "face with three painted vertices scores 1")
    checks.close(fw[1], 2.0 / 3.0, 1e-12, "face aggregation is the vertex mean")

    verts_in, faces_in = bsel.selection_counts(faces, weights, threshold=0.5)
    checks.ok(verts_in == 3, f"selected vertex count ({verts_in})")
    checks.ok(faces_in == 2, f"selected face count at threshold 0.5 ({faces_in})")

def check_region_pass(checks: Checks) -> None:
    checks.section("brush_refine — region-local pass")

    try:
        import pymeshlab  # noqa: F401
        import trimesh  # noqa: F401
        from model.engine.brush_refine import BrushSelectionError, refine_region
    except Exception as exc:
        print(f"    SKIP  pymeshlab/trimesh unavailable ({exc})")
        return

    mesh = _grid(41)
    stamps = bsel.stamps_from_payload(_stamps_covering_left_half())

    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "plane.obj"
        target = Path(tmp) / "plane_refined.obj"
        mesh.export(str(source))

        before = trimesh.load(str(source), process=False)
        before_verts = np.asarray(before.vertices, dtype=np.float64)

        stats, meta = refine_region(
            input_path=source,
            output_path=target,
            stamps=stamps,
            reduction_percent=50.0,
        )

        checks.ok(target.exists(), "refined mesh was written")
        checks.ok(
            meta["selected_face_count"] > 0,
            f"brush selected a region ({meta['selected_face_count']} faces)",
        )
        checks.ok(
            meta["faces_removed"] > 0,
            f"faces were removed ({meta['faces_removed']})",
        )
        checks.ok(
            meta["faces_after"] == stats.face_count,
            "reported face count matches the exported mesh",
        )
        checks.ok(
            meta["region_mode"] == "selected_faces",
            f"PyMeshLab face selection drove the pass (mode={meta['region_mode']})",
        )

        # The load-bearing guarantee: nothing outside the stroke moved.  The
        # stroke band ends near model x = 0.3, so x > 0.45 is comfortably clear
        # of it and every vertex there must survive at its exact position.
        after_verts = np.asarray(
            trimesh.load(str(target), process=False).vertices, dtype=np.float64
        )
        surviving = {tuple(np.round(p, 7)) for p in after_verts}
        outside = before_verts[before_verts[:, 0] > 0.45]
        lost_outside = sum(
            1 for p in outside if tuple(np.round(p, 7)) not in surviving
        )
        checks.ok(
            lost_outside == 0,
            f"all {len(outside)} vertices outside the stroke survived "
            f"(lost {lost_outside})",
        )

        inside = before_verts[before_verts[:, 0] < 0.2]
        lost_inside = sum(1 for p in inside if tuple(np.round(p, 7)) not in surviving)
        checks.ok(
            lost_inside > 0,
            f"vertices inside the stroke were collapsed ({lost_inside} of {len(inside)})",
        )

        # A stroke placed off the model must fail loudly and write nothing.
        missed = Path(tmp) / "missed.obj"
        try:
            refine_region(
                input_path=source,
                output_path=missed,
                stamps=bsel.stamps_from_payload(
                    [{"center": [9.0, 9.0, 9.0], "radius": 0.05}]
                ),
            )
            checks.ok(False, "off-model stroke raises BrushSelectionError")
        except BrushSelectionError:
            checks.ok(True, "off-model stroke raises BrushSelectionError")
        checks.ok(not missed.exists(), "a failed pass writes no output file")


_PARITY_SCRIPT = """
import { readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'

const libUrl = pathToFileURL(process.argv[2]).href
const { buildWeights, normalizedFrame } = await import(libUrl)
const fixture = JSON.parse(readFileSync(process.argv[3], 'utf8'))

const { origin, scale } = normalizedFrame(fixture.min, fixture.max)
const count = fixture.vertices.length / 3
const unit = new Float32Array(count * 3)
for (let i = 0, o = 0; i < count; i++, o += 3) {
  unit[o] = (fixture.vertices[o] - origin[0]) / scale
  unit[o + 1] = (fixture.vertices[o + 1] - origin[1]) / scale
  unit[o + 2] = (fixture.vertices[o + 2] - origin[2]) / scale
}

const stamps = fixture.stamps.map((s) => ({ ...s, falloff: fixture.falloff }))
const weights = buildWeights(unit, count, stamps)
process.stdout.write(JSON.stringify({ scale, weights: Array.from(weights) }))
"""


def check_viewer_parity(checks: Checks) -> None:
    """The viewer's kernel and the engine's must agree, or the highlight lies."""
    import json
    import shutil
    import subprocess

    checks.section("viewer parity — JS kernel vs Python kernel")

    node = shutil.which("node")
    lib = (
        Path(__file__).resolve().parent.parent.parent
        / "web" / "src" / "lib" / "brushSelection.js"
    )
    if node is None or not lib.exists():
        print(f"    SKIP  node or {lib.name} unavailable")
        return

    rng = np.random.default_rng(7)
    vertices = rng.normal(scale=3.0, size=(900, 3))
    stamps_payload = []
    for _ in range(12):
        stamps_payload.append({
            "center": (rng.random(3) * 0.9).tolist(),
            "radius": float(0.05 + rng.random() * 0.2),
            "erase": bool(rng.random() < 0.3),
            "strength": float(0.4 + rng.random() * 0.6),
        })

    for falloff in ("smooth", "linear", "hard"):
        fixture = {
            "vertices": vertices.reshape(-1).tolist(),
            "min": vertices.min(axis=0).tolist(),
            "max": vertices.max(axis=0).tolist(),
            "stamps": stamps_payload,
            "falloff": falloff,
        }

        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "parity.mjs"
            data = Path(tmp) / "fixture.json"
            script.write_text(_PARITY_SCRIPT, encoding="utf-8")
            data.write_text(json.dumps(fixture), encoding="utf-8")
            proc = subprocess.run(
                [node, str(script), str(lib), str(data)],
                capture_output=True, text=True, timeout=120,
            )

        if proc.returncode != 0:
            checks.ok(False, f"node kernel ran ({falloff}): {proc.stderr.strip()[:180]}")
            continue

        js = json.loads(proc.stdout)
        origin, scale = bsel.frame_from_vertices(vertices)
        checks.close(js["scale"], scale, 1e-9, f"frame scale agrees ({falloff})")

        py = bsel.build_vertex_weights(
            vertices, bsel.stamps_from_payload(stamps_payload), origin, scale, falloff
        )
        drift = float(np.max(np.abs(np.asarray(js["weights"], dtype=np.float64) - py)))
        # float32 on the JS side against float64 here, so exact equality is not
        # on offer; 1e-5 is far tighter than the 0.5 selection threshold.
        checks.ok(drift < 1e-5, f"weights agree within 1e-5 ({falloff}, drift {drift:.2e})")
        checks.ok(
            float(py.max()) > 0.5,
            f"fixture actually paints something ({falloff}, max {py.max():.3f})",
        )


def check_importance_spread(checks: Checks) -> None:
    """A narrow importance band has to be stretched, or QEM protects everything."""
    checks.section("brush_refine — importance dynamic range")

    try:
        from model.engine.brush_refine import _spread_importance
    except Exception as exc:
        print(f"    SKIP  brush_refine unavailable ({exc})")
        return

    # The composed stack lands in a band like [0.90, 1.00]; PyMeshLab reads that
    # as "protect every vertex equally".
    band = np.linspace(0.90, 1.00, 200)
    spread = _spread_importance(band)
    checks.close(float(spread.min()), 0.0, 1e-9, "narrow band is stretched down to 0")
    checks.close(float(spread.max()), 1.0, 1e-9, "narrow band is stretched up to 1")
    checks.ok(
        bool(np.all(np.diff(spread) >= -1e-12)),
        "the spread preserves importance ordering",
    )

    # The GNN stage multiplies importance past 1.0, so the input must not be
    # clipped before the rescale or those peaks all collapse onto each other.
    raw = np.array([0.5, 1.4, 1.9, 2.0])
    spread_raw = _spread_importance(raw)
    checks.ok(
        len(np.unique(np.round(spread_raw, 6))) == 4,
        f"values above 1.0 stay distinguishable ({np.round(spread_raw, 3).tolist()})",
    )

    flat = _spread_importance(np.full(50, 0.97))
    checks.close(float(flat.max()), 0.0, 1e-12, "a uniform map carries no signal")

    outlier = np.concatenate([np.linspace(0.90, 0.92, 99), [1.0]])
    spread_outlier = _spread_importance(outlier)
    checks.ok(
        float(spread_outlier[:99].max() - spread_outlier[:99].min()) > 0.5,
        "one outlier cannot squash the rest of the band",
    )


def check_reduction_is_honoured(checks: Checks) -> None:
    """A flat importance map must not silently cancel the user's reduction."""
    checks.section("brush_refine — requested reduction is delivered")

    try:
        import pymeshlab  # noqa: F401
        import trimesh  # noqa: F401
        from model.engine import brush_refine as br
    except Exception as exc:
        print(f"    SKIP  pymeshlab/trimesh unavailable ({exc})")
        return

    mesh = _grid(41)
    stamps = bsel.stamps_from_payload(_stamps_covering_left_half())

    def run(reduction=60.0):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "plane.obj"
            target = Path(tmp) / "plane_out.obj"
            mesh.export(str(source))
            _, meta = br.refine_region(
                input_path=source,
                output_path=target,
                stamps=stamps,
                reduction_percent=reduction,
            )
            surviving = {
                tuple(np.round(p, 7))
                for p in np.asarray(
                    trimesh.load(str(target), process=False).vertices,
                    dtype=np.float64,
                )
            }
        return meta, surviving

    before_verts = np.asarray(mesh.vertices, dtype=np.float64)
    outside = before_verts[before_verts[:, 0] > 0.45]

    # An importance map pinned at full protection carries no ranking at all;
    # the reduction still has to happen, driven by geometric error.
    real_importance = br._region_importance
    br._region_importance = lambda m: np.ones(len(m.vertices), dtype=np.float64)
    try:
        meta, surviving = run()
    finally:
        br._region_importance = real_importance

    asked = int(round(meta["selected_face_count"] * 0.60))
    checks.ok(
        meta["faces_removed"] >= asked * br.ESCALATION_SHORTFALL,
        f"a flat importance map still reduces "
        f"({meta['faces_removed']} of {asked} requested)",
    )

    # Now force the weighted attempt to come up empty — the failure mode measured
    # on a real model, where the region protected itself out of decimation — and
    # check the pass escalates instead of returning the mesh unchanged.
    real_decimate = br._decimate_selection
    calls = {"n": 0}

    def stubborn_first_attempt(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return 0
        return real_decimate(*args, **kwargs)

    br._decimate_selection = stubborn_first_attempt
    try:
        meta, surviving = run()
    finally:
        br._decimate_selection = real_decimate

    checks.ok(calls["n"] >= 2, f"a barren first attempt is retried ({calls['n']} calls)")
    checks.ok(
        meta["faces_removed"] > 0,
        f"the retry still delivers a reduction ({meta['faces_removed']} faces)",
    )
    checks.ok(
        meta["region_escalated"] is True,
        f"the escalation is reported to the caller ({meta['region_escalated']})",
    )
    checks.ok(
        meta["region_mode"] == "selected_faces",
        f"escalating keeps the region confined (mode={meta['region_mode']})",
    )
    lost_outside = sum(
        1 for p in outside if tuple(np.round(p, 7)) not in surviving
    )
    checks.ok(
        lost_outside == 0,
        f"escalating still moves nothing outside the stroke (lost {lost_outside})",
    )


def main() -> int:
    checks = Checks("Refactor brush — selection maths and region pass")
    check_selection_maths(checks)
    check_face_weights(checks)
    check_viewer_parity(checks)
    check_importance_spread(checks)
    check_region_pass(checks)
    check_reduction_is_honoured(checks)
    return checks.finish()


if __name__ == "__main__":
    run(main)
