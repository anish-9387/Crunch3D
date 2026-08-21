"""tests/test_halfedge.py — half-edge structure and local collapse (§6).

    python -m model.tests.test_halfedge
"""

from __future__ import annotations

import numpy as np

from ..geometry.halfedge import HalfEdgeMesh
from ..geometry.normalize import normalize_points
from ..geometry.validation import validate
from ._harness import Checks, cube, open_plane, run, sphere


def _twin_consistency(mesh: HalfEdgeMesh) -> bool:
    for h in range(3 * len(mesh.faces)):
        if not mesh.face_alive[h // 3]:
            continue
        t = mesh.twin(h)
        if t < 0:
            continue
        if mesh.twin(t) != h:
            return False
        if mesh.origin(h) != mesh.dest(t) or mesh.dest(h) != mesh.origin(t):
            return False
    return True


def structural(c: Checks, tri, label: str, expect_closed: bool) -> None:
    c.section(f"{label} — structure")
    mesh = HalfEdgeMesh.from_trimesh(tri)

    c.ok(mesh.n_faces == len(tri.faces), "alive face count matches input")
    c.ok(mesh.n_verts == len(tri.vertices), "alive vertex count matches input")
    c.ok(_twin_consistency(mesh), "twin(twin(h)) == h and endpoints agree")

    for h in range(0, 3 * len(mesh.faces), max(1, len(mesh.faces) // 5) * 3 or 1):
        if not mesh.face_alive[h // 3]:
            continue
        c.ok(
            mesh.dest(h) == mesh.origin(mesh.next_he(h))
            and mesh.origin(h) == mesh.dest(mesh.prev_he(h))
            and mesh.face_of(h) == h // 3,
            f"next/prev/face are consistent at h={h}",
        )
        break

    edges = mesh.unique_edges()
    c.ok(bool(np.all(edges[:, 0] < edges[:, 1])), "unique_edges are sorted (min, max)")
    c.ok(len(np.unique(edges, axis=0)) == len(edges), "unique_edges has no duplicates")

    expected_edges = len(tri.edges_unique)
    c.ok(len(edges) == expected_edges, f"edge count matches trimesh ({len(edges)} vs {expected_edges})")

    boundary = sum(1 for e in edges if mesh.is_boundary_edge(int(e[0]), int(e[1])))
    if expect_closed:
        c.ok(boundary == 0, "closed surface reports no boundary edges")
    else:
        c.ok(boundary > 0, "open surface reports boundary edges")

    v = int(edges[0, 0])
    ring = mesh.one_ring(v)
    c.ok(v not in ring, "one_ring excludes the vertex itself")
    c.ok(len(ring) == mesh.valence(v), "valence equals one-ring size")
    c.ok(
        all(len(mesh.edge_faces(v, int(w))) >= 1 for w in ring),
        "every one-ring neighbour shares at least one face",
    )


def collapse_behaviour(c: Checks) -> None:
    c.section("collapse — invariants")
    tri = sphere(3)
    mesh = HalfEdgeMesh.from_trimesh(tri)
    faces_before = mesh.n_faces
    verts_before = mesh.n_verts

    edges = mesh.unique_edges()
    u, v = int(edges[0, 0]), int(edges[0, 1])
    midpoint = 0.5 * (mesh.verts[u] + mesh.verts[v])

    c.ok(mesh.collapse(u, v, midpoint), "collapse of a live interior edge succeeds")
    c.ok(mesh.n_faces == faces_before - 2, "interior collapse removes exactly 2 faces")
    c.ok(mesh.n_verts == verts_before - 1, "interior collapse removes exactly 1 vertex")
    c.ok(not mesh.vert_alive[u], "the removed endpoint is dead")
    c.ok(np.allclose(mesh.verts[v], midpoint), "the survivor moved to the new position")
    c.ok(_twin_consistency(mesh), "twins stay consistent after a collapse")
    c.ok(u not in mesh.one_ring(v), "the dead vertex left the survivor's one-ring")
    c.ok(not mesh.collapse(u, v, midpoint), "re-collapsing a dead edge is refused")

    for _ in range(60):
        live = mesh.unique_edges()
        if not len(live):
            break
        a, b = int(live[0, 0]), int(live[0, 1])
        mesh.collapse(a, b, 0.5 * (mesh.verts[a] + mesh.verts[b]))
    c.ok(_twin_consistency(mesh), "twins survive a long collapse sequence")

    verts, faces, remap = mesh.compact()
    c.ok(len(faces) == mesh.n_faces, "compact() keeps every alive face")
    c.ok(faces.max() < len(verts), "compact() reindexes faces inside the new vertex range")
    c.ok(
        len(np.unique(faces)) == len(verts),
        "compact() drops every unreferenced vertex",
    )
    c.ok(
        bool(np.all(remap[mesh.vert_alive & (remap >= 0)] >= 0)),
        "the remap covers the surviving vertices",
    )


def euler_characteristic(c: Checks) -> None:
    c.section("collapse — Euler characteristic")
    mesh = HalfEdgeMesh.from_trimesh(sphere(3))
    before = mesh.n_verts - len(mesh.unique_edges()) + mesh.n_faces

    edges = mesh.unique_edges()
    done = 0
    for u, v in edges[:25]:
        u, v = int(u), int(v)
        if not (mesh.vert_alive[u] and mesh.vert_alive[v]):
            continue
        if len(mesh.edge_faces(u, v)) != 2:
            continue
        shared = mesh.one_ring(u) & mesh.one_ring(v)
        if len(shared) != 2:
            continue
        mesh.collapse(u, v, 0.5 * (mesh.verts[u] + mesh.verts[v]))
        done += 1

    after = mesh.n_verts - len(mesh.unique_edges()) + mesh.n_faces
    c.ok(done > 0, f"performed {done} link-condition-safe collapses")
    c.ok(after == before == 2, f"chi stays 2 for a sphere (before={before}, after={after})")


def open_surface_collapse(c: Checks) -> None:
    c.section("collapse — boundary edge")
    mesh = HalfEdgeMesh.from_trimesh(open_plane(6))
    faces_before = mesh.n_faces

    target = None
    for u, v in mesh.unique_edges():
        u, v = int(u), int(v)
        if len(mesh.edge_faces(u, v)) == 1 and len(mesh.one_ring(u) & mesh.one_ring(v)) == 1:
            target = (u, v)
            break

    c.ok(target is not None, "found a boundary edge with a valid link")
    if target:
        u, v = target
        mesh.collapse(u, v, 0.5 * (mesh.verts[u] + mesh.verts[v]))
        c.ok(mesh.n_faces == faces_before - 1, "boundary collapse removes exactly 1 face")
        c.ok(_twin_consistency(mesh), "twins stay consistent after a boundary collapse")


def validation_report(c: Checks) -> None:
    c.section("validation report (§5.2)")
    tri = cube()
    report = validate(np.asarray(tri.vertices), np.asarray(tri.faces))
    c.ok(report.vertices == len(tri.vertices), "reports the vertex count")
    c.ok(report.faces == len(tri.faces), "reports the face count")
    c.ok(report.boundary_edges == 0, "closed cube has no boundary edges")
    c.ok(report.non_manifold_edges == 0, "closed cube has no non-manifold edges")
    c.ok(report.degenerate_faces == 0, "closed cube has no degenerate faces")
    c.ok(report.components == 1, "closed cube is one component")
    c.ok(report.is_clean, "closed cube validates clean")
    c.ok(set(report.to_dict()) >= {
        "vertices", "faces", "boundary_edges", "non_manifold_edges",
        "degenerate_faces", "components",
    }, "to_dict() carries the documented keys")

    plane = validate(*(np.asarray(open_plane(6).vertices), np.asarray(open_plane(6).faces)))
    c.ok(plane.boundary_edges == 20, f"6x6 grid has 20 boundary edges (got {plane.boundary_edges})")

    verts = np.array([[0.0, 0, 0], [1, 0, 0], [2, 0, 0], [0, 1, 0]])
    faces = np.array([[0, 1, 2], [0, 1, 3], [0, 1, 3]])
    messy = validate(verts, faces)
    c.ok(messy.degenerate_faces == 1, "collinear triangle is flagged degenerate")
    c.ok(messy.duplicate_faces == 1, "repeated triangle is flagged duplicate")
    c.ok(messy.non_manifold_edges == 1, "edge shared by 3 faces is flagged non-manifold")

    nan_report = validate(np.array([[np.nan, 0, 0], [1, 0, 0], [0, 1, 0]]), np.array([[0, 1, 2]]))
    c.ok(nan_report.nan_vertices == 1, "NaN vertex is detected")

    two = np.vstack([np.asarray(cube().vertices), np.asarray(cube().vertices) + 10.0])
    two_faces = np.vstack([np.asarray(cube().faces), np.asarray(cube().faces) + len(cube().vertices)])
    c.ok(validate(two, two_faces).components == 2, "two disjoint cubes report 2 components")


def normalization(c: Checks) -> None:
    c.section("scale normalization (§5.3)")
    points = np.asarray(sphere(2).vertices) * 37.0 + np.array([100.0, -5.0, 8.0])
    normalized, transform = normalize_points(points)

    diagonal = np.linalg.norm(normalized.max(axis=0) - normalized.min(axis=0))
    c.close(float(diagonal), 1.0, 1e-9, "bbox diagonal normalizes to 1")
    c.ok(
        bool(np.allclose(normalized.mean(axis=0), 0.0, atol=1e-9)),
        "centroid lands on the origin",
    )
    c.ok(
        bool(np.allclose(transform.invert(normalized), points, atol=1e-9)),
        "invert() recovers the original coordinates",
    )
    c.ok(set(transform.to_dict()) == {"centroid", "scale"}, "to_dict() is JSON-safe")


def main() -> int:
    c = Checks("half-edge / geometry")
    structural(c, cube(), "cube", expect_closed=True)
    structural(c, sphere(3), "icosphere", expect_closed=True)
    structural(c, open_plane(6), "open plane", expect_closed=False)
    collapse_behaviour(c)
    euler_characteristic(c)
    open_surface_collapse(c)
    validation_report(c)
    normalization(c)
    return c.finish()


if __name__ == "__main__":
    run(main)
