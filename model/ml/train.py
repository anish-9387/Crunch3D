from __future__ import annotations

import argparse
import json
import logging
import random
from pathlib import Path

import numpy as np
import torch

from ..core.config import LOSS_RANKING, LOSS_REGRESSION, LOSS_SAFETY, SEED
from .losses import total_loss
from .model import Crunch3DModel

logger = logging.getLogger(__name__)


def _set_seed(seed: int = SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def train(
    data_dir: str | Path,
    epochs: int = 50,
    lr: float = 1e-3,
    batch_size: int = 1,
    checkpoint_dir: str | Path | None = None,
    val_split: float = 0.15,
    device: str | None = None,
    warm_start: bool = True,
):
    _set_seed()
    data_dir = Path(data_dir)
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    if checkpoint_dir is None:
        checkpoint_dir = Path(__file__).parent / "checkpoints"
    checkpoint_dir = Path(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(data_dir.glob("*.pt"))
    if not files:
        logger.warning("No data in %s", data_dir)
        return {"ok": False, "error": "no data"}

    objs = []
    for p in files:
        try:
            objs.append(torch.load(p, map_location="cpu", weights_only=False))
        except Exception as e:
            logger.warning("Skip %s: %s", p.name, e)

    if not objs:
        return {"ok": False, "error": "no loadable data"}

    is_dict = isinstance(objs[0], dict) and "x" in objs[0]

    random.seed(SEED)
    idx = list(range(len(objs)))
    random.shuffle(idx)
    n_val = max(1, int(len(objs) * val_split))
    n_train = len(objs) - n_val
    train_idx, val_idx = idx[:n_train], idx[n_train:]
    train_objs = [objs[i] for i in train_idx]
    val_objs = [objs[i] for i in val_idx]

    sample = train_objs[0]
    if is_dict:
        v_dim = sample["x"].shape[1] if hasattr(sample["x"], "shape") else sample["x"].shape[-1]
        e_dim = sample["edge_features"].shape[1] if "edge_features" in sample and sample["edge_features"] is not None else 0
    else:
        v_dim = sample.x.shape[1]
        e_dim = sample.edge_attr.shape[1] if hasattr(sample, "edge_attr") and sample.edge_attr is not None else 0

    model = Crunch3DModel(vertex_in_dim=v_dim, edge_feat_dim=e_dim).to(device)
    ckpt_path = checkpoint_dir / "crunch3d_gnn.pt"
    meta_path = checkpoint_dir / "crunch3d_gnn_meta.json"
    if warm_start and ckpt_path.exists():
        try:
            ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
            sd = ckpt.get("state_dict", ckpt)
            model.load_state_dict(sd, strict=False)
            logger.info("Warm start from %s", ckpt_path)
        except Exception as e:
            logger.warning("Warm start failed: %s", e)

    opt = torch.optim.Adam(model.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode="min", factor=0.5, patience=5)

    best_val = float("inf")
    patience = 10
    no_imp = 0

    def _to_device(obj):
        if is_dict:
            x = torch.as_tensor(obj["x"], dtype=torch.float32, device=device)
            ei = torch.as_tensor(obj["edge_index"], dtype=torch.long, device=device) if "edge_index" in obj else torch.zeros((2, 0), dtype=torch.long, device=device)
            if ei.dim() == 2 and ei.shape[0] != 2 and ei.shape[1] == 2:
                ei = ei.t().contiguous()
            ei2 = None
            if "edge_index_2hop" in obj and obj["edge_index_2hop"] is not None and len(obj["edge_index_2hop"]):
                ei2 = torch.as_tensor(obj["edge_index_2hop"], dtype=torch.long, device=device)
                if ei2.dim() == 2 and ei2.shape[0] != 2:
                    ei2 = ei2.t().contiguous()
            eli = torch.as_tensor(obj["edges"], dtype=torch.long, device=device) if "edges" in obj else torch.zeros((2, 0), dtype=torch.long, device=device)
            if eli.dim() == 2 and eli.shape[0] != 2 and eli.shape[1] == 2:
                eli = eli.t().contiguous()
            ef = torch.as_tensor(obj["edge_features"], dtype=torch.float32, device=device) if "edge_features" in obj and obj["edge_features"] is not None else None
            y = torch.as_tensor(obj["labels"], dtype=torch.float32, device=device) if "labels" in obj else None
            mask = torch.as_tensor(obj["safety_mask"], dtype=torch.bool, device=device) if "safety_mask" in obj and obj["safety_mask"] is not None else None
            return x, ei, eli, ef, ei2, y, mask
        else:
            x = obj.x.to(device).float()
            ei = obj.edge_index.to(device)
            ei2 = getattr(obj, "edge_index_2hop", None)
            if ei2 is not None:
                ei2 = ei2.to(device)
            eli = obj.edge_label_index.to(device) if hasattr(obj, "edge_label_index") else obj.edge_index.to(device)
            ef = getattr(obj, "edge_attr", None)
            if ef is not None:
                ef = ef.to(device).float()
            y = getattr(obj, "y", None)
            if y is not None:
                y = y.to(device).float()
                if y.numel() == eli.shape[1] * 2:
                    y = y[: eli.shape[1]]
            mask = getattr(obj, "safety_mask", None)
            if mask is not None:
                mask = mask.to(device).bool()
            return x, ei, eli, ef, ei2, y, mask

    for epoch in range(epochs):
        model.train()
        tr_loss = 0.0
        for obj in train_objs:
            x, ei, eli, ef, ei2, y, mask = _to_device(obj)
            if y is None or y.numel() == 0:
                continue
            if eli.shape[1] != y.numel():
                y = y[: eli.shape[1]] if y.numel() > eli.shape[1] else y
                if y.numel() != eli.shape[1]:
                    continue
            opt.zero_grad()
            pred = model(x, ei, eli, ef, ei2)
            if pred.shape != y.shape:
                pred = pred[: y.numel()]
            loss = total_loss(pred, y, mask)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            tr_loss += loss.item()
        tr_loss /= max(len(train_objs), 1)

        model.eval()
        va_loss = 0.0
        with torch.no_grad():
            for obj in val_objs:
                x, ei, eli, ef, ei2, y, mask = _to_device(obj)
                if y is None or y.numel() == 0:
                    continue
                if eli.shape[1] != y.numel():
                    y = y[: eli.shape[1]] if y.numel() > eli.shape[1] else y
                    if y.numel() != eli.shape[1]:
                        continue
                pred = model(x, ei, eli, ef, ei2)
                if pred.shape != y.shape:
                    pred = pred[: y.numel()]
                va_loss += total_loss(pred, y, mask).item()
        va_loss /= max(len(val_objs), 1)
        sched.step(va_loss)

        if va_loss < best_val - 1e-6:
            best_val = va_loss
            no_imp = 0
            torch.save({"state_dict": model.state_dict(), "hparams": model.hparams}, ckpt_path)
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"best_val": best_val, "epoch": epoch + 1, "hparams": model.hparams, "train_loss": tr_loss}, f, indent=2)
        else:
            no_imp += 1

        if (epoch + 1) % 5 == 0 or epoch == 0:
            logger.info("Epoch %d/%d tr=%.4f va=%.4f lr=%.2e", epoch + 1, epochs, tr_loss, va_loss, opt.param_groups[0]["lr"])

        if no_imp >= patience:
            logger.info("Early stop at %d", epoch + 1)
            break

    return {"ok": True, "best_val": best_val, "checkpoint": str(ckpt_path)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", required=True)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    print(train(args.data_dir, epochs=args.epochs, lr=args.lr, device=args.device))
