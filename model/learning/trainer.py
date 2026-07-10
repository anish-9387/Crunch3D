"""
learning/trainer.py — Training loop for the edge importance GNN.

Can be run standalone:
    python -m model.learning.trainer --data_dir ./training_meshes --epochs 100

Or imported and called programmatically.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CHECKPOINT_DIR = Path(__file__).parent / "checkpoints"


def train(
    data_dir: str | Path,
    epochs: int = 100,
    lr: float = 1e-3,
    checkpoint_dir: str | Path | None = None,
) -> dict:
    """Train the edge importance GNN.

    Parameters
    ----------
    data_dir : path
        Directory containing training mesh files.
    epochs : int
        Number of training epochs.
    lr : float
        Learning rate.
    checkpoint_dir : path, optional
        Where to save the trained model.

    Returns
    -------
    metrics : dict
        Training metrics (loss, epochs completed, etc.).
    """
    try:
        import torch
    except ImportError as e:
        raise ImportError(
            "Training requires 'torch'. Install with: pip install torch"
        ) from e

    from .gnn_model import build_edge_importance_model

    if checkpoint_dir is None:
        checkpoint_dir = DEFAULT_CHECKPOINT_DIR
    checkpoint_dir = Path(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    model = build_edge_importance_model()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = torch.nn.MSELoss()

    logger.info("Training GNN for %d epochs on data from %s", epochs, data_dir)

    # Placeholder training loop — to be filled once training data is available
    best_loss = float("inf")
    for epoch in range(epochs):
        # TODO: Load batches from data_dir using dataset.py
        # For now, this is a scaffold
        loss_val = 0.0  # placeholder

        if loss_val < best_loss:
            best_loss = loss_val
            save_path = checkpoint_dir / "edge_importance.pt"
            torch.save(model.state_dict(), save_path)

        if (epoch + 1) % 10 == 0:
            logger.info("Epoch %d/%d — loss: %.6f", epoch + 1, epochs, loss_val)

    return {
        "epochs_completed": epochs,
        "best_loss": best_loss,
        "checkpoint_path": str(checkpoint_dir / "edge_importance.pt"),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train edge importance GNN")
    parser.add_argument("--data_dir", type=str, required=True)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--lr", type=float, default=1e-3)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    result = train(args.data_dir, args.epochs, args.lr)
    print(result)
