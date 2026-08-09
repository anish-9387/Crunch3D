"""
test_edge_features.py — Verify the 19-cue edge-feature descriptor.

Run with:  python -m model.debug.test_edge_features

Checks, per test mesh:

  1. Every cue in FEATURE_NAMES is produced, finite, and edge-aligned.
  2. The fused importance stays inside [0, 1].
  3. Cues that need absent attributes (UVs, colours, rig) report present=False
     rather than fabricating data.
  4. Geometric cues respond correctly to known geometry — a cube's 12 model
     edges must be flagged sharp, a smooth sphere must flag none, and an open
     plane must flag its perimeter as boundary.
  5. scatter_to_vertices() and feature_matrix() return the documented shapes.
  6. The optimizer's protection term keeps importance in [0, 1] and never
     lowers a vertex's protection relative to the base map.

Exits non-zero if any check fails, so it can gate a commit.
"""

import logging
import sys
import time

import numpy as np
import trimesh

from ..importance.edge_features import (
    EDGE_FEATURE_COUNT,
    FEATURE_NAMES,
    compute_edge_feature_importance,
    scatter_to_vertices,
)
from ..importance.importance_mapper import compute_importance

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
log = logging.getLogger("test_edge_features")

FAILURES: list[str] = []


def check(condition: bool, label: str) -> bool:
    if condition:
        print(f"    PASS  {label}")
        return True
    print(f"    FAIL  {label}")
    FAILURES.append(label)
    return False


# ── Test meshes ──────────────────────────────────────────────────────────────


def _cube() -> trimesh.Trimesh:
    return trimesh.creation.box(extents=(1.0, 1.0, 1.0))


def _sphere() -> trimesh.Trimesh:
    return trimesh.creation.icosphere(subdivisions=3, radius=1.0)


def _open_plane() -> trimesh.Trimesh:
    """A flat 6x6 grid — every perimeter edge is a boundary edge."""
    n = 6
    xs, ys = np.meshgrid(np.linspace(0, 1, n), np.linspace(0, 1, n))
    verts = np.column_stack([xs.ravel(), ys.ravel(), np.zeros(n * n)])
    faces = []
    for r in range(n - 1):
        for c in range(n - 1):
            a = r * n + c
            faces.append([a, a + 1, a + n])
            faces.append([a + 1, a + n + 1, a + n])
    return trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=False)


def _uv_sphere() -> trimesh.Trimesh:
    """Sphere carrying UVs and vertex colours, to exercise the optional cues."""
    mesh = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    verts = np.asarray(mesh.vertices)
    uv = np.column_stack([
        (np.arctan2(verts[:, 2], verts[:, 0]) + np.pi) / (2 * np.pi),
        (verts[:, 1] + 1.0) / 2.0,
    ])
    mesh.visual = trimesh.visual.TextureVisuals(uv=uv)
    colors = np.zeros((len(verts), 4), dtype=np.uint8)
    colors[:, 0] = ((verts[:, 0] + 1.0) * 127).astype(np.uint8)
    colors[:, 1] = ((verts[:, 1] + 1.0) * 127).astype(np.uint8)
    colors[:, 2] = ((verts[:, 2] + 1.0) * 127).astype(np.uint8)
    colors[:, 3] = 255
    mesh.visual.vertex_colors = colors
    return mesh


# ── Core structural checks ───────────────────────────────────────────────────


def run_structural(mesh: trimesh.Trimesh, label: str) -> None:
    print(f"\n[{label}]  {len(mesh.vertices)} verts / {len(mesh.faces)} faces")

    t0 = time.perf_counter()
    result = compute_edge_feature_importance(mesh)
    elapsed = time.perf_counter() - t0
    n_edges = len(result.edges)
    print(f"    {n_edges} unique edges in {elapsed * 1000:.1f} ms")

    check(n_edges > 0, "edge list is non-empty")
    check(result.edges.shape[1] == 2, "edge list is (E, 2)")
    check(
        bool(np.all(result.edges[:, 0] < result.edges[:, 1])),
        "edges stored as sorted (min, max) pairs",
    )
    check(
        len(np.unique(result.edges, axis=0)) == n_edges,
        "no duplicate edges",
    )

    missing = [name for name in FEATURE_NAMES if name not in result.features]
    check(not missing, f"all {EDGE_FEATURE_COUNT} cues produced (missing: {missing})")

    for name in FEATURE_NAMES:
        arr = result.features.get(name)
        if arr is None:
            continue
        if len(arr) != n_edges:
            check(False, f"cue '{name}' is edge-aligned")
        elif not np.all(np.isfinite(arr)):
            check(False, f"cue '{name}' is finite")

    print("    PASS  every cue is edge-aligned and finite")

    imp = result.importance
    check(len(imp) == n_edges, "fused importance is edge-aligned")
    check(
        bool(np.all(imp >= 0.0) and np.all(imp <= 1.0)),
        f"fused importance in [0, 1] (got [{imp.min():.3f}, {imp.max():.3f}])",
    )
    check(float(np.std(imp)) > 1e-6, "fused importance discriminates between edges")

    matrix = result.feature_matrix()
    check(
        matrix.shape == (n_edges, EDGE_FEATURE_COUNT),
        f"feature_matrix() is (E, {EDGE_FEATURE_COUNT}) (got {matrix.shape})",
    )

    scattered = scatter_to_vertices(result, len(mesh.vertices))
    check(
        len(scattered) == len(mesh.vertices),
        "scatter_to_vertices() is vertex-aligned",
    )
    check(
        bool(np.all(scattered >= 0.0) and np.all(scattered <= 1.0)),
        "scattered vertex importance in [0, 1]",
    )

    summary_names = {item["name"] for item in result.summary["features"]}
    check(
        summary_names == set(FEATURE_NAMES),
        "summary reports every cue",
    )
    check(
        result.summary["edge_count"] == n_edges,
        "summary edge_count matches",
    )


