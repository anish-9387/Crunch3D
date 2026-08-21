from __future__ import annotations

import numpy as np

from ..core.config import LAP_PE_DIM

_EPS = 1e-12


def _normalized_laplacian(edge_index: np.ndarray, n: int):
    from scipy.sparse import coo_matrix, diags, eye

    if n == 0 or len(edge_index) == 0:
        return eye(n, format="csr")
    src, dst = edge_index[:, 0], edge_index[:, 1]
    rows = np.concatenate([src, dst])
    cols = np.concatenate([dst, src])
    data = np.ones(len(rows), dtype=np.float64)
    adj = coo_matrix((data, (rows, cols)), shape=(n, n)).tocsr()
    adj.data[:] = 1.0
    adj.setdiag(0.0)
    adj.eliminate_zeros()
    deg = np.asarray(adj.sum(axis=1)).ravel()
    inv = np.zeros_like(deg)
    m = deg > _EPS
    inv[m] = 1.0 / np.sqrt(deg[m])
    d = diags(inv)
    return eye(n, format="csr") - d @ adj @ d


def laplacian_pe(
    verts: np.ndarray,
    faces: np.ndarray,
    edges: np.ndarray | None = None,
    dim: int = LAP_PE_DIM,
) -> np.ndarray:
    if len(verts) == 0:
        return np.zeros((0, dim), dtype=np.float32)
    n = len(verts)
    if dim <= 0:
        return np.zeros((n, 0), dtype=np.float32)
    if n <= dim + 1:
        return np.zeros((n, dim), dtype=np.float32)

    if edges is None:
        if len(faces) == 0:
            return np.zeros((n, dim), dtype=np.float32)
        src = faces.ravel()
        dst = faces[:, [1, 2, 0]].ravel()
        edge_index = np.column_stack([np.minimum(src, dst), np.maximum(src, dst)])
        edge_index = np.unique(edge_index, axis=0)
    else:
        edge_index = np.asarray(edges, dtype=np.int64)

    try:
        from scipy.sparse import eye
        from scipy.sparse.linalg import eigsh

        lap = _normalized_laplacian(edge_index, n)
        shifted = 2.0 * eye(n, format="csr") - lap
        k = min(dim + 1, n - 1)
        vals, vecs = eigsh(shifted, k=k, which="LM", tol=1e-6, maxiter=3000)
        spectrum = 2.0 - vals
        order = np.argsort(spectrum)
        vecs = vecs[:, order]
        spectrum = spectrum[order]
        mask = spectrum > 1e-8
        vecs = vecs[:, mask]
        if vecs.shape[1] == 0:
            return np.zeros((n, dim), dtype=np.float32)
        pe = vecs[:, :dim]
        if pe.shape[1] < dim:
            pad = np.zeros((n, dim - pe.shape[1]), dtype=np.float64)
            pe = np.concatenate([pe, pad], axis=1)
        norms = np.linalg.norm(pe, axis=0, keepdims=True)
        pe = pe / np.maximum(norms, _EPS)
        return pe.astype(np.float32)
    except Exception:
        return np.zeros((n, dim), dtype=np.float32)
