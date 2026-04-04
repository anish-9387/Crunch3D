import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import mesh

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

app.include_router(mesh.router)


@app.get("/")
async def root():
    return {
        "name": "OptiMesh API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "upload": "POST /api/upload",
            "optimize": "POST /api/optimize",
            "feedback": "POST /api/feedback",
            "training_summary": "GET /api/training/summary",
            "training_bootstrap": "POST /api/training/bootstrap",
            "recommend": "GET /api/recommend/{job_id}",
            "status": "GET /api/status/{job_id}",
            "preview": "GET /api/preview/{job_id}",
            "download": "GET /api/download/{job_id}",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
