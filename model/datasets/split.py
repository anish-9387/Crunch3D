from __future__ import annotations

import random
import shutil
from pathlib import Path

from ..core.config import SEED


def group_key(path: Path) -> str:
    name = path.stem
    for suffix in ["_90", "_80", "_75", "_70", "_60", "_50", "_25", "_10"]:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    if "_stage" in name:
        name = name.split("_stage")[0]
    return name


def split_dataset(src_dir: Path, out_root: Path, train=0.7, val=0.15, test=0.15, seed=SEED):
    src_dir = Path(src_dir)
    out_root = Path(out_root)
    files = sorted(src_dir.glob("*.pt"))
    if not files:
        files = sorted(src_dir.glob("*.npz"))
    groups: dict[str, list[Path]] = {}
    for p in files:
        groups.setdefault(group_key(p), []).append(p)
    keys = list(groups.keys())
    rng = random.Random(seed)
    rng.shuffle(keys)
    n = len(keys)
    n_train = int(n * train)
    n_val = int(n * val)
    train_keys = set(keys[:n_train])
    val_keys = set(keys[n_train : n_train + n_val])
    test_keys = set(keys[n_train + n_val :])

    for split_name, keyset in [("train", train_keys), ("val", val_keys), ("test", test_keys)]:
        d = out_root / split_name
        d.mkdir(parents=True, exist_ok=True)
        for k in keyset:
            for p in groups[k]:
                shutil.copy2(p, d / p.name)
    return {"train": len(train_keys), "val": len(val_keys), "test": len(test_keys), "objects": n}
