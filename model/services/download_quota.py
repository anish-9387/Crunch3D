"""
services/download_quota.py — Daily download quota (5 optimized models / 24h).

Users may optimize as many times as they like, but only a fixed number of
downloads per rolling 24-hour window per client.  There is no auth in this
MVP, so the client is identified by an anonymous device ID that the
frontend mints once and stores in localStorage (sent as ``X-Client-Id``).
Callers without a header fall back to their IP address, which still gives
curl/API users a fair share.

Storage is a tiny SQLite database (``data/usage.db``) so quotas survive
server restarts.  All functions are best-effort: if the DB write fails the
download is still served rather than erroring the whole response.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "usage.db"
WINDOW_SECONDS = 24 * 60 * 60  # rolling 24h
MAX_DOWNLOADS_PER_DAY = int(os.getenv("MAX_DOWNLOADS_PER_DAY", "5"))
PRUNE_KEEP_SECONDS = 7 * 24 * 60 * 60

_conn: sqlite3.Connection | None = None


def _connection() -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        return _conn
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS downloads (
            client_id     TEXT NOT NULL,
            job_id        TEXT NOT NULL,
            downloaded_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_downloads_client_time
        ON downloads (client_id, downloaded_at)
        """
    )
    conn.commit()
    _conn = conn
    return conn


def _query(client_id: str) -> int:
    cutoff = time.time() - WINDOW_SECONDS
    cur = _connection().execute(
        "SELECT COUNT(*) FROM downloads WHERE client_id = ? AND downloaded_at >= ?",
        (client_id, cutoff),
    )
    row = cur.fetchone()
    return int(row[0]) if row else 0


def is_enabled() -> bool:
    return MAX_DOWNLOADS_PER_DAY > 0


def get_quota(client_id: str) -> dict:
    """Return usage stats for a client without consuming anything."""
    used = _query(client_id) if is_enabled() else 0
    limit = MAX_DOWNLOADS_PER_DAY if is_enabled() else -1
    return {
        "daily_limit": limit,
        "downloads_used": used,
        "downloads_remaining": max(limit - used, 0) if is_enabled() else -1,
        "window_seconds": WINDOW_SECONDS,
        "resets_in_seconds": _resets_in(used),
    }


def _resets_in(used: int) -> int:
    """Seconds until the oldest counted download leaves the window."""
    if used == 0:
        return 0
    cutoff = time.time() - WINDOW_SECONDS
    cur = _connection().execute(
        "SELECT MIN(downloaded_at) FROM downloads "
        "WHERE client_id IS NOT NULL AND downloaded_at >= ?",
        (cutoff,),
    )
    row = cur.fetchone()
    if not row or row[0] is None:
        return 0
    return max(0, int(row[0] + WINDOW_SECONDS - time.time()))


def can_download(client_id: str) -> bool:
    """True if the client still has downloads left in the rolling window."""
    if not is_enabled():
        return True
    return _query(client_id) < MAX_DOWNLOADS_PER_DAY


def consume_download(client_id: str, job_id: str) -> bool:
    """Record one download.  Returns False when the quota is exhausted."""
    if not is_enabled():
        return True
    if _query(client_id) >= MAX_DOWNLOADS_PER_DAY:
        return False
    try:
        _connection().execute(
            "INSERT INTO downloads (client_id, job_id, downloaded_at) VALUES (?, ?, ?)",
            (client_id, job_id, time.time()),
        )
        _connection().commit()
        return True
    except Exception:
        # Never fail a download because telemetry could not be recorded.
        logger.exception("Failed to record download quota usage")
        return True


def prune() -> None:
    """Drop rows older than a week to keep the DB small."""
    try:
        cutoff = time.time() - PRUNE_KEEP_SECONDS
        _connection().execute(
            "DELETE FROM downloads WHERE downloaded_at < ?", (cutoff,)
        )
        _connection().commit()
    except Exception:
        pass