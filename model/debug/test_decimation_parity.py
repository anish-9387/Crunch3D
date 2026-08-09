"""Regression: the 19-cue edge-feature stage must not change decimation output.

Patches the *module-level* binding in ``mesh_optimizer`` — the flag is imported
by value at module load, so patching ``core.config`` after import is a no-op and
would silently run both arms with cues enabled.
"""
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import trimesh  # noqa: E402

from model.engine import mesh_optimizer as mo  # noqa: E402

CASES = {
    "icosphere": trimesh.creation.icosphere(subdivisions=3),
    "box_subdiv": trimesh.creation.box(extents=(1, 1, 1))
    .subdivide()
    .subdivide()
    .subdivide(),
    "cylinder": trimesh.creation.cylinder(radius=0.5, height=2.0, sections=64),
}

original_flag = mo.ENABLE_EDGE_FEATURES
rows = []

with tempfile.TemporaryDirectory() as tmp:
    tmpdir = pathlib.Path(tmp)
    for name, mesh in CASES.items():
        src = tmpdir / f"{name}.obj"
        mesh.export(src)
        target = max(4, int(len(mesh.faces) * 0.4))

        out = {}
        for flag in (True, False):
            mo.ENABLE_EDGE_FEATURES = flag
            dst = tmpdir / f"{name}_{int(flag)}.obj"
            stats, extra = mo.decimate_mesh(src, dst, target_faces=target)
            out[flag] = (
                stats.face_count,
                stats.vertex_count,
                round(float(extra.get("quality_deviation_percent") or 0.0), 4),
                extra.get("edge_features") is not None,
            )

        same_topology = out[True][:2] == out[False][:2]
        rows.append((name, out[True], out[False], same_topology))

mo.ENABLE_EDGE_FEATURES = original_flag


def fmt(t):
    return f"{t[0]}F/{t[1]}V/dev={t[2]}%"


print(f"{'mesh':<12} {'cues ON':<26} {'cues OFF':<26} {'summary?':<9} same budget")
for name, on, off, same in rows:
    print(f"{name:<12} {fmt(on):<26} {fmt(off):<26} {str(on[3]):<9} {same}")

print()
print("FACE/VERTEX BUDGET UNCHANGED:", all(r[3] for r in rows))
print("SUMMARY ONLY WHEN ENABLED:", all(r[1][3] and not r[2][3] for r in rows))
print(
    "MAX DEVIATION DELTA (on - off):",
    round(max(r[1][2] - r[2][2] for r in rows), 4),
    "pp",
)
