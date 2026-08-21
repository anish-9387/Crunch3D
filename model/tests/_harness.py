"""tests/_harness.py — tiny check/report helper shared by the test scripts.

Mirrors the convention already used by ``model/debug/test_*.py``: print one line
per assertion, collect failures, exit non-zero so a run can gate a commit.
No pytest dependency.
"""

from __future__ import annotations

import sys

import numpy as np


class Checks:
    def __init__(self, title: str):
        self.title = title
        self.failures: list[str] = []
        self.passed = 0
        print(f"\n=== {title} ===")

    def section(self, label: str) -> None:
        print(f"\n[{label}]")

    def ok(self, condition: bool, label: str) -> bool:
        if condition:
            self.passed += 1
            print(f"    PASS  {label}")
            return True
        self.failures.append(label)
        print(f"    FAIL  {label}")
        return False

    def close(self, condition_value: float, expected: float, tol: float, label: str) -> bool:
        return self.ok(abs(condition_value - expected) <= tol, f"{label} ({condition_value:.6g})")

    def finish(self) -> int:
        print("\n" + "-" * 62)
        if self.failures:
            print(f"{self.title}: {len(self.failures)} of {self.passed + len(self.failures)} checks FAILED")
            for item in self.failures:
                print(f"  - {item}")
            return 1
        print(f"{self.title}: all {self.passed} checks passed")
        return 0


def run(main) -> None:
    sys.exit(main())


# ── shared fixtures ─────────────────────────────────────────────────────────


def cube():
    import trimesh

    return trimesh.creation.box(extents=(1.0, 1.0, 1.0))


def sphere(subdivisions: int = 3):
    import trimesh

    return trimesh.creation.icosphere(subdivisions=subdivisions, radius=1.0)


def open_plane(n: int = 6):
    """Flat n×n grid — 4(n-1) perimeter edges, zero dihedral everywhere."""
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


def uv_sphere(subdivisions: int = 2):
    """Sphere carrying UVs and vertex colours, for the asset-aware cues."""
    import trimesh

    mesh = sphere(subdivisions)
    verts = np.asarray(mesh.vertices)
    uv = np.column_stack([
        (np.arctan2(verts[:, 2], verts[:, 0]) + np.pi) / (2 * np.pi),
        (verts[:, 1] + 1.0) / 2.0,
    ])
    mesh.visual = trimesh.visual.TextureVisuals(uv=uv)
    colors = np.zeros((len(verts), 4), dtype=np.uint8)
    colors[:, :3] = ((verts + 1.0) * 127).astype(np.uint8)
    colors[:, 3] = 255
    mesh.visual.vertex_colors = colors
    return mesh
