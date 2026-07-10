"""
learning/gnn_model.py — GNN architecture for edge importance prediction.

Implements the Edge Importance Predictor (§IV-B) using a message-passing
GNN over the mesh dual graph.

Architecture:
    Input:  per-edge features (QEM cost, dihedral angle, curvature, etc.)
    Layers: 3× GAT convolution + batch norm + ReLU
    Output: ŷ_σ ∈ [0, 1] per edge (importance score)

Requires: torch, torch-geometric (import-guarded).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)


def _require_torch():
    """Import torch and torch_geometric or raise helpful errors."""
    try:
        import torch
    except ImportError as e:
        raise ImportError(
            "The learning module requires 'torch'. "
            "Install it with: pip install torch"
        ) from e

    try:
        import torch_geometric
    except ImportError as e:
        raise ImportError(
            "The learning module requires 'torch-geometric'. "
            "See: https://pytorch-geometric.readthedocs.io/en/latest/install/installation.html"
        ) from e

    return torch, torch_geometric


def build_edge_importance_model(
    in_features: int = 6,
    hidden_dim: int = 64,
    num_layers: int = 3,
    heads: int = 4,
):
    """Build the GNN model for edge importance prediction.

    Parameters
    ----------
    in_features : int
        Number of input features per edge.
        Default 6: [qem_cost, dihedral_angle, mean_curvature,
                     gaussian_curvature, uv_stretch, boundary_flag]
    hidden_dim : int
        Hidden dimension for GAT layers.
    num_layers : int
        Number of GAT layers.
    heads : int
        Number of attention heads per GAT layer.

    Returns
    -------
    model : torch.nn.Module
        The GNN model.
    """
    torch, torch_geometric = _require_torch()
    from torch import nn
    from torch_geometric.nn import GATConv, BatchNorm

    class EdgeImportanceGNN(nn.Module):
        """Graph Attention Network for edge importance prediction."""

        def __init__(self):
            super().__init__()
            self.convs = nn.ModuleList()
            self.norms = nn.ModuleList()

            # First layer
            self.convs.append(GATConv(in_features, hidden_dim, heads=heads, concat=False))
            self.norms.append(BatchNorm(hidden_dim))

            # Hidden layers
            for _ in range(num_layers - 1):
                self.convs.append(GATConv(hidden_dim, hidden_dim, heads=heads, concat=False))
                self.norms.append(BatchNorm(hidden_dim))

            # Edge prediction head
            self.edge_head = nn.Sequential(
                nn.Linear(hidden_dim * 2, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, 1),
                nn.Sigmoid(),
            )

        def forward(self, x, edge_index):
            """Forward pass.

            Parameters
            ----------
            x : (N, in_features) tensor
                Node features.
            edge_index : (2, E) long tensor
                Edge connectivity.

            Returns
            -------
            y : (E,) tensor
                Predicted importance per edge ∈ [0, 1].
            """
            for conv, norm in zip(self.convs, self.norms):
                x = conv(x, edge_index)
                x = norm(x)
                x = torch.nn.functional.relu(x)

            # Edge features via concatenation of endpoint node features
            src, dst = edge_index[0], edge_index[1]
            edge_feat = torch.cat([x[src], x[dst]], dim=-1)
            y = self.edge_head(edge_feat).squeeze(-1)
            return y

    model = EdgeImportanceGNN()
    logger.info(
        "Built EdgeImportanceGNN: %d params",
        sum(p.numel() for p in model.parameters()),
    )
    return model
