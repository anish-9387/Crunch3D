from __future__ import annotations

import torch
import torch.nn as nn

from ..core.config import CONV_TYPE, DROPOUT, GNN_LAYERS, HIDDEN_DIM, LAP_PE_DIM, TWO_HOP_WEIGHT
from ..features.registry import edge_dim, vertex_dim
from .edge_decoder import EdgeDecoder
from .encoder import VertexEncoder


class Crunch3DModel(nn.Module):
    def __init__(
        self,
        vertex_in_dim: int | None = None,
        edge_feat_dim: int | None = None,
        hidden_dim: int = HIDDEN_DIM,
        layers: int = GNN_LAYERS,
        dropout: float = DROPOUT,
        conv_type: str = CONV_TYPE,
        two_hop_weight: float = TWO_HOP_WEIGHT,
        lap_pe_dim: int = LAP_PE_DIM,
    ):
        super().__init__()
        if vertex_in_dim is None:
            vertex_in_dim = vertex_dim() + lap_pe_dim
        if edge_feat_dim is None:
            edge_feat_dim = edge_dim()
        self.encoder = VertexEncoder(vertex_in_dim, hidden_dim, layers, dropout, conv_type, two_hop_weight)
        self.decoder = EdgeDecoder(hidden_dim, edge_feat_dim)
        self.hparams = dict(
            vertex_in_dim=vertex_in_dim,
            edge_feat_dim=edge_feat_dim,
            hidden_dim=hidden_dim,
            layers=layers,
            dropout=dropout,
            conv_type=conv_type,
            two_hop_weight=two_hop_weight,
            lap_pe_dim=lap_pe_dim,
        )

    def forward(self, x, edge_index, edge_label_index, edge_features=None, edge_index_2hop=None):
        h = self.encoder(x, edge_index, edge_index_2hop)
        return self.decoder(h, edge_label_index, edge_features)

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())


def build_model(**kwargs) -> Crunch3DModel:
    return Crunch3DModel(**kwargs)


@torch.no_grad()
def predict_edge_importance(mesh, model_path=None, tiers=("A", "B"), device="cpu"):
    from pathlib import Path

    from ..graph.builder import build_graph

    g = build_graph(mesh, tiers=tiers)
    if model_path is None:
        from pathlib import Path as P

        model_path = P(__file__).parent / "checkpoints" / "crunch3d_gnn.pt"
    model_path = Path(model_path)
    if not model_path.exists():
        return g.edges, __import__("numpy").full(len(g.edges), 0.5, dtype=float)

    import torch

    ckpt = torch.load(model_path, map_location=device, weights_only=False)
    state = ckpt.get("state_dict", ckpt) if isinstance(ckpt, dict) else ckpt
    hparams = ckpt.get("hparams", {}) if isinstance(ckpt, dict) else {}

    vertex_in = g.x.shape[1]
    edge_in = g.edge_features.shape[1] if g.edge_features.size else 0
    allowed = {"hidden_dim", "layers", "dropout", "conv_type", "two_hop_weight", "lap_pe_dim"}
    filtered = {k: v for k, v in hparams.items() if k in allowed}
    model = Crunch3DModel(vertex_in_dim=vertex_in, edge_feat_dim=edge_in, **filtered)
    try:
        model.load_state_dict(state, strict=False)
    except Exception:
        return g.edges, __import__("numpy").full(len(g.edges), 0.5, dtype=float)
    model.eval().to(device)

    x = torch.from_numpy(g.x).to(device)
    ei = torch.from_numpy(g.edge_index.T.copy()).long().to(device) if len(g.edge_index) else torch.zeros((2, 0), dtype=torch.long, device=device)
    ei2 = torch.from_numpy(g.edge_index_2hop.T.copy()).long().to(device) if g.edge_index_2hop is not None and len(g.edge_index_2hop) else None
    eli = torch.from_numpy(g.edges.T.copy()).long().to(device) if len(g.edges) else torch.zeros((2, 0), dtype=torch.long, device=device)
    ef = torch.from_numpy(g.edge_features).to(device) if g.edge_features.size else None

    with torch.no_grad():
        scores = model(x, ei, eli, ef, ei2).cpu().numpy()
    return g.edges, scores.astype(float)
