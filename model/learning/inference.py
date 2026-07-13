"""
learning/inference.py — GNN inference for edge importance prediction.

Loads a pre-trained model and predicts ŷ_σ for each edge.
Used at decimation time when ENABLE_GNN_IMPORTANCE is True.

Uses geometry-aware features from features.py (same as training).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import trimesh

from .features import compute_vertex_features

logger = logging.getLogger(__name__)

# Default model checkpoint path
DEFAULT_MODEL_PATH = Path(__file__).parent / "checkpoints" / "crunch3d_gnn_model.pt"


def predict_edge_importance(
    mesh: "trimesh.Trimesh",
    model_path: str | Path | None = None,
) -> np.ndarray:
    """Predict per-edge importance using the trained GNN.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Input mesh.
    model_path : path, optional
        Path to the saved model checkpoint.
        Defaults to ``learning/checkpoints/crunch3d_gnn_model.pt``.

    Returns
    -------
    importance : (E,) float array
        Predicted importance ŷ_σ ∈ [0, 1] per unique edge.

    Raises
    ------
    ImportError
        If torch/torch-geometric are not installed.
    """
    try:
        import torch
    except ImportError as e:
        raise ImportError(
            "GNN inference requires 'torch'. Install with: pip install torch"
        ) from e

    if model_path is None:
        model_path = DEFAULT_MODEL_PATH
    model_path = Path(model_path)

    if not model_path.exists():
        logger.warning(
            "No trained model found at %s. "
            "Returning uniform importance (0.5). "
            "Train a model first with: python -m model.learning.trainer --data_dir model/learning/training_data",
            model_path,
        )
        return np.full(len(mesh.edges_unique), 0.5, dtype=np.float64)

    # Load model and run inference
    from .gnn_model import build_edge_importance_model

    model = build_edge_importance_model()
    state = torch.load(model_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()

    # Geometry-aware node features (same as training)
    x = torch.tensor(compute_vertex_features(mesh), dtype=torch.float32)

    # Build undirected edges and their reverse to get bidirectional graph
    edges_unique = mesh.edges_unique
    edges_bidirectional = np.vstack([edges_unique, edges_unique[:, [1, 0]]])
    edge_index = torch.tensor(edges_bidirectional, dtype=torch.long).t().contiguous()

    with torch.no_grad():
        y = model(x, edge_index)

    # Average bidirectional edges: first half is forward, second half is reverse
    half = len(edges_unique)
    result = ((y[:half] + y[half:]) / 2.0).numpy().flatten().astype(np.float64)

    logger.info(
        "GNN predicted edge importance: min=%.4f, max=%.4f, mean=%.4f",
        result.min(), result.max(), result.mean(),
    )

    return result
