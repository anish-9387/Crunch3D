"""
test_weighted_qem.py — Verify whether qualityweight actually changes QEM output.

Pipeline for each test mesh:

  1. Load trimesh, compute importance.
  2. Export to PyMeshLab, preclean.
  3. Inject importance as quality (PLY round-trip).
  4. Decimate with qualityweight=False  → output A
  5. Decimate with qualityweight=True   → output B
  6. Compare A vs B (metrics, topology, timing).

If the outputs are identical it proves qualityweight is broken in this
PyMeshLab version.
"""

import logging
import time

import numpy as np
import pymeshlab as pml
import trimesh

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("test_weighted_qem")

# ── helpers ──────────────────────────────────────────────────────────────────


def _build_colored_ply(ms: pml.MeshSet, importance: np.ndarray, n_verts: int) -> bool:
    """Inject importance as vertex colours via PLY round-trip (same as
    _inject_importance_as_quality in mesh_optimizer.py)."""
    import os
    import tempfile

    fd_plain, path_plain = tempfile.mkstemp(suffix=".ply")
    os.close(fd_plain)
    fd_colour, path_colour = tempfile.mkstemp(suffix="_clr.ply")
    os.close(fd_colour)

    try:
        ms.save_current_mesh(path_plain, binary=False, save_vertex_color=False)
        with open(path_plain, encoding="ascii") as f:
            content = f.read()
        lines = content.rstrip("\n").split("\n")

        header_end = -1
        for i, line in enumerate(lines):
            if line == "end_header":
                header_end = i
                break
        if header_end == -1:
            return False

        new_lines = []
        for line in lines:
            if line.startswith("element face"):
                new_lines.extend([
                    "property uchar red",
                    "property uchar green",
                    "property uchar blue",
                    "property uchar alpha",
                ])
            new_lines.append(line)

        shift = 4
        new_header_end = header_end + shift
        colour_byte = (np.clip(importance, 0.0, 1.0) * 255.0).astype(np.uint8)

        for v_idx in range(n_verts):
            orig_idx = header_end + 1 + v_idx
            new_idx = new_header_end + 1 + v_idx
            coords = lines[orig_idx].strip()
            c = int(colour_byte[v_idx])
            new_lines[new_idx] = f"{coords} {c} {c} {c} 255"

        with open(path_colour, "w", encoding="ascii") as f:
            f.write("\n".join(new_lines) + "\n")

        old_id = ms.current_mesh_id()
        ms.load_new_mesh(path_colour)
        ms.apply_filter(
            "compute_scalar_by_function_per_vertex",
            q="(r+g+b)/(3.0*255.0)",
            normalize=False,
        )
        ms.set_current_mesh(old_id)
        ms.delete_current_mesh()
        return True

    except Exception as exc:
        log.warning("PLY injection failed: %s", exc)
        return False
    finally:
        for p in (path_plain, path_colour):
            try:
                os.unlink(p)
            except OSError:
                pass


# ── test runner ──────────────────────────────────────────────────────────────


