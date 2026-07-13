"""
learning/dataset.py — Training data loader for edge importance GNN.

Converts mesh files with ground-truth importance labels into
PyTorch Geometric Data objects for supervised training.

Uses geometry-aware features from features.py instead of raw coordinates.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from .features import compute_vertex_features, NUM_FEATURES

logger = logging.getLogger(__name__)


def mesh_to_graph_data(
    mesh_or_path,
    ground_truth_importance: np.ndarray | None = None,
):
    """Convert a mesh (or mesh file path) into a PyG Data object.

    Parameters
    ----------
    mesh_or_path : trimesh.Trimesh or str or Path
        Either a loaded Trimesh object or a path to a mesh file.
    ground_truth_importance : (E_unique,) array, optional
        Ground-truth edge importance for supervised training.
        Length must match edges_unique count.

    Returns
    -------
    data : torch_geometric.data.Data
        Graph data with geometry-aware node features, edge index,
        and optional edge labels.
    """
    try:
        import torch
        from torch_geometric.data import Data
        import trimesh
    except ImportError as e:
        raise ImportError(
            "The dataset module requires 'torch', 'torch-geometric', and 'trimesh'. "
        ) from e

    # Accept either a loaded mesh or a file path
    if isinstance(mesh_or_path, (str, Path)):
        mesh = trimesh.load(str(mesh_or_path), process=False)
        if not isinstance(mesh, trimesh.Trimesh):
            raise ValueError(f"Expected a single Trimesh, got {type(mesh)}")
    else:
        mesh = mesh_or_path

    # Geometry-aware node features (V, 6)
    x = torch.tensor(compute_vertex_features(mesh), dtype=torch.float32)

    # Edge index (bidirectional)
    edges_unique = mesh.edges_unique
    edges_bidirectional = np.vstack([edges_unique, edges_unique[:, [1, 0]]])
    edge_index = torch.tensor(edges_bidirectional, dtype=torch.long).t().contiguous()

    data = Data(x=x, edge_index=edge_index)

    if ground_truth_importance is not None:
        # Duplicate importance for the reverse edges so shape matches edge_index
        gt_bidirectional = np.concatenate([ground_truth_importance, ground_truth_importance])
        data.y = torch.tensor(gt_bidirectional, dtype=torch.float32)

    return data
