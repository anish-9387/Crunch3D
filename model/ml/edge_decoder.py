from __future__ import annotations

import torch
import torch.nn as nn


class EdgeDecoder(nn.Module):
    def __init__(self, hidden_dim: int = 64, edge_feat_dim: int = 0):
        super().__init__()
        in_dim = hidden_dim * 3 + edge_feat_dim
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, h, edge_label_index, edge_features=None):
        u, v = edge_label_index[0], edge_label_index[1]
        hu, hv = h[u], h[v]
        diff = (hu - hv).abs()
        parts = [hu, hv, diff]
        if edge_features is not None and edge_features.numel() > 0:
            if edge_features.shape[0] == edge_label_index.shape[1]:
                parts.append(edge_features)
            else:
                parts.append(torch.zeros(edge_label_index.shape[1], self.net[0].in_features - hu.shape[1] * 3, device=h.device, dtype=h.dtype))
        x = torch.cat(parts, dim=-1)
        return torch.sigmoid(self.net(x)).squeeze(-1)