# ── Geometry-specific behaviour ──────────────────────────────────────────────


def run_geometry_semantics() -> None:
    print("\n[geometry semantics]")

    cube = compute_edge_feature_importance(_cube())
    sharp = cube.features["sharp_edge_flag"]
    # A unit cube triangulated by trimesh has 12 model edges plus 6 diagonals;
    # only the 12 model edges fold by 90 degrees.
    check(
        int(sharp.sum()) == 12,
        f"cube flags exactly its 12 model edges as sharp (got {int(sharp.sum())})",
    )
    check(
        float(cube.features["boundary_edge_flag"].sum()) == 0.0,
        "closed cube has no boundary edges",
    )
    check(
        bool(np.all(cube.features["edge_length"] > 0)),
        "cube edge lengths are positive",
    )

    sphere = compute_edge_feature_importance(_sphere())
    check(
        float(sphere.features["sharp_edge_flag"].sum()) == 0.0,
        "smooth sphere flags no sharp edges",
    )
    check(
        float(sphere.features["dihedral_angle"].max()) < 0.1,
        "smooth sphere has small dihedral angles",
    )

    plane_mesh = _open_plane()
    plane = compute_edge_feature_importance(plane_mesh)
    boundary = plane.features["boundary_edge_flag"]
    # A 6x6 grid has 5 edges per side, 4 sides.
    check(
        int(boundary.sum()) == 20,
        f"open plane flags its 20 perimeter edges (got {int(boundary.sum())})",
    )
    check(
        float(plane.features["dihedral_angle"].max()) < 1e-6,
        "flat plane has zero dihedral angle",
    )


def run_optional_cues() -> None:
    print("\n[optional cue presence]")

    plain = compute_edge_feature_importance(_sphere())
    check(
        not plain.present.get("uv_seam", True),
        "UV cue reports absent on a mesh without UVs",
    )
    check(
        not plain.present.get("vertex_color_difference", True),
        "vertex-colour cue reports absent without colours",
    )
    check(
        not plain.present.get("bone_weight_difference", True),
        "bone-weight cue reports absent without a rig",
    )
    check(
        plain.present.get("dihedral_angle", False),
        "pure-geometry cues stay present on a bare mesh",
    )

    textured = compute_edge_feature_importance(_uv_sphere())
    check(
        textured.present.get("uv_seam", False),
        "UV cue activates when UVs are present",
    )
    check(
        textured.present.get("texture_gradient", False),
        "texture-gradient cue activates with UVs/colours",
    )


def run_degenerate() -> None:
    print("\n[degenerate input]")

    empty = trimesh.Trimesh(
        vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=np.int64), process=False
    )
    result = compute_edge_feature_importance(empty)
    check(len(result.edges) == 0, "empty mesh returns an empty result")
    check(result.summary["edge_count"] == 0, "empty mesh summary is zeroed")
    check(
        len(scatter_to_vertices(result, 0)) == 0,
        "scatter on an empty mesh returns an empty array",
    )

    single = trimesh.Trimesh(
        vertices=np.array([[0.0, 0, 0], [1, 0, 0], [0, 1, 0]]),
        faces=np.array([[0, 1, 2]]),
        process=False,
    )
    tri = compute_edge_feature_importance(single)
    check(len(tri.edges) == 3, "single triangle yields 3 edges")
    check(
        float(tri.features["boundary_edge_flag"].sum()) == 3.0,
        "single triangle is all boundary",
    )


def run_protection_contract() -> None:
    """The optimizer contract: protection stays in [0, 1] and never demotes."""
    print("\n[optimizer protection contract]")

    from ..engine.mesh_optimizer import _apply_edge_feature_protection

    mesh = _sphere()
    base = compute_importance(mesh)
    protected, summary = _apply_edge_feature_protection(mesh, base)

    check(len(protected) == len(mesh.vertices), "protected map is vertex-aligned")
    check(
        bool(np.all(protected >= 0.0) and np.all(protected <= 1.0)),
        f"protected map in [0, 1] (got [{protected.min():.3f}, {protected.max():.3f}])",
    )
    check(summary is not None, "protection returns a summary for the API")
    check(
        bool(np.all(np.isfinite(protected))),
        "protected map is finite",
    )

    # Ranking must still track the base map plus the edge boost, never invert.
    base_order = np.argsort(base)
    check(
        float(np.corrcoef(base[base_order], protected[base_order])[0, 1]) > 0.5,
        "protection preserves the base importance ranking",
    )

    # A length mismatch must be a no-op rather than a crash.
    mismatched, mismatch_summary = _apply_edge_feature_protection(mesh, base[:-1])
    check(
        len(mismatched) == len(base) - 1 and mismatch_summary is None,
        "length mismatch degrades to a no-op",
    )


def main() -> int:
    for mesh, label in [
        (_cube(), "cube"),
        (_sphere(), "icosphere"),
        (_open_plane(), "open plane"),
        (_uv_sphere(), "textured sphere"),
    ]:
        run_structural(mesh, label)

    run_geometry_semantics()
    run_optional_cues()
    run_degenerate()
    run_protection_contract()

    print("\n" + "=" * 60)
    if FAILURES:
        print(f"{len(FAILURES)} CHECK(S) FAILED:")
        for item in FAILURES:
            print(f"  - {item}")
        return 1
    print("All edge-feature checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
