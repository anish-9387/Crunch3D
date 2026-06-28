"""
forensic_transform_trace.py — Trace transforms of every component through
the entire optimisation pipeline to identify where positions drift.

Usage:
    python backend/debug/forensic_transform_trace.py  <glb-file>

This script mirrors the exact steps in mesh_optimizer.py without
modifying any source code.  It prints the state at each stage so the
user can pinpoint where transforms are lost.
"""

from __future__ import annotations

import os
import sys
import tempfile
import textwrap
import traceback

import numpy as np
import pymeshlab as pml
import trimesh

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _centroid(v: np.ndarray) -> np.ndarray:
    return v.mean(axis=0)


def _bbox_center(v: np.ndarray) -> np.ndarray:
    return (v.min(axis=0) + v.max(axis=0)) / 2.0


def _describe(verts: np.ndarray, label: str = "", indent: str = "") -> str:
    if verts is None or verts.size == 0:
        return f"{indent}{label}: (no vertices)"
    c = _centroid(verts)
    bc = _bbox_center(verts)
    vmin = verts.min(axis=0)
    vmax = verts.max(axis=0)
    return (
        f"{indent}{label}\n"
        f"{indent}  vertices : {verts.shape[0]}\n"
        f"{indent}  centroid : ({c[0]:8.4f}, {c[1]:8.4f}, {c[2]:8.4f})\n"
        f"{indent}  bbox_ctr : ({bc[0]:8.4f}, {bc[1]:8.4f}, {bc[2]:8.4f})\n"
        f"{indent}  bbox_min : ({vmin[0]:8.4f}, {vmin[1]:8.4f}, {vmin[2]:8.4f})\n"
        f"{indent}  bbox_max : ({vmax[0]:8.4f}, {vmax[1]:8.4f}, {vmax[2]:8.4f})\n"
    )


def _describe_scene(
    scene: trimesh.Scene,
    label: str,
    indent: str = "",
) -> None:
    print(f"\n{indent}╔══ {label} ══╗")
    for node_name in scene.graph.nodes_geometry:
        val = scene.graph[node_name]
        transform = val[0]
        geom_name = val[1] if len(val) >= 2 else node_name
        geom = scene.geometry[geom_name]
        if not isinstance(geom, trimesh.Trimesh) or len(geom.faces) == 0:
            continue
        v = geom.vertices
        # world-space vertices
        vw = trimesh.transformations.transform_points(v, transform)

        t = transform[:3, 3]
        s = np.linalg.norm(transform[:3, :3], axis=0)
        print(
            f"{indent}  node='{node_name}'  geom='{geom_name}'\n"
            f"{indent}    local  verts={v.shape[0]}  faces={geom.faces.shape[0]}"
        )
        print(_describe(v, "local  ", indent + "    "), end="")
        print(_describe(vw, "world  ", indent + "    "), end="")
        print(
            f"{indent}    transform: t=({t[0]:.4f}, {t[1]:.4f}, {t[2]:.4f})  "
            f"s=({s[0]:.4f}, {s[1]:.4f}, {s[2]:.4f})"
        )
    print(f"{indent}╚══ end {label} ══╝")


def _describe_trimesh_list(
    meshes: list[tuple[str, trimesh.Trimesh]],
    label: str,
    indent: str = "",
) -> None:
    print(f"\n{indent}╔══ {label} ══╗")
    for name, m in meshes:
        if m is None or len(m.faces) == 0:
            continue
        v = m.vertices
        c = _centroid(v)
        bc = _bbox_center(v)
        print(
            f"{indent}  '{name}'  verts={v.shape[0]}  faces={m.faces.shape[0]}\n"
            f"{indent}    centroid : ({c[0]:8.4f}, {c[1]:8.4f}, {c[2]:8.4f})\n"
            f"{indent}    bbox_ctr : ({bc[0]:8.4f}, {bc[1]:8.4f}, {bc[2]:8.4f})"
        )
    print(f"{indent}╚══ end {label} ══╝")


def _describe_pml_mesh(ms: pml.MeshSet, label: str, indent: str = "") -> None:
    v = np.asarray(ms.current_mesh().vertex_matrix(), dtype=np.float64)
    f = np.asarray(ms.current_mesh().face_matrix(), dtype=np.int64)
    c = _centroid(v)
    bc = _bbox_center(v)
    print(
        f"\n{indent}── {label} ──\n"
        f"{indent}  verts={v.shape[0]}  faces={f.shape[0]}\n"
        f"{indent}  centroid : ({c[0]:8.4f}, {c[1]:8.4f}, {c[2]:8.4f})\n"
        f"{indent}  bbox_ctr : ({bc[0]:8.4f}, {bc[1]:8.4f}, {bc[2]:8.4f})"
    )


