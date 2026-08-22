from pathlib import Path as _Path
from dotenv import load_dotenv as _load_dotenv
_load_dotenv(_Path(__file__).resolve().parent.parent / ".env")

import asyncio
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import routes

app = FastAPI(
    title="OptiMesh API",
    description="3D Mesh Optimization & LOD Generation Service",
    version="1.0.0",
)

default_origins = ["http://localhost:5173", "http://localhost:3000"]
configured_origins = os.getenv("CORS_ORIGINS", "")
allow_origins = (
    [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
    if configured_origins.strip()
    else default_origins
)
allow_origin_regex = os.getenv("CORS_ORIGIN_REGEX", r"https://.*\.vercel\.app")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)


async def _self_learning_loop() -> None:
    """Background task: grow the dataset and fine-tune the GNN on its own.

    Runs in a thread pool so heavy PyTorch work never blocks the event loop.
    """
    import logging

    from .learning.continuous_learning import (
        backfill_seed_batch,
        count_samples,
        retrain_now,
        seed_target_count,
        should_retrain,
    )

    logger = logging.getLogger(__name__)
    loop = asyncio.get_running_loop()

    while True:
        try:
            await asyncio.sleep(45)

            # 1. Backfill the procedural seed dataset toward the target size
            #    (bootstrap the "large dataset" without any downloads).
            target = seed_target_count()
            current = count_samples()
            if current < target:
                n = await loop.run_in_executor(None, backfill_seed_batch, 25)
                if n:
                    logger.info("Seed dataset backfill: +%d samples (now %d/%d)",
                                n, count_samples(), target)

            # 2. Fine-tune when enough real runs accumulated since last train.
            if should_retrain():
                metrics = await loop.run_in_executor(None, retrain_now)
                logger.info("Self-learning retrain: %s", metrics)

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Self-learning loop iteration failed")


@app.on_event("startup")
async def _startup() -> None:
    from .learning import continuous_learning

    if continuous_learning.AUTO_RETRAIN:
        app.state.learning_task = asyncio.create_task(_self_learning_loop())


@app.on_event("shutdown")
async def _shutdown() -> None:
    task = getattr(app.state, "learning_task", None)
    if task is not None:
        task.cancel()


@app.get("/")
async def root():
    return {
        "name": "OptiMesh API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "upload": "POST /api/upload",
            "optimize": "POST /api/optimize",
            "brush_refine": "POST /api/brush/refine",
            "recommend": "GET /api/recommend/{job_id}",
            "status": "GET /api/status/{job_id}",
            "importance": "GET /api/importance/{job_id}",
            "preview": "GET /api/preview/{job_id}",
            "download": "GET /api/download/{job_id}",
            "download_quota": "GET /api/download/quota",
            "learning_status": "GET /api/learning/status",
            "learning_retrain": "POST /api/learning/retrain",
        },
    }


@app.get("/health")
async def health():
    from .services import cloud_storage

    return {
        "status": "ok",
        "storage": cloud_storage.storage_info(),
    }