from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import trimesh

from ..graph.builder import build_graph
from ..labels.oracle import compute_oracle_labels

try:
    import torch

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


def _hash_mesh(verts: np.ndarray, faces: np.ndarray) -> str:
    h = hashlib.sha1()
    h.update(verts.tobytes())
    h.update(faces.tobytes())
    return h.hexdigest()[:12]


def cache_one(mesh: trimesh.Trimesh, out_path: Path, tiers=("A", "B"), k=None, overwrite=False) -> Path | None:
    if out_path.exists() and not overwrite:
        return out_path
    g = build_graph(mesh, tiers=tiers)
    edges, labels, safety = compute_oracle_labels(mesh, k=k)
    edge_map = {tuple(e): i for i, e in enumerate(g.edges)}
    aligned = np.full(len(g.edges), 0.5, dtype=np.float32)
    aligned_safety = np.zeros(len(g.edges), dtype=bool)
    for e, lab, s in zip(edges, labels, safety):
        j = edge_map.get((int(e[0]), int(e[1])), -1)
        if j >= 0:
            aligned[j] = float(lab)
            aligned_safety[j] = bool(s)
    verts = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    data = {
        "x": g.x,
        "edge_index": g.edge_index,
        "edge_index_2hop": g.edge_index_2hop,
        "edges": g.edges,
        "edge_features": g.edge_features,
        "labels": aligned,
        "safety_mask": aligned_safety,
        "pe": g.pe,
        "pos": verts,
        "faces": faces,
        "face_count": int(len(faces)),
        "hash": _hash_mesh(verts, faces),
        "metadata": g.metadata,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if HAS_TORCH:
        torch.save(data, out_path)
    else:
        np.savez_compressed(out_path.with_suffix(".npz"), **{k: v for k, v in data.items() if isinstance(v, np.ndarray)})
    return out_path
