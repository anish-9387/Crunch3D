"""
learning/trainer.py — Training loop for the edge importance GNN.

Features:
  - Loads .pt graph datasets from a data directory
  - 80/20 train/validation split
  - Early stopping (patience=15)
  - Learning rate scheduling (ReduceLROnPlateau)
  - Logs training AND validation loss
  - Saves best model checkpoint

Usage:
    python -m model.learning.trainer --data_dir model/learning/training_data --epochs 200
"""

from __future__ import annotations

import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CHECKPOINT_DIR = Path(__file__).parent / "checkpoints"


def train(
    data_dir: str | Path,
    epochs: int = 200,
    lr: float = 1e-3,
    checkpoint_dir: str | Path | None = None,
    val_split: float = 0.2,
    patience: int = 15,
) -> dict:
    """Train the edge importance GNN with proper evaluation.

    Parameters
    ----------
    data_dir : path
        Directory containing .pt graph datasets.
    epochs : int
        Maximum number of training epochs.
    lr : float
        Initial learning rate.
    checkpoint_dir : path, optional
        Where to save the trained model.
    val_split : float
        Fraction of data used for validation (default 0.2).
    patience : int
        Early stopping patience (default 15 epochs).

    Returns
    -------
    metrics : dict
        Training metrics.
    """
    try:
        import torch
    except ImportError as e:
        raise ImportError(
            "Training requires 'torch'. Install with: pip install torch"
        ) from e

    try:
        from torch_geometric.loader import DataLoader
    except ImportError as e:
        raise ImportError(
            "Training requires 'torch_geometric'. Install with: pip install torch-geometric"
        ) from e

    from .gnn_model import build_edge_importance_model

    if checkpoint_dir is None:
        checkpoint_dir = DEFAULT_CHECKPOINT_DIR
    checkpoint_dir = Path(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    # ── Load datasets ─────────────────────────────────────────────────────
    data_dir = Path(data_dir)
    dataset = []
    if data_dir.exists() and data_dir.is_dir():
        for p in sorted(data_dir.iterdir()):
            if p.is_file() and p.suffix == ".pt":
                try:
                    dataset.append(torch.load(p, weights_only=False))
                except Exception as e:
                    logger.warning("Failed to load %s: %s", p.name, e)

    save_path = checkpoint_dir / "crunch3d_gnn_model.pt"

    if not dataset:
        logger.warning("No training data found in %s. Generating a dummy checkpoint.", data_dir)
        model = build_edge_importance_model()
        torch.save(model.state_dict(), save_path)
        return {
            "epochs_completed": 0,
            "best_train_loss": 0.0,
            "best_val_loss": 0.0,
            "checkpoint_path": str(save_path),
            "dataset_size": 0,
        }

    # ── Train/val split ───────────────────────────────────────────────────
    random.seed(42)
    indices = list(range(len(dataset)))
    random.shuffle(indices)

    val_count = max(1, int(len(dataset) * val_split))
    train_count = len(dataset) - val_count

    train_data = [dataset[i] for i in indices[:train_count]]
    val_data = [dataset[i] for i in indices[train_count:]]

    logger.info("Dataset: %d total → %d train, %d val", len(dataset), len(train_data), len(val_data))

    train_loader = DataLoader(train_data, batch_size=1, shuffle=True)
    val_loader = DataLoader(val_data, batch_size=1, shuffle=False)

    # ── Model, optimizer, scheduler ───────────────────────────────────────
    model = build_edge_importance_model()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5,
    )
    criterion = torch.nn.MSELoss()

    # ── Training loop with early stopping ─────────────────────────────────
    best_val_loss = float("inf")
    best_train_loss = float("inf")
    epochs_without_improvement = 0

    logger.info("Training GNN for up to %d epochs (patience=%d)...", epochs, patience)

    for epoch in range(epochs):
        # ── Train ──
        model.train()
        train_loss = 0.0
        for batch in train_loader:
            optimizer.zero_grad()
            out = model(batch.x, batch.edge_index)
            loss = criterion(out, batch.y)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
        avg_train_loss = train_loss / len(train_loader)

        # ── Validate ──
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for batch in val_loader:
                out = model(batch.x, batch.edge_index)
                loss = criterion(out, batch.y)
                val_loss += loss.item()
        avg_val_loss = val_loss / len(val_loader)

        scheduler.step(avg_val_loss)

        # ── Checkpointing ──
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_train_loss = avg_train_loss
            torch.save(model.state_dict(), save_path)
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        if (epoch + 1) % 10 == 0 or epoch == 0:
            current_lr = optimizer.param_groups[0]["lr"]
            logger.info(
                "Epoch %3d/%d — train_loss: %.6f | val_loss: %.6f | lr: %.2e | patience: %d/%d",
                epoch + 1, epochs, avg_train_loss, avg_val_loss, current_lr,
                epochs_without_improvement, patience,
            )

        if epochs_without_improvement >= patience:
            logger.info("Early stopping at epoch %d (no improvement for %d epochs)", epoch + 1, patience)
            break

    logger.info(
        "Training complete. Best val_loss: %.6f | Checkpoint: %s",
        best_val_loss, save_path,
    )

    return {
        "epochs_completed": epoch + 1,
        "best_train_loss": round(best_train_loss, 6),
        "best_val_loss": round(best_val_loss, 6),
        "checkpoint_path": str(save_path),
        "dataset_size": len(dataset),
        "train_size": len(train_data),
        "val_size": len(val_data),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train edge importance GNN")
    parser.add_argument("--data_dir", type=str, required=True)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--patience", type=int, default=15)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    result = train(args.data_dir, args.epochs, args.lr, patience=args.patience)
    print(result)