# ═══════════════════════════════════════════════════════════════════════
# Exact pipeline steps (mirrored from mesh_optimizer.py)
# ═══════════════════════════════════════════════════════════════════════


def trace_pipeline(input_path: str) -> None:
    print("=" * 72)
    print("  FORENSIC TRANSFORM TRACE")
    print("=" * 72)

    # ── 1. Original scene after loading ──────────────────────────────
    print("\n" + "#" * 72)
    print("#  STAGE 1: Original scene after loading (trimesh.load)")
    print("#" * 72)

    loaded = trimesh.load(input_path, process=False)
    is_scene = isinstance(loaded, trimesh.Scene)

    if is_scene:
        print(f"Loaded as Scene with {len(loaded.geometry)} geometries")
        _describe_scene(loaded, "ORIGINAL SCENE (with world transforms)")
    else:
        print(f"Loaded as single Trimesh: v={len(loaded.vertices)} f={len(loaded.faces)}")
        _describe_trimesh_list([("(root)", loaded)], "ORIGINAL SINGLE MESH")

    # ── 2. After _load_components (current pipeline) ─────────────────
    print("\n" + "#" * 72)
    print("#  STAGE 2: _load_components — geometry.values() EXTRACTED")
    print("#  (this is where the pipeline discards scene graph)")
    print("#" * 72)

    components_raw: list[trimesh.Trimesh] = []
    component_names: list[str] = []
    if is_scene:
        for name, geom in loaded.geometry.items():
            if isinstance(geom, trimesh.Trimesh) and len(geom.faces) > 0:
                components_raw.append(geom)
                component_names.append(name)
                local_c = _centroid(geom.vertices)
                # Also compute what world-space would be
                # find the node that references this geometry
                world_verts = None
                node_name = name
                for nn in loaded.graph.nodes_geometry:
                    gn = loaded.graph[nn][1] if len(loaded.graph[nn]) >= 2 else ""
                    if gn == name:
                        xform = loaded.graph[nn][0]
                        world_verts = trimesh.transformations.transform_points(
                            geom.vertices.copy(), xform
                        )
                        node_name = nn
                        break
                wc = _centroid(world_verts) if world_verts is not None else local_c

                print(f"\n  Component '{name}':")
                print(f"    Node:       {node_name}")
                print(f"    Local  centroid: ({local_c[0]:8.4f}, {local_c[1]:8.4f}, {local_c[2]:8.4f})")
                print(f"    World  centroid: ({wc[0]:8.4f}, {wc[1]:8.4f}, {wc[2]:8.4f})")
                print(f"    Δ (world-local): ({wc[0]-local_c[0]:8.4f}, {wc[1]-local_c[1]:8.4f}, {wc[2]-local_c[2]:8.4f})")
                print(f"    World transform is LOST at this stage")
    else:
        components_raw.append(loaded)
        component_names.append("(root)")

    print(f"\n  >>> {len(components_raw)} components extracted (transforms discarded) <<<")

    # ── 3. face-target distribution & per-component trace ────────────
    total_faces = sum(len(c.faces) for c in components_raw)
    target_faces = max(100, int(total_faces * 0.3))  # 30% default target

    print(f"\n{'#' * 72}")
    print(f"#  Target faces: {target_faces}  (total original: {total_faces})")
    print(f"#  Targets are proportional per component using vertex-ratio")
    print(f"{'#' * 72}")

    output_parts: list[trimesh.Trimesh] = []

    for idx, (name, mesh) in enumerate(zip(component_names, components_raw)):
        if len(mesh.faces) == 0:
            continue

        ratio = len(mesh.faces) / total_faces if total_faces > 0 else 1.0
        comp_target = max(4, int(target_faces * ratio))

        print(f"\n{'━' * 72}")
        print(f"  COMPONENT {idx}: '{name}'")
        print(f"    Face ratio: {ratio:.4f}  → target {comp_target} faces")
        print(f"    Current (local space): {len(mesh.vertices)}v {len(mesh.faces)}f")

        local_c = _centroid(mesh.vertices)
        print(f"    Local centroid: ({local_c[0]:8.4f}, {local_c[1]:8.4f}, {local_c[2]:8.4f})")

        # ── 4. OBJ export for PyMeshLab (_component_to_pymeshlab) ──
        print(f"\n    ── STAGE 4-5: _component_to_pymeshlab (OBJ round-trip) ──")
        tmp_obj = tempfile.NamedTemporaryFile(suffix=".obj", delete=False)
        tmp_path = tmp_obj.name
        tmp_obj.close()
        try:
            mesh.export(tmp_path)
            ms = pml.MeshSet()
            ms.load_new_mesh(tmp_path)
        finally:
            os.unlink(tmp_path)

        _describe_pml_mesh(ms, "After OBJ export/import to PyMeshLab", indent="    ")

        # ── 6. Preclean (_apply_structure_preclean) ─────────────────
        print(f"\n    ── STAGE 6: _apply_structure_preclean ──")
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
                pass

        _describe_pml_mesh(ms, "After preclean", indent="    ")

        # ── 7. Decimation (_apply_decimation) ───────────────────────
        print(f"\n    ── STAGE 7: Decimation (qualityweight=True) ──")
        dec_target = int(max(comp_target, 4))
        ms.apply_filter(
            "meshing_decimation_quadric_edge_collapse",
            targetfacenum=dec_target,
            preservenormal=True,
            preserveboundary=True,
            preservetopology=False,
            planarquadric=False,
            qualitythr=0.3,
            qualityweight=True,
            selected=False,
        )
        _describe_pml_mesh(ms, "After decimation", indent="    ")

        # ── 8. Convert back to Trimesh (_pymeshlab_to_trimesh) ──────
        print(f"\n    ── STAGE 8-9: _pymeshlab_to_trimesh (OBJ round-trip) ──")
        tmp2 = tempfile.NamedTemporaryFile(suffix=".obj", delete=False)
        tmp2_path = tmp2.name
        tmp2.close()
        try:
            ms.save_current_mesh(tmp2_path)
            result = trimesh.load(tmp2_path, process=False)
            if isinstance(result, trimesh.Scene):
                parts = [
                    g for g in result.geometry.values()
                    if isinstance(g, trimesh.Trimesh) and len(g.faces) > 0
                ]
                result_mesh = trimesh.util.concatenate(parts) if parts else None
            elif isinstance(result, trimesh.Trimesh) and len(result.faces) > 0:
                result_mesh = result
            else:
                result_mesh = None
        finally:
            os.unlink(tmp2_path)

        if result_mesh is not None:
            _describe_trimesh_list(
                [(name, result_mesh)],
                f"Converted back to Trimesh",
                indent="    ",
            )
            output_parts.append(result_mesh)
        else:
            print("    Result: None — component lost")
            continue

        # Compare local position before/after
        rc = _centroid(result_mesh.vertices)
        drift = np.linalg.norm(rc - local_c)
        print(f"\n    >>> CENTROID DRIFT from original local space: {drift:.6f}")
        print(f"    >>> Original local centroid: ({local_c[0]:8.4f}, {local_c[1]:8.4f}, {local_c[2]:8.4f})")
        print(f"    >>> After pipeline centroid: ({rc[0]:8.4f}, {rc[1]:8.4f}, {rc[2]:8.4f})")
        if drift > 1e-4:
            print(f"    ⚠ DRIFT DETECTED — component moved within local space")
        else:
            print(f"    ✓ Local-space position preserved within tolerance")

    # ── 9. Final concatenation ──────────────────────────────────────
    print(f"\n{'#' * 72}")
    print(f"#  STAGE 9: trimesh.util.concatenate(output_parts)")
    print(f"#  (Merges all components into a single mesh — NO transforms applied)")
    print(f"{'#' * 72}")

    if len(output_parts) == 0:
        print("  No output parts — aborting.")
        return

    if len(output_parts) == 1:
        final = output_parts[0]
    else:
        final = trimesh.util.concatenate(output_parts)

    fc = _centroid(final.vertices)
    fbc = _bbox_center(final.vertices)
    print(f"\n  Merged result: {len(final.vertices)}v {len(final.faces)}f")
    print(f"  Centroid : ({fc[0]:8.4f}, {fc[1]:8.4f}, {fc[2]:8.4f})")
    print(f"  BBox ctr : ({fbc[0]:8.4f}, {fbc[1]:8.4f}, {fbc[2]:8.4f})")

    # ── 10. Expected world-space positions (for comparison) ─────────
    if is_scene:
        print(f"\n{'#' * 72}")
        print(f"#  REFERENCE: Expected world-space positions")
        print(f"#  (what the meshes WOULD look like if transforms were applied)")
        print(f"{'#' * 72}")
        all_world_verts = []
        for node_name in loaded.graph.nodes_geometry:
            val2 = loaded.graph[node_name]
            transform = val2[0]; geom_name = val2[1] if len(val2) >= 2 else node_name
            geom = loaded.geometry.get(geom_name)
            if geom is None or not isinstance(geom, trimesh.Trimesh) or len(geom.faces) == 0:
                continue
            vw = trimesh.transformations.transform_points(geom.vertices, transform)
            all_world_verts.append(vw)

        if all_world_verts:
            all_vw = np.vstack(all_world_verts)
            wc = _centroid(all_vw)
            wbc = _bbox_center(all_vw)
            print(f"  World-space combined: {all_vw.shape[0]}v")
            print(f"  World centroid : ({wc[0]:8.4f}, {wc[1]:8.4f}, {wc[2]:8.4f})")
            print(f"  World BBox ctr : ({wbc[0]:8.4f}, {wbc[1]:8.4f}, {wbc[2]:8.4f})")

        # ── Compare: merged output vs world-space reference ─────────
        print(f"\n{'#' * 72}")
        print(f"#  COMPARISON: Merged output vs World-space reference")
        print(f"{'#' * 72}")
        if all_world_verts:
            ref_centroid = _centroid(all_vw)
            out_centroid = _centroid(final.vertices)
            delta = np.linalg.norm(out_centroid - ref_centroid)
            print(f"  World ref centroid: ({ref_centroid[0]:8.4f}, {ref_centroid[1]:8.4f}, {ref_centroid[2]:8.4f})")
            print(f"  Output   centroid: ({out_centroid[0]:8.4f}, {out_centroid[1]:8.4f}, {out_centroid[2]:8.4f})")
            print(f"  Δ centroid: {delta:.4f}")
            if delta > 1e-3:
                print(f"  ❌ TRANSFORMS ARE DISCARDED — output is in LOCAL space")
                print(f"  ❌ All components collapse to wrong positions")
            else:
                print(f"  ✓ Transform position matched (unlikely given code analysis)")

    # ── 11. Scene hierarchy loss ─────────────────────────────────────
    print(f"\n{'#' * 72}")
    print(f"#  CONCLUSION: Scene hierarchy")
    print(f"{'#' * 72}")
    if is_scene:
        print(f"  Original scene: {len(loaded.graph.nodes_geometry)} meshes in a hierarchy")
        print(f"  Output: single merged mesh — NO hierarchy, NO transforms")
        print(f"  Original parent-child relationships: LOST")
        print(f"  Export: single mesh file — not a Scene")

    # ── World-space bounding overlay ─────────────────────────────────
    print(f"\n{'#' * 72}")
    print(f"#  OVERLAY CHECK: Which components would overlap")
    print(f"#  in local space vs world space?")
    print(f"{'#' * 72}")

    if is_scene:
        for node_name in loaded.graph.nodes_geometry:
            val2 = loaded.graph[node_name]
            transform = val2[0]; geom_name = val2[1] if len(val2) >= 2 else node_name
            geom = loaded.geometry.get(geom_name)
            if geom is None or not isinstance(geom, trimesh.Trimesh) or len(geom.faces) == 0:
                continue

            v_local = geom.vertices
            v_world = trimesh.transformations.transform_points(v_local.copy(), transform)

            lc = _centroid(v_local)
            wc = _centroid(v_world)
            t = transform[:3, 3]

            # Find components that share similar local-space origin
            print(f"\n  '{geom_name}'")
            print(f"    Local   centroid: ({lc[0]:8.4f}, {lc[1]:8.4f}, {lc[2]:8.4f})")
            print(f"    World   centroid: ({wc[0]:8.4f}, {wc[1]:8.4f}, {wc[2]:8.4f})")
            print(f"    Node translate:   ({t[0]:8.4f}, {t[1]:8.4f}, {t[2]:8.4f})")
            print(f"    IN-PIPELINE (local) position: ({lc[0]:8.4f}, {lc[1]:8.4f}, {lc[2]:8.4f})")
            print(f"    EXPECTED   position:          ({wc[0]:8.4f}, {wc[1]:8.4f}, {wc[2]:8.4f})")

    print("\n" + "=" * 72)
    print("  END OF TRACE")
    print("=" * 72)


# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python forensic_transform_trace.py <glb-file>")
        sys.exit(1)
    trace_pipeline(sys.argv[1])
