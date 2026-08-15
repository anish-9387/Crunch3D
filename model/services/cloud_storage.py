"""
services/cloud_storage.py — 3rd-party object storage for Crunch3D.

Meshes and their optimized outputs are stored in a Cloudflare R2 bucket
(or any S3-compatible provider — AWS S3, MinIO, Backblaze B2, etc.) so
the service never depends on the container's ephemeral filesystem.

Design
------
- ``STORAGE_BACKEND=cloud`` makes the bucket the *authoritative* store:
  every upload must succeed (misconfiguration fails fast at startup),
  and all previews/downloads are served from the bucket — never from the
  container disk.  The local filesystem is then only an ephemeral working
  cache for the mesh-processing engine.
- ``STORAGE_BACKEND=local`` (default) keeps the legacy local-disks
  behaviour, so development and CI stay untouched.
- R2 is the recommended target: $0 egress on downloads, S3-compatible
  API (boto3 works as-is), and a 10 GB free tier.  To point at AWS S3,
  only ``CLOUD_STORAGE_ENDPOINT``/``CLOUD_STORAGE_REGION`` change.
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import BinaryIO, Iterator

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


BUCKET = os.getenv("CLOUD_STORAGE_BUCKET", "crunch3d").strip()
ENDPOINT = os.getenv("CLOUD_STORAGE_ENDPOINT", "").strip().rstrip("/")
REGION = os.getenv("CLOUD_STORAGE_REGION", "auto").strip()
ACCESS_KEY = os.getenv("CLOUD_STORAGE_ACCESS_KEY", "").strip()
SECRET_KEY = os.getenv("CLOUD_STORAGE_SECRET_KEY", "").strip()
PUBLIC_BASE_URL = os.getenv("CLOUD_STORAGE_PUBLIC_BASE_URL", "").strip().rstrip("/")

BACKEND_CLOUD = os.getenv("STORAGE_BACKEND", "local").strip().lower() == "cloud"

if BACKEND_CLOUD and not (ENDPOINT and ACCESS_KEY and SECRET_KEY and BUCKET):
    raise RuntimeError(
        "STORAGE_BACKEND=cloud requires CLOUD_STORAGE_ENDPOINT, "
        "CLOUD_STORAGE_ACCESS_KEY, CLOUD_STORAGE_SECRET_KEY and "
        "CLOUD_STORAGE_BUCKET to be set."
    )

ENABLED = BACKEND_CLOUD

if ENABLED:
    try:
        import boto3  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "STORAGE_BACKEND=cloud requires the 'boto3' package. "
            "Run: pip install boto3"
        ) from exc

UPLOADS_PREFIX = "uploads"
PROCESSED_PREFIX = "processed"
META_PREFIX = "meta"

_client = None


def _get_client():
    """Lazily build the boto3 S3 client (S3-compatible, works with R2/AWS)."""
    global _client
    if _client is not None:
        return _client
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError(
            "Cloud storage is enabled but 'boto3' is not installed. "
            "Run: pip install boto3"
        ) from exc
    _client = boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name=REGION,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
    )
    return _client


def is_enabled() -> bool:
    return ENABLED


def storage_info() -> dict:
    """Non-secret storage configuration for diagnostics endpoints."""
    return {
        "backend": "cloud" if ENABLED else "local",
        "provider": (
            "cloudflare-r2" if "r2.cloudflarestorage.com" in ENDPOINT else "s3-compatible"
        )
        if ENABLED
        else None,
        "bucket": BUCKET if ENABLED else None,
        "public_base_url": PUBLIC_BASE_URL or None,
    }


def _key(prefix: str, job_id: str, filename: str) -> str:
    return f"{prefix}/{job_id}/{filename}"


def key_upload(job_id: str, filename: str) -> str:
    return _key(UPLOADS_PREFIX, job_id, filename)


def key_processed(job_id: str, filename: str) -> str:
    return _key(PROCESSED_PREFIX, job_id, filename)


def key_meta(job_id: str) -> str:
    return f"{META_PREFIX}/{job_id}/_job_meta.json"


def list_prefix(prefix: str) -> list[str]:
    """Return all object keys under a prefix (paginated)."""
    if not ENABLED:
        return []
    keys: list[str] = []
    try:
        client = _get_client()
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
    except Exception as exc:
        logger.warning("cloud_storage.list_prefix(%s) failed: %s", prefix, exc)
    return keys


def upload_file(key: str, path: str | Path) -> bool:
    """Upload a local file to the bucket.  Returns success."""
    if not ENABLED:
        return False
    try:
        _get_client().upload_file(str(path), BUCKET, key)
        return True
    except Exception as exc:
        logger.warning("cloud_storage.upload_file(%s) failed: %s", key, exc)
        return False


def upload_bytes(key: str, data: bytes) -> bool:
    if not ENABLED:
        return False
    try:
        _get_client().put_object(Bucket=BUCKET, Key=key, Body=data)
        return True
    except Exception as exc:
        logger.warning("cloud_storage.upload_bytes(%s) failed: %s", key, exc)
        return False


def download_file(key: str, path: str | Path) -> bool:
    """Fetch an object to a local file.  Returns success (False if absent)."""
    if not ENABLED:
        return False
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        _get_client().download_file(BUCKET, key, str(path))
        return True
    except Exception as exc:
        logger.warning("cloud_storage.download_file(%s) failed: %s", key, exc)
        return False


def open_stream(key: str) -> tuple[BinaryIO, int] | None:
    """Return an (file-like, size-in-bytes) reader for streaming responses."""
    if not ENABLED:
        return None
    try:
        resp = _get_client().get_object(Bucket=BUCKET, Key=key)
        size = int(resp.get("ContentLength", 0))
        body: BinaryIO = resp["Body"]
        # boto3's StreamingBody is not seekable; wrap so StreamingResponse can
        # iterate it directly.
        return body, size
    except Exception as exc:
        logger.warning("cloud_storage.open_stream(%s) failed: %s", key, exc)
        return None


def read_bytes(key: str) -> bytes | None:
    """Whole-object read; used for the small job-meta JSON."""
    if not ENABLED:
        return None
    try:
        resp = _get_client().get_object(Bucket=BUCKET, Key=key)
        return resp["Body"].read()
    except Exception as exc:
        logger.warning("cloud_storage.read_bytes(%s) failed: %s", key, exc)
        return None


def exists(key: str) -> bool:
    if not ENABLED:
        return False
    try:
        _get_client().head_object(Bucket=BUCKET, Key=key)
        return True
    except Exception:
        return False


def delete_prefix(prefix: str) -> bool:
    """Delete every object under a prefix (used by job cleanup)."""
    if not ENABLED:
        return False
    keys = list_prefix(prefix)
    if not keys:
        return True
    try:
        client = _get_client()
        for start in range(0, len(keys), 1000):
            chunk = [{"Key": k} for k in keys[start : start + 1000]]
            client.delete_objects(Bucket=BUCKET, Delete={"Objects": chunk})
        return True
    except Exception as exc:
        logger.warning("cloud_storage.delete_prefix(%s) failed: %s", prefix, exc)
        return False


def delete_objects(keys: list[str]) -> bool:
    if not ENABLED or not keys:
        return False
    try:
        client = _get_client()
        for start in range(0, len(keys), 1000):
            chunk = [{"Key": k} for k in keys[start : start + 1000]]
            client.delete_objects(Bucket=BUCKET, Delete={"Objects": chunk})
        return True
    except Exception as exc:
        logger.warning("cloud_storage.delete_objects failed: %s", exc)
        return False