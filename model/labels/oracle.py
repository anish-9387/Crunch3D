from __future__ import annotations

import numpy as np

from ..core.config import ORACLE_CANDIDATES, ORACLE_WEIGHTS

_EPS = 1e-12


def _diagonal(verts: np.ndarray) -> float:
    if len(verts) == 0:
        return 1.0
    d = float(np.linalg.norm(verts.max(axis=0) - verts.min(axis=0)))
    return d if d > _EPS else 1.0


def _sample_edges(n_edges: int, k: int, seed: int = 42) -> np.ndarray:
    if n_edges <= k:
        return np.arange(n_edges)
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(n_edges, k, replace=False))


def compute_oracle_labels(mesh, k: int | None = None, seed: int = 42):
    verts = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if len(faces) == 0 or len(verts) == 0:
        return np.zeros((0, 2), dtype=np.int64), np.zeros(0, dtype=np.float32), np.zeros(0, dtype=bool)

    from ..geometry.halfedge import HalfEdgeMesh
    from ..geometry.quadric import QuadricSet
    from ..importance.edge_features import compute_edge_feature_importance
    from ..features.registry import safety_mask as compute_safety_mask
    from ..features.base import MeshContext

    he = HalfEdgeMesh(verts, faces)
    quadrics = QuadricSet.from_mesh(he, boundary_weight=0.0)
    raw_edges = he.unique_edges()
    n = len(raw_edges)
    if n == 0:
        return raw_edges, np.zeros(0, dtype=np.float32), np.zeros(0, dtype=bool)

    if k is None:
        if n < 5000:
            k = ORACLE_CANDIDATES[0]
        elif n < 20000:
            k = ORACLE_CANDIDATES[1]
        else:
            k = ORACLE_CANDIDATES[2]
    sel = _sample_edges(n, k, seed)
    edges = raw_edges[sel]

    diag = _diagonal(verts)
    qem_costs, qem_pos = quadrics.edge_costs(edges)
    qem_costs = np.asarray(qem_costs, dtype=np.float64)
    qem_norm = np.percentile(np.abs(qem_costs), 95) if len(qem_costs) else 1.0
    qem_norm = max(qem_norm, _EPS)
    qem_term = np.clip(qem_costs / qem_norm, 0, 1)

    try:
        desc = compute_edge_feature_importance(mesh)
        present = desc.present
        feats = desc.features
        edge_map = {tuple(e): i for i, e in enumerate(desc.edges)}
        idx = np.array([edge_map.get((min(int(u), int(v)), max(int(u), int(v))), -1) for u, v in edges], dtype=np.int64)
        valid = idx >= 0

        def _pick(name: str):
            arr = feats.get(name)
            if arr is None or not valid.any():
                return np.zeros(len(edges), dtype=np.float64)
            out = np.zeros(len(edges), dtype=np.float64)
            out[valid] = arr[idx[valid]]
            return out

        dihedral = _pick("dihedral_angle")
        normal_diff = _pick("surface_normal_difference")
        uv_seam = _pick("uv_seam")
        material = _pick("material_boundary")
        bone = _pick("bone_weight_difference")
        sharp = _pick("sharp_edge_flag")
        boundary = _pick("boundary_edge_flag")
    except Exception:
        dihedral = np.zeros(len(edges), dtype=np.float64)
        normal_diff = np.zeros(len(edges), dtype=np.float64)
        uv_seam = np.zeros(len(edges), dtype=np.float64)
        material = np.zeros(len(edges), dtype=np.float64)
        bone = np.zeros(len(edges), dtype=np.float64)
        sharp = np.zeros(len(edges), dtype=np.float64)
        boundary = np.zeros(len(edges), dtype=np.float64)

    try:
        from ..importance.edge_features import _vertex_mean_curvature, _vertex_gaussian_curvature

        mc = _vertex_mean_curvature(mesh)
        gc = _vertex_gaussian_curvature(verts, faces)
        curv_jump = np.abs(mc[edges[:, 0]] - mc[edges[:, 1]])
        gauss_jump = np.abs(gc[edges[:, 0]] - gc[edges[:, 1]])
        curv_term = np.clip(curv_jump / max(np.percentile(curv_jump, 95) + _EPS, _EPS), 0, 1)
        gauss_term = np.clip(gauss_jump / max(np.percentile(gauss_jump, 95) + _EPS, _EPS), 0, 1)
        curvature_term = 0.6 * curv_term + 0.4 * gauss_term
    except Exception:
        curvature_term = np.zeros(len(edges), dtype=np.float64)

    normal_term = np.clip((dihedral + normal_diff) * 0.5, 0, 1)

    link_ok = np.ones(len(edges), dtype=np.float64)
    for i, (u, v) in enumerate(edges):
        u, v = int(u), int(v)
        ru = he.one_ring(u)
        rv = he.one_ring(v)
        shared = ru & rv
        link_faces = he.edge_faces(u, v)
        opposite = {int(w) for f in link_faces for w in he.faces[f] if int(w) not in (u, v)}
        if shared != opposite:
            link_ok[i] = 0.0
        if boundary[i] > 0.5 and len(link_faces) < 2:
            link_ok[i] *= 0.5
    topology_term = 1.0 - link_ok

    w = ORACLE_WEIGHTS
    oracle_cost = (
        w["qem"] * qem_term
        + w["normal"] * normal_term
        + w["curvature"] * curvature_term
        + w["topology"] * topology_term
        + w["uv"] * np.clip(uv_seam, 0, 1)
        + w["material"] * np.clip(material, 0, 1)
        + w["skin"] * np.clip(bone, 0, 1)
    )
    oracle_cost = np.clip(oracle_cost, 0, 1)
    importance = 1.0 - oracle_cost
    importance = np.clip(importance, 0, 1).astype(np.float32)

    try:
        ctx = MeshContext(mesh, normalize=False)
        from ..features.registry import extract

        fs = extract(mesh, tiers=("A", "B"))
        from ..features.registry import safety_mask

        mask_full = safety_mask(fs)
        sel_mask = np.zeros(len(edges), dtype=bool)
        full_map = {tuple(e): i for i, e in enumerate(fs.edges)}
        for i, (u, v) in enumerate(edges):
            j = full_map.get((min(int(u), int(v)), max(int(u), int(v))), -1)
            if j >= 0:
                sel_mask[i] = bool(mask_full[j])
    except Exception:
        sel_mask = (boundary > 0.5) | (uv_seam > 0.5) | (material > 0.5) | (sharp > 0.5)

    return edges.astype(np.int64), importance, sel_mask


def oracle_for_mesh(mesh, **kwargs):
    edges, labels, safety = compute_oracle_labels(mesh, **kwargs)
    return {"edges": edges, "labels": labels, "safety_mask": safety}