def run_test(mesh: trimesh.Trimesh, label: str, target_faces: int):
    log.info("=" * 60)
    log.info("Test: %s  (%d verts, %d faces → target %d)",
             label, len(mesh.vertices), len(mesh.faces), target_faces)

    from backend.services.importance_mapper import compute_importance

    # --- load into PyMeshLab ---
    v = mesh.vertices.astype(np.float64)
    f = mesh.faces.astype(np.int32)

    def _preclean(ms: pml.MeshSet):
        for filt, kw in [
            ("meshing_remove_duplicate_vertices", {}),
            ("meshing_remove_duplicate_faces", {}),
            ("meshing_remove_unreferenced_vertices", {}),
            ("meshing_repair_non_manifold_vertices", {}),
            ("meshing_repair_non_manifold_edges", {"method": 0}),
        ]:
            try:
                ms.apply_filter(filt, **kw)
            except Exception:
                continue

    def _run_qem(qualityweight: bool) -> pml.Mesh:
        ms = pml.MeshSet()
        ms.add_mesh(pml.Mesh(v.copy(), f.copy()), "test")
        _preclean(ms)
        n_verts = ms.current_mesh().vertex_number()

        # --- Compute importance AFTER preclean so vertex count matches ---
        pml_m = ms.current_mesh()
        verts = np.asarray(pml_m.vertex_matrix(), dtype=np.float64)
        faces = np.asarray(pml_m.face_matrix(), dtype=np.int64)
        tri = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
        importance = compute_importance(tri)
        log.info("  Importance: min=%.4f max=%.4f mean=%.4f  (len=%d)",
                 importance.min(), importance.max(), importance.mean(), len(importance))

        assert len(importance) == n_verts, (
            f"Importance {len(importance)} != vertex count {n_verts} after preclean"
        )

        # inject importance
        ok = _build_colored_ply(ms, importance, n_verts)
        log.info("  Injection: %s", ok)

        scalar = ms.current_mesh().vertex_scalar_array()
        log.info("  Quality field: min=%.4f max=%.4f",
                 scalar.min(), scalar.max())

        # decimate
        t0 = time.perf_counter()
        ms.apply_filter(
            "meshing_decimation_quadric_edge_collapse",
            targetfacenum=int(max(target_faces, 4)),
            qualityweight=qualityweight,
            preservenormal=True,
            preserveboundary=True,
            preservetopology=False,
            planarquadric=False,
            qualitythr=0.3,
            autoclean=True,
            selected=False,
        )
        elapsed = time.perf_counter() - t0
        log.info("  qualityweight=%-5s  %d verts  %d faces  (%.3f s)",
                 str(qualityweight),
                 ms.current_mesh().vertex_number(),
                 ms.current_mesh().face_number(),
                 elapsed)

        return ms.current_mesh()

    log.info("  ── Run qualityweight=False ──")
    result_a = _run_qem(qualityweight=False)

    log.info("  ── Run qualityweight=True ──")
    result_b = _run_qem(qualityweight=True)

    # --- comparison ---
    log.info("")
    log.info("  ── Comparison ──")
    if result_a is None or result_b is None:
        log.error("  One or both runs failed — skipping comparison")
        return

    # topology
    va, vb = result_a.vertex_matrix(), result_b.vertex_matrix()
    fa, fb = result_a.face_matrix(), result_b.face_matrix()
    log.info("  Vertices:  A=%d  B=%d  %s",
             va.shape[0], vb.shape[0],
             "IDENTICAL" if va.shape[0] == vb.shape[0] else "DIFFERENT")
    log.info("  Faces:     A=%d  B=%d  %s",
             fa.shape[0], fb.shape[0],
             "IDENTICAL" if fa.shape[0] == fb.shape[0] else "DIFFERENT")

    # byte identity (save to temp PLY and compare)
    import tempfile, os
    _, ta = tempfile.mkstemp(suffix=".ply")
    os.close(_)
    _, tb = tempfile.mkstemp(suffix=".ply")
    os.close(_)
    try:
        ms_a = pml.MeshSet()
        ms_a.add_mesh(result_a, "A")
        ms_a.save_current_mesh(ta, binary=False)
        ms_b = pml.MeshSet()
        ms_b.add_mesh(result_b, "B")
        ms_b.save_current_mesh(tb, binary=False)

        with open(ta) as fa_:
            ca = fa_.read()
        with open(tb) as fb_:
            cb = fb_.read()
        log.info("  Byte-identical: %s", "YES" if ca == cb else "NO")
    finally:
        for p in (ta, tb):
            try:
                os.unlink(p)
            except OSError:
                pass

    # vertex difference (which vertices survived)
    if va.shape[0] == vb.shape[0]:
        diff = np.abs(va - vb).max()
        log.info("  Max vertex-position diff: %.6f", diff)
    else:
        log.info("  Different vertex counts — cannot compare position-wise")

    # Check which importance levels survive
    # Re-import importance values for the surviving vertices
    log.info("")
    log.info("  ── Importance preservation ──")
    # Compute Hausdorff if possible
    try:
        ha = pml.MeshSet()
        ha.add_mesh(result_a, "A")
        hb = pml.MeshSet()
        hb.add_mesh(result_b, "B")
        hd = ha.get_hausdorff_distance(hb)
        log.info("  Hausdorff distance:  %.6f  (%.6f  mean/ RMS)", hd, hd)
    except Exception as e:
        log.info("  Hausdorff: N/A  (%s)", e)

    log.info("")
    return result_a, result_b


# ── main ────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    # --- Synthetic mesh A: box with duplicated verts ---
    v = np.array([
        [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
        [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
        [-1, -1, 0], [0, -1, 0], [0, 0, 0], [-1, 0, 0],
    ], dtype=np.float64)
    f = np.array([
        [0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7],
        [8, 9, 10], [8, 10, 11],
    ], dtype=np.int32)
    mesh_a = trimesh.Trimesh(vertices=v, faces=f, process=False)

    # --- Synthetic mesh B: grid with a bump ---
    res = 8
    vv, ff = [], []
    for j in range(res):
        for i in range(res):
            x = i / (res - 1) * 2 - 1
            y = j / (res - 1) * 2 - 1
            dist = np.sqrt(x ** 2 + y ** 2)
            z = max(0, 0.3 * (1 - dist * 1.5)) if dist < 0.66 else 0
            vv.append([x, y, z])
    vv = np.array(vv, dtype=np.float64)
    for j in range(res - 1):
        for i in range(res - 1):
            a = j * res + i
            b = a + 1
            c = (j + 1) * res + i
            d = c + 1
            ff.append([a, b, c])
            ff.append([b, d, c])
    ff = np.array(ff, dtype=np.int32)
    mesh_b = trimesh.Trimesh(vertices=vv, faces=ff, process=False)

    tests = [
        (mesh_a, "Duplicated quad", 4),
        (mesh_b, "Grid bump", 40),
    ]

    # --- Try real mesh if available ---
    import os as _os
    _real_paths = [
        "/Users/aashisoni/Codes/team projects/Optimesh/backend/uploads/9736d49c089f/spartan_armour_mkv_-_halo_reach (1).glb",
    ]
    for p in _real_paths:
        if _os.path.exists(p):
            try:
                scene = trimesh.load(p, force="scene")
                parts = [g for g in scene.geometry.values()
                         if isinstance(g, trimesh.Trimesh) and len(g.faces) > 0]
                if parts:
                    real_mesh = trimesh.util.concatenate(parts)
                    target = max(4, len(real_mesh.faces) // 3)
                    tests.append((real_mesh, "Halo armour", target))
            except Exception as e:
                log.warning("Could not load %s: %s", p, e)

    for mesh, label, target in tests:
        run_test(mesh, label, target)
        print()
