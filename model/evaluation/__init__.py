"""Quantitative evaluation harness (§52-59, §92)."""

from .benchmark import evaluate, load_mesh, run_benchmark
from .chamfer import bbox_diagonal, chamfer_distance, sample_surface
from .features import feature_metrics
from .laplacian import laplacian_spectrum, spectrum_error
from .normals import normal_error
from .topology import topology_metrics, wrong_adjacency

__all__ = [
    "bbox_diagonal",
    "chamfer_distance",
    "evaluate",
    "feature_metrics",
    "laplacian_spectrum",
    "load_mesh",
    "normal_error",
    "run_benchmark",
    "sample_surface",
    "spectrum_error",
    "topology_metrics",
    "wrong_adjacency",
]
