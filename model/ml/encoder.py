from __future__ import annotations

import torch
import torch.nn as nn


def _get_conv(conv_type: str, in_dim: int, out_dim: int):
    if conv_type == "gcn":
        from torch_geometric.nn import GCNConv

        return GCNConv(in_dim, out_dim, add_self_loops=True)
    if conv_type == "sage":
        from torch_geometric.nn import SAGEConv

        return SAGEConv(in_dim, out_dim)
    if conv_type == "gatv2":
        from torch_geometric.nn import GATv2Conv

        return GATv2Conv(in_dim, out_dim, heads=1, concat=False)
    if conv_type == "mlp":
        return None
    raise ValueError(conv_type)


class VertexEncoder(nn.Module):
    def __init__(
        self,
        in_dim: int,
        hidden_dim: int = 64,
        layers: int = 3,
        dropout: float = 0.15,
        conv_type: str = "gcn",
        two_hop_weight: float = 0.5,
    ):
        super().__init__()
        self.two_hop_weight = two_hop_weight
        self.layers = layers
        self.dropout = dropout
        self.conv_type = conv_type

        self.proj = nn.Linear(in_dim, hidden_dim)

        self.convs_1hop = nn.ModuleList()
        self.convs_2hop = nn.ModuleList()
        self.norms_1hop = nn.ModuleList()
        self.norms_2hop = nn.ModuleList()

        for i in range(layers):
            d_in = hidden_dim
            c1 = _get_conv(conv_type, d_in, hidden_dim)
            self.convs_1hop.append(c1)
            self.norms_1hop.append(nn.LayerNorm(hidden_dim))
            if two_hop_weight != 0:
                c2 = _get_conv(conv_type, d_in, hidden_dim)
                self.convs_2hop.append(c2)
                self.norms_2hop.append(nn.LayerNorm(hidden_dim))
            else:
                self.convs_2hop.append(None)
                self.norms_2hop.append(None)

    def _branch(self, x, edge_index, convs, norms):
        for conv, norm in zip(convs, norms):
            if conv is None:
                continue
            if self.conv_type == "mlp":
                x = torch.relu(norm(x))
                x = nn.functional.dropout(x, p=self.dropout, training=self.training)
                continue
            h = conv(x, edge_index)
            h = norm(h)
            h = torch.relu(h)
            h = nn.functional.dropout(h, p=self.dropout, training=self.training)
            x = h
        return x

    def forward(self, x, edge_index, edge_index_2hop=None):
        x = self.proj(x)
        x = torch.relu(x)

        h1 = self._branch(x, edge_index, self.convs_1hop, self.norms_1hop)

        if self.two_hop_weight != 0 and edge_index_2hop is not None and edge_index_2hop.numel() > 0:
            h2 = self._branch(x, edge_index_2hop, self.convs_2hop, self.norms_2hop)
            return h1 + self.two_hop_weight * h2
        return h1
