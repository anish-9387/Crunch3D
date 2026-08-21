from __future__ import annotations

import dataclasses

import numpy as np

from ..core.config import LAP_PE_DIM, TWO_HOP_MAX_DEGREE, TWO_HOP_WEIGHT
from ..features.registry import DEFAULT_TIERS, extract
from .positional_encoding import laplacian_pe


@dataclasses.dataclass
class GraphData:
    x: np.ndarray
    edge_index: np.ndarray
    edge_index_2hop: np.ndarray | None
    edge_features: np.ndarray
    edges: np.ndarray
    pe: np.ndarray
    num_nodes: int
    metadata: dict

    def to_pyg(self):
        try:
            import torch
            from torch_geometric.data import Data
        except ImportError as e:
            raise ImportError("torch_geometric required") from e
        data = Data(
            x=torch.from_numpy(self.x),
            edge_index=torch.from_numpy(self.edge_index.T.copy()).long() if len(self.edge_index) else torch.zeros((2, 0), dtype=torch.long),
            num_nodes=self.num_nodes,
        )
        if self.edge_index_2hop is not None and len(self.edge_index_2hop):
            data.edge_index_2hop = torch.from_numpy(self.edge_index_2hop.T.copy()).long()
        if len(self.edge_features):
            data.edge_attr = torch.from_numpy(self.edge_features)
        if len(self.pe):
            data.pe = torch.from_numpy(self.pe)
        data.edge_label_index = torch.from_numpy(self.edges.T.copy()).long() if len(self.edges) else torch.zeros((2, 0), dtype=torch.long)
        return data


def _build_edge_index(faces: np.ndarray, n: int) -> np.ndarray:
    if len(faces) == 0:
        return np.zeros((0, 2), dtype=np.int64)
    src = faces.ravel()
    dst = faces[:, [1, 2, 0]].ravel()
    edges = np.column_stack([np.minimum(src, dst), np.maximum(src, dst)])
    return np.unique(edges, axis=0)


def _two_hop_edges(edge_index: np.ndarray, n: int, max_degree: int = TWO_HOP_MAX_DEGREE) -> np.ndarray:
    if len(edge_index) == 0 or n == 0:
        return np.zeros((0, 2), dtype=np.int64)
    from scipy.sparse import coo_matrix

    rows = np.concatenate([edge_index[:, 0], edge_index[:, 1]])
    cols = np.concatenate([edge_index[:, 1], edge_index[:, 0]])
    adj = coo_matrix((np.ones(len(rows), dtype=np.int8), (rows, cols)), shape=(n, n)).tocsr()
    adj.setdiag(0)
    adj.eliminate_zeros()
    two = adj @ adj
    two.setdiag(0)
    two.eliminate_zeros()
    two.data[:] = 1
    two = two.tocsr()
    two = two - adj
    two.data[two.data < 0] = 0
    two.eliminate_zeros()
    two.setdiag(0)
    two.eliminate_zeros()
    coo = two.tocoo()
    if coo.nnz == 0:
        return np.zeros((0, 2), dtype=np.int64)
    pairs = np.column_stack([coo.row, coo.col])
    pairs = pairs[pairs[:, 0] < pairs[:, 1]]
    if len(pairs) == 0:
        return pairs
    if max_degree > 0 and len(pairs) > n * max_degree:
        rng = np.random.default_rng(42)
        keep = []
        order = np.argsort(pairs[:, 0], kind="stable")
        pairs = pairs[order]
        uniq, counts = np.unique(pairs[:, 0], return_counts=True)
        offset = 0
        for v, cnt in zip(uniq, counts):
            sl = pairs[offset:offset + cnt]
            offset += cnt
            if len(sl) > max_degree:
                sl = sl[rng.choice(len(sl), max_degree, replace=False)]
            keep.append(sl)
        pairs = np.vstack(keep) if keep else pairs
    return pairs.astype(np.int64)


def build_graph(
    mesh,
    tiers: tuple[str, ...] = DEFAULT_TIERS,
    exclude: tuple[str, ...] = (),
    lap_pe_dim: int = LAP_PE_DIM,
    two_hop: bool = True,
    two_hop_weight: float = TWO_HOP_WEIGHT,
    two_hop_max_degree: int = TWO_HOP_MAX_DEGREE,
) -> GraphData:
    feats = extract(mesh, tiers=tiers, exclude=exclude, normalize=True)
    x_base = feats.vertex
    if lap_pe_dim > 0:
        pe = laplacian_pe(
            np.asarray(mesh.vertices),
            np.asarray(mesh.faces),
            feats.edges,
            dim=lap_pe_dim,
        )
        x = np.concatenate([x_base, pe], axis=1) if len(pe) and pe.shape[1] else x_base
    else:
        pe = np.zeros((len(x_base), 0), dtype=np.float32)
        x = x_base

    n = feats.vertex.shape[0]
    edge_index = _build_edge_index(np.asarray(mesh.faces, dtype=np.int64), n)
    edge_2hop = _two_hop_edges(edge_index, n, max_degree=two_hop_max_degree) if two_hop else None

    return GraphData(
        x=x.astype(np.float32),
        edge_index=edge_index,
        edge_index_2hop=edge_2hop,
        edge_features=feats.edge.astype(np.float32),
        edges=feats.edges.astype(np.int64),
        pe=pe.astype(np.float32),
        num_nodes=n,
        metadata={
            "vertex_names": feats.vertex_names,
            "edge_names": feats.edge_names,
            "tiers": list(tiers),
            "lap_pe_dim": int(lap_pe_dim),
            "two_hop_weight": float(two_hop_weight),
            "diagonal": feats.metadata.get("diagonal", 1.0),
        },
    )


def mesh_to_pyg_data(mesh, tiers=DEFAULT_TIERS, **kwargs):
    return build_graph(mesh, tiers=tiers, **kwargs).to_pyg()
