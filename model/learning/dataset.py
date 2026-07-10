"""
learning/dataset.py — Training data loader for edge importance GNN.

Converts mesh files with ground-truth quality metrics into
PyTorch Geometric Data objects for supervised training.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def mesh_to_graph_data(
    mesh_path: str | Path,
    ground_truth_importance: np.ndarray | None = None,
):
    """Convert a mesh file into a PyG Data object.

    Parameters
    ----------
    mesh_path : path
        Path to the mesh file.
    ground_truth_importance : (E,) array, optional
        Ground-truth edge importance for supervised training.

    Returns
    -------
    data : torch_geometric.data.Data
        Graph data with node features, edge index, and optional labels.
    """
    try:
        import torch
        from torch_geometric.data import Data
        import trimesh
    except ImportError as e:
        raise ImportError(
            "The dataset module requires 'torch', 'torch-geometric', and 'trimesh'. "
        ) from e

    mesh = trimesh.load(str(mesh_path), process=False)
    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(f"Expected a single Trimesh, got {type(mesh)}")

    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    normals = np.asarray(mesh.vertex_normals, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.int64)

    # Node features: position + normals
    x = torch.tensor(np.hstack([vertices, normals]), dtype=torch.float32)

    # Edge index (bidirectional)
    edges_unique = mesh.edges_unique
    edges_bidirectional = np.vstack([edges_unique, edges_unique[:, [1, 0]]])
    edge_index = torch.tensor(edges_bidirectional, dtype=torch.long).t().contiguous()

    data = Data(x=x, edge_index=edge_index)

    if ground_truth_importance is not None:
        data.y = torch.tensor(ground_truth_importance, dtype=torch.float32)

    return data
