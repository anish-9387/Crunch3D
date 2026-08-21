"""evaluation/laplacian.py — global structural change via the graph spectrum (§57).

The normalized graph Laplacian L = I − D^(−1/2) A D^(−1/2) has eigenvalues in
[0, 2]; its low-frequency end is a global shape descriptor that is invariant to
vertex ordering.  Comparing the k lowest non-trivial eigenvalues before and
after simplification answers "the mesh got smaller but did the overall
structure survive?".

The smallest eigenvalues of L are the largest of (2I − L), and Lanczos
converges far more reliably on the largest end, so that is what we solve.
"""

from __future__ import annotations

import numpy as np

SPECTRUM_SIZE = 30
_EPS = 1e-12


def _normalized_laplacian(faces: np.ndarray, n_verts: int):
    from scipy.sparse import coo_matrix, diags, eye

    src = faces.ravel()
    dst = faces[:, [1, 2, 0]].ravel()
    rows = np.concatenate([src, dst])
    cols = np.concatenate([dst, src])
    adjacency = coo_matrix(
        (np.ones(len(rows), dtype=np.float64), (rows, cols)), shape=(n_verts, n_verts)
    ).tocsr()
    adjacency.data[:] = 1.0
    adjacency.setdiag(0.0)
    adjacency.eliminate_zeros()

    degree = np.asarray(adjacency.sum(axis=1)).ravel()
    inv_sqrt = np.zeros_like(degree)
    nonzero = degree > _EPS
    inv_sqrt[nonzero] = 1.0 / np.sqrt(degree[nonzero])
    scaling = diags(inv_sqrt)
    return eye(n_verts, format="csr") - scaling @ adjacency @ scaling


def laplacian_spectrum(
    verts: np.ndarray, faces: np.ndarray, size: int = SPECTRUM_SIZE
) -> np.ndarray:
    """The ``size`` lowest non-trivial normalized-Laplacian eigenvalues."""
    from scipy.sparse import eye
    from scipy.sparse.linalg import eigsh

    faces = np.asarray(faces, dtype=np.int64)
    if len(faces) == 0:
        return np.zeros(0, dtype=np.float64)

    used = np.unique(faces)
    remap = np.full(int(used.max()) + 1, -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    faces = remap[faces]
    n = len(used)

    k = int(min(size + 1, n - 1))
    if k < 2:
        return np.zeros(0, dtype=np.float64)

    laplacian = _normalized_laplacian(faces, n)
    shifted = 2.0 * eye(n, format="csr") - laplacian
    try:
        values = eigsh(shifted, k=k, which="LM", return_eigenvectors=False, tol=1e-6)
    except Exception:
        return np.zeros(0, dtype=np.float64)

    spectrum = np.sort(2.0 - np.asarray(values, dtype=np.float64))
    return spectrum[1:]  # drop the trivial zero eigenvalue


def spectrum_error(
    original_verts: np.ndarray,
    original_faces: np.ndarray,
    simplified_verts: np.ndarray,
    simplified_faces: np.ndarray,
    size: int = SPECTRUM_SIZE,
) -> dict:
    before = laplacian_spectrum(original_verts, original_faces, size)
    after = laplacian_spectrum(simplified_verts, simplified_faces, size)
    if before.size == 0 or after.size == 0:
        return {"laplacian_error": None, "laplacian_relative_error": None}

    k = min(len(before), len(after))
    delta = np.abs(before[:k] - after[:k])
    reference = float(np.linalg.norm(before[:k]))
    return {
        "laplacian_error": round(float(delta.mean()), 8),
        "laplacian_relative_error": round(
            float(np.linalg.norm(delta) / reference) if reference > _EPS else 0.0, 8
        ),
        "laplacian_modes_compared": int(k),
    }
