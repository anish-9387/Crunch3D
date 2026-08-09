"""
services/optimization_events.py — Optimization telemetry log.

Every completed optimization is appended to ``training/optimization_events.jsonl``
as one JSON object per line. That log is the input to
``model.learning.data_prep``, which turns recorded jobs into self-supervised
training data for the GNN edge-importance predictor.

The log is append-only and best-effort: a failure to record telemetry must
never fail the optimization the user actually asked for.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

TRAINING_DIR = Path(__file__).parent.parent / "training"
OPTIMIZATION_EVENTS_FILE = TRAINING_DIR / "optimization_events.jsonl"

TRAINING_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=True) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []

    records: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_optimization_event(
    *,
    job_id: str,
    original_stats: dict,
    optimized_stats: dict,
    request_payload: dict,
    quality_meta: dict,
    processing_time_seconds: float,
    reduction_percent: float,
) -> None:
    """Append one completed optimization to the telemetry log.

    Swallows I/O errors on purpose — losing a telemetry line is acceptable,
    failing a finished optimization because of one is not.
    """
    event = {
        "timestamp_utc": _utc_now(),
        "job_id": job_id,
        "request": request_payload,
        "original_stats": original_stats,
        "optimized_stats": optimized_stats,
        "quality_meta": quality_meta,
        "processing_time_seconds": processing_time_seconds,
        "reduction_percent": reduction_percent,
    }
    try:
        _append_jsonl(OPTIMIZATION_EVENTS_FILE, event)
    except OSError as exc:
        logger.warning("Could not record optimization event for %s: %s", job_id, exc)


def count_optimization_events() -> int:
    """Number of optimizations recorded so far (0 if the log is absent)."""
    return len(_read_jsonl(OPTIMIZATION_EVENTS_FILE))
