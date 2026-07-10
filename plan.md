# Crunch3D V2 — Complete Redesign Plan

> **Mission:** Outperform Crunch3D V1 and all existing mesh decimation approaches by combining multi-resolution spectral geometry processing, learned importance fields, adaptive manifold-aware decimation, perceptual error metrics, and asynchronous distributed execution into a single production-grade system.

---

## 1. Executive Summary

Crunch3D V1 is a functional MVP with significant architectural debt: PLY round-trip hacks for quality injection, pure-Python O(n²) loops for core algorithms, serial per-component processing, blocking event-loop execution, and a hand-weighted importance field with no learning capability.

**Crunch3D V2 redesign targets:**
- **10–50× speedup** through vectorized NumPy/CUDA importance computation, direct PyMeshLab buffer manipulation, and parallel per-component processing
- **50–80% better detail preservation** via learned importance fields, multi-resolution curvature, and perceptual error metrics
- **Formal non-manifold correctness** through local manifold repair + simplicial-complex inspired collapse ordering
- **Production readiness** with async task queues, persistent storage, multi-format export, scene graph preservation
- **Scientific rigor** with Hausdorff surface deviation, CSF-weighted perceptual metrics, and ablation-validated design choices

---

## 2. Architecture Review (V1)

### 2.1 Module Dependency Graph (V1)

```
mesh.py (router)
  ├── file_handler.py         — Job ID, path management
  ├── mesh_analyzer.py        — Stats via Trimesh
  ├── mesh_optimizer.py       — Core decimation engine
  │   ├── importance_mapper.py — Per-vertex importance
  │   │   └── curvature.py    — Fast/accurate curvature
  │   └── pymeshlab            — QEM edge collapse
  └── feedback_trainer.py     — Logging, preference model
```

### 2.2 Critical Architecture Flaws

| Issue | Location | Impact |
|-------|----------|--------|
| PLY round-trip for quality | `_inject_importance_as_quality()` | +3–8s per component, fragile parsing |
| OBJ round-trips bi-directional | `_component_to_pymeshlab()` / `_pymeshlab_to_trimesh()` | +1–3s per component, temp file I/O |
| Pure Python loops for adjacency/boundary/valence | `_build_adjacency()`, `_boundary_importance()`, `_feature_density()` | O(V·deg) in Python — 100× slower than vectorized |
| Blocking event loop | `decimate_mesh()` called directly from route | Entire server unresponsive during optimization |
| In-memory job store | `jobs: dict[str, dict]` | Lost on restart, no persistence |
| Serial per-component processing | `_decimate_all_components()` for-loop | No utilization of multi-core CPUs |
| Scene graph flattening | `_load_components()` applies transforms | Hierarchy lost, cannot re-export multi-mesh formats |
| Single-format output | `_save_current_mesh()` fallback to OBJ | GLB/GLTF inputs become OBJ-only output |
| Hand-weighted importance | Eq. (1)–(5) with fixed weights | Cannot adapt to mesh type or user preference |
| Point-sampled quality guard | 700-vertex random sample | Does not measure true surface deviation |

---

## 3. Mathematical Review (V1)

### 3.1 Importance Field

V1 computes four cues:
```
C(v) = |H(v)|               (discrete mean curvature)
N(v) = avg arccos(|n_f·n_v|)(normal variation)
B(v) = β if boundary        (boundary bonus)
D(v) = deg(v)               (valence)
```

**Problems:**
1. Curvature radius fixed at 2% of bbox — no automatic scale selection
2. Normal variation uses vertex normals, which are already smoothed averages — double smoothing reduces sensitivity
3. Boundary bonus is binary (0 or 0.3) — no distance-based falloff
4. Valence is a poor proxy for feature density on non-uniform triangulations
5. Laplacian smoothing with fixed α=0.5 and k=3 — no convergence criterion, no edge-awareness

### 3.2 Quality Guard

```
δ = max(P95(NND(ref→opt)), P95(NND(opt→ref))) / D_bbox × 100
```

**Problems:**
1. Point-to-point nearest neighbor does not equal surface-to-surface distance
2. 700-point random sample has ~√700 ≈ 26-point effective resolution per axis
3. No statistical confidence interval — single measurement, no variance estimation
4. Bidirectional max is conservative but the 95th percentile discards the worst 5% of errors — contradicting the "guarantee"

### 3.3 QEM Formulation

Standard quadric: Q(v) = vᵀAv + 2bᵀv + c

V1 modifies collapse cost via quality-weighting:
```
cost(e) = quality(v₁)·Q(v₁) + quality(v₂)·Q(v₂)
```

**Problem:** PyMeshLab's `qualityweight` flag is poorly documented. The debug test (`test_weighted_qem.py`) was designed specifically to verify whether this flag actually produces different output — indicating uncertainty about whether the importance injection works at all.

---

## 4. Algorithm Review (V1)

### 4.1 Asymptotic Complexity (V1)

| Algorithm | Complexity | Real bottleneck |
|-----------|-----------|-----------------|
| Importance: curvature (fast) | O(V·deg) Python loops | ~66ms/module — acceptable |
| Importance: boundary | O(F) Python dict ops | ~50ms — should be O(F) vectorized |
| Importance: feature density | O(F) Python array ops | ~30ms — trivial but pure Python |
| Adjacency build | O(F·3) Python set ops | ~100ms for 500K faces |
| Laplacian smoothing | O(V·deg·k) Python | ~200ms for 3 iterations |
| PLY injection | O(V + H) string ops | ~2–5s file I/O |
| QEM decimation | O(V log V) | Fast (~500ms) — not the bottleneck |
| Quality guard NN | O(S·V) chunked, S=700 | ~1–3s per deviation check |

**Key insight:** The *infrastructure* (file I/O, Python loops, format conversions) dominates the *actual computation* (QEM) by 5–10×.

### 4.2 Vectorization Opportunities

1. **Normal variation**: Replace Python loop with `np.einsum('ij,ij->i', ...)` and scatter-add
2. **Boundary detection**: Use `np.bincount` on flattened edge indices
3. **Adjacency**: Use sparse COO matrix → CSR format
4. **Laplacian**: Matrix-form: `x^{t+1} = (I - αL)x^t` with sparse Laplacian
5. **Quality NN**: Use `scipy.spatial.cKDTree` instead of chunked brute-force

---

## 5. Literature Survey (Expanded)

### 5.1 Classical Quadric Error Metrics

| Work | Year | Contribution | Limitation |
|------|------|-------------|------------|
| Garland & Heckbert | 1997 | QEM for surface simplification | Uniform treatment, manifold assumption |
| Garland & Heckbert | 1998 | Attribute-aware QEM (color+UV) | Degrades at texture seams |
| Lindstrom & Turk | 1998 | Volume-preserving simplification | No perceptual metric |
| Hoppe et al. | 1993 | Mesh optimization | Slow, not real-time |
| Cohen et al. | 1996 | Simplification envelopes | Conservative but complex |

### 5.2 Importance-Weighted and Adaptive Simplification

| Work | Year | Contribution | Limitation |
|------|------|-------------|------------|
| Bo et al. | 2026 | Multi-constraint QEM with seam/sharpness/texture | No non-manifold handling, no learned component |
| Lee et al. | 2005 | Mesh saliency via center-surround | Multi-scale but hand-designed |
| Castello et al. | 2008 | Perceptual simplification | View-dependent, not general-purpose |
| Zhang et al. | 2015 | Feature-preserving QEM with normal tensor | No texture awareness |
| **Crunch3D V2** | **2026** | **Multi-cue importance + learned field + perceptual guard** | **Proposed** |

### 5.3 Non-Manifold and Wild-Mesh Processing

| Work | Year | Contribution | Limitation |
|------|------|-------------|------------|
| Liu et al. | 2025 | Simplicial 2-complex decimation | No importance weighting, no texture |
| Gueunet et al. | 2019 | Parallel decimation | Manifold-only |
| Trettner & Kobbelt | 2020 | Fast floating-point decimation | Geometry-only |
| **Crunch3D V2** | **2026** | **Hybrid: component split + local manifold repair + importance** | **Proposed** |

### 5.4 Geometric Deep Learning for Meshes

| Work | Year | Contribution | Limitation |
|------|------|-------------|------------|
| Sharp et al. (DiffusionNet) | 2022 | Discretization-agnostic learning on surfaces | No decimation-specific training |
| Sun et al. (HKS) | 2009 | Heat kernel signature | Multi-scale but fixed |
| Bronstein et al. | 2017 | Geometric deep learning survey | Framework, not application |
| Ranjan et al. | 2018 | Mesh autoencoders | Requires fixed topology |
| **Crunch3D V2** | **2026** | **DiffusionNet-based importance predictor** | **Proposed** |

### 5.5 Perceptual Error Metrics

| Work | Year | Contribution | Limitation |
|------|------|-------------|------------|
| Barten | 1999 | Contrast sensitivity function model | Complex calibration |
| Daly (VDP) | 1993 | Visible differences predictor | Heavy computation |
| Mantiuk et al. | 2011 | HDR-VDP-2 | Designed for images, not geometry |
| Lavoué & Mantiuk | 2015 | Quality metric for 3D meshes | No CSF adaptation |
| **Crunch3D V2** | **2026** | **CSF-weighted perceptual surface deviation** | **Proposed** |

### 5.6 Comparison Table

| Property | Garland97 | Bo26 | Liu25 | Sharp22 | Crunch3D V1 | **Crunch3D V2** |
|----------|-----------|------|-------|---------|-------------|-----------------|
| QEM base | ✓ | ✓ | Extended | — | ✓ | **✓+ Direct buffer** |
| Importance weighting | — | Partial | — | — | ✓ PLY hack | **✓ Direct injection** |
| Non-manifold handling | — | — | ✓ Simplicial | — | Partial (split) | **✓ Hybrid** |
| Learned importance | — | — | — | ✓ (unrelated task) | — | **✓ DiffusionNet** |
| Perceptual metric | — | — | — | — | Point NN | **✓ Hausdorff + CSF** |
| Texture awareness | — | ✓ | Partial | — | — | **✓ UV budget + SLIM** |
| Async processing | — | — | — | — | — | **✓ Celery** |
| Scene graph preservation | — | — | — | — | — | **✓ GLB multi-node** |
| Production tests | — | — | — | — | — | **✓ 90%+ coverage** |

---

## 6. Weakness Analysis (Critical Review)

### 6.1 SEVERE: PLY Round-Trip Importance Injection

**Why it's severe:** Every importance-weighted decimation writes an ASCII PLY file, edits it line-by-line with string manipulation, reads it back, applies a function, and deletes the old mesh. This is:
- **Fragile:** One format change in PyMeshLab breaks it silently
- **Slow:** 2–5s per component, scaling with vertex count
- **Error-prone:** The `test_weighted_qem.py` debug script was created specifically because the team couldn't verify whether the hack actually works
- **Untestable:** String-based PLY editing cannot be unit tested reliably

### 6.2 SEVERE: No Async Job Queue

**Why it's severe:** FastAPI routes call `decimate_mesh()` synchronously. A 240-second optimization blocks the entire server — all other uploads, status checks, and downloads hang. The README acknowledges this but treats it as a known limitation rather than a critical architectural flaw.

### 6.3 MODERATE: Python Loop Bottlenecks

Three core algorithms use pure Python loops over faces/vertices:
- `_boundary_importance()` — dict-based edge counting
- `_feature_density()` — per-face valence increment  
- `_build_adjacency()` — per-face set updates
- `_laplacian_smooth()` — per-vertex neighbor iteration

For a 500K-face mesh, these loops execute ~1.5M iterations each in CPython — ~50–100× slower than vectorized alternatives.

### 6.4 MODERATE: Point-Sampled Quality Guard

The quality guard samples 700 vertices randomly. For a mesh with 500K vertices:
- Sampling covers 0.14% of vertices
- Nearest-neighbor distances are point-to-point, not surface-to-surface
- The 95th percentile discards the worst 5% of errors
- No confidence interval or statistical rigor

### 6.5 MODERATE: Scene Graph Loss

Multi-mesh formats (GLB, GLTF, FBX) have their transforms applied to flatten geometry. This means:
- Mesh hierarchy is lost
- Cannot re-export as multi-node GLB
- Individual component materials/textures are merged

### 6.6 MINOR: Hand-Weighted Importance

The four cue weights (0.45, 0.20, 0.20, 0.15) are "empirically set" — no ablation study, no cross-validation, no dataset-driven optimization.

### 6.7 MINOR: No Texture Awareness, No Animation Awareness

Both are on the roadmap but unimplemented. V2 must address both.

### 6.8 CODE QUALITY: No Tests

Zero unit tests. Zero integration tests. Zero CI/CD. The only "tests" are debug scripts with hardcoded paths to a specific developer's machine.

---

## 7. Proposed Improvements (V2)

### 7.1 Direct Quality Array Injection (P0)

**Instead of:** PLY round-trip hack
**Do:** Use PyMeshLab's `compute_scalar_by_function_per_vertex` with a formula, OR patch PyMeshLab to expose `set_vertex_quality_array()`, OR use direct NumPy buffer sharing via `mesh.vertex_quality_array()` if accessible.

**Fallback:** Write a small Cython/C extension that directly manipulates PyMeshLab's internal mesh structure.

**Expected gain:** Eliminate 2–5s per component, remove the most fragile code in the system.

### 7.2 In-Process Mesh Transfer (P0)

**Instead of:** OBJ file round-trips
**Do:** Directly construct PyMeshLab mesh from NumPy arrays using `ml.Mesh(vertex_matrix=..., face_matrix=...)` constructor (available in PyMeshLab 2025.7+).

**Expected gain:** Eliminate 1–3s per component, remove temp file I/O entirely.

### 7.3 Vectorized Importance Computation (P0)

**Instead of:** Python loops for boundary, valence, adjacency, Laplacian
**Do:** Use NumPy vectorized operations and SciPy sparse matrices.

**Boundary detection (vectorized):**
```python
faces_sorted = np.sort(mesh.faces, axis=1)
edge_keys = np.column_stack([
    faces_sorted[:, [0, 1]],
    faces_sorted[:, [1, 2]],
    faces_sorted[:, [2, 0]],
]).reshape(-1, 2)
# Hash each edge pair to a single integer
edge_ids = edge_keys[:, 0] * n_verts + edge_keys[:, 1]
counts = np.bincount(edge_ids, minlength=n_verts*n_verts)
boundary_mask = (counts[edge_ids] == 1)
```

**Laplacian smoothing (matrix form):**
```python
n = len(vertices)
L = sparse.csr_matrix(...)  # cotangent Laplacian
for _ in range(k):
    x = (1 - alpha) * x + alpha * (L @ x) / deg
```

**Expected gain:** 10–100× speedup on importance computation.

### 7.4 Async Task Queue (P0)

**Instead of:** Synchronous route handler
**Do:** Use Celery + Redis for task queue. The `/api/optimize` endpoint returns immediately with a task ID. Frontend polls `/api/status/{job_id}` for completion.

**Expected gain:** Server remains responsive during long optimizations. Enables parallel processing.

### 7.5 Persistent Storage (P1)

**Instead of:** In-memory dict
**Do:** SQLite for job metadata + filesystem for mesh files. Optional Redis for hot caching.

### 7.6 Parallel Per-Component Processing (P1)

**Instead of:** Serial for-loop over components
**Do:** Use `concurrent.futures.ProcessPoolExecutor` or Celery chord for parallel component decimation. Each component gets its own worker process (avoids GIL).

**Expected gain:** N-component speedup on multi-core systems (typically 2–4× for 4+ component meshes).

### 7.7 Learned Importance Field via Spectral GNN (P2)

**Instead of:** Four hand-weighted cues
**Do:** A lightweight graph neural network (inspired by DiffusionNet but 10× smaller) that takes 16 spectral features per vertex (first 8 HKS scales + 8 WKS scales) and outputs a single importance score.

**Training:** Use a dataset of 10,000+ meshes with artist-annotated importance maps or automatically generated from "where does QEM fail?" analysis.

**Expected gain:** 50–80% better retention of perceptually important features.

### 7.8 Perceptual Quality Guard (P1)

**Instead of:** Point-to-point NN at 95th percentile
**Do:** 
1. Use one-sided Hausdorff distance for surface-to-surface deviation
2. Weight error by CSF at platform-typical viewing distance
3. Report with 95% confidence interval via bootstrapping
4. Maximum error (100th percentile) for true guarantee

### 7.9 Scene Graph Preservation (P1)

**Instead of:** Applying transforms and flattening
**Do:** Maintain a scene DAG. Decimate each leaf mesh independently, then reconstruct the scene hierarchy.

### 7.10 Multi-Format Export (P1)

Support GLB (with scene graph), GLTF (separate files + JSON), PLY, STL, OBJ output.

### 7.11 Texture Budget Reallocation (P2)

After decimation, re-parameterize UVs using SLIM and allocate texel density proportional to importance.

### 7.12 Comprehensive Test Suite (P0)

- Unit tests for all services (pytest, 90%+ coverage)
- Integration tests for API endpoints
- Regression tests for known mesh types
- Performance regression benchmarks in CI

---

## 8. Redesigned Architecture (V2)

### 8.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React + Three.js)               │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP/WS
┌───────────────────────▼─────────────────────────────────────┐
│              FastAPI Gateway + WebSocket                     │
├─────────────────────────────────────────────────────────────┤
│  Auth        Rate Limit     Request Validation               │
└───────────┬──────────────────────────────┬──────────────────┘
            │                              │
┌───────────▼──────────┐   ┌───────────────▼──────────────────┐
│  Redis (Cache/Queue)  │   │  PostgreSQL (Job Store)          │
└───────────┬──────────┘   └───────────────┬──────────────────┘
            │                              │
┌───────────▼──────────────────────────────▼──────────────────┐
│              Celery Workers (N instances)                   │
├─────────────────────────────────────────────────────────────┤
│  Worker 1: Component A  │  Worker 2: Component B           │
│  ├─ Trimesh Analysis    │  ├─ Trimesh Analysis              │
│  ├─ Importance (GPU/CPU)│  ├─ Importance (GPU/CPU)          │
│  ├─ QEM Decimation     │  ├─ QEM Decimation                │
│  └─ Quality Check      │  └─ Quality Check                 │
├─────────────────────────────────────────────────────────────┤
│  Worker 3: Merge + LOD Package                               │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Module Structure (V2)

```
backend/
├── main.py                       # FastAPI app, middleware, routes
├── config.py                     # All configurable constants
├── requirements.txt
├── Dockerfile
├── docker-compose.yml            # FastAPI + Redis + PostgreSQL + Celery
│
├── core/
│   ├── __init__.py
│   ├── task_queue.py             # Celery app, task definitions
│   ├── storage.py                # PostgreSQL + Redis job store
│   └── scene_graph.py            # DAG-based scene hierarchy
│
├── analysis/
│   ├── __init__.py
│   ├── mesh_stats.py             # Stats extraction (replaces mesh_analyzer.py)
│   ├── diagnostic.py             # Topology analysis, non-manifold detection
│   └── texture.py                # UV analysis, texel density
│
├── importance/
│   ├── __init__.py
│   ├── cues.py                   # Vectorized cue computation (all 4+ cues)
│   ├── spectral.py               # HKS, WKS, spectral descriptors
│   ├── laplacian.py              # Sparse cotangent Laplacian, smoothing
│   ├── learning.py               # DiffusionNet-based learned importance
│   ├── geodesic.py               # Heat-method geodesic protection
│   └── fusion.py                 # Multi-cue fusion (learned or weighted)
│
├── decimation/
│   ├── __init__.py
│   ├── direct_qem.py             # Direct buffer access to PyMeshLab QEM
│   ├── manifold_repair.py        # Local non-manifold repair
│   ├── quality_injector.py       # Direct quality array injection (NO PLY)
│   └── guard.py                  # Perceptual quality guard (Hausdorff + CSF)
│
├── export/
│   ├── __init__.py
│   ├── scene_reconstructor.py    # Rebuild scene DAG after decimation
│   ├── format_converter.py       # Multi-format export (GLB, GLTF, OBJ, etc.)
│   └── lod_packager.py           # LOD ZIP package
│
├── learning/
│   ├── __init__.py
│   ├── dataset.py                # Mesh dataset construction
│   ├── trainer.py                # Importance model training
│   └── inference.py              # ONNX Runtime inference
│
├── training/                     # Training data (same as V1)
│
├── api/
│   ├── __init__.py
│   ├── routes.py                 # All API endpoints
│   ├── schemas.py                # Pydantic models (extended)
│   └── middleware.py             # Auth, rate limiting, CORS
│
└── tests/
    ├── conftest.py               # Fixtures, test meshes
    ├── test_importance.py
    ├── test_decimation.py
    ├── test_quality_guard.py
    ├── test_api.py
    └── test_scene_graph.py
```

### 8.3 Data Flow (V2)

```
1. POST /api/upload
   → Save file to S3/filesystem
   → Store metadata in PostgreSQL (job_id, filename, status='uploaded')
   → Return job_id

2. POST /api/optimize
   → Validate request
   → Enqueue Celery task: optimize_mesh(job_id, params)
   → Update job status to 'processing'
   → Return immediately with job_id

3. Celery Worker: optimize_mesh(job_id, params)
   a. Load mesh from storage → Trimesh
   b. Load scene DAG from storage
   c. For each component (parallel via chord):
      i.   Extract component with world-space transform
      ii.  Compute importance field (vectorized cues + optional learned model)
      iii. Direct-inject quality into PyMeshLab buffer
      iv.  Run QEM decimation
      v.   Check perceptual quality guard
      vi.  If fail: relax target, retry (up to 3 iterations)
   d. Merge components → scene DAG reconstruction
   e. Generate LOD package
   f. Export to requested format
   g. Store result metadata in PostgreSQL
   h. Update job status to 'completed'

4. Frontend polls GET /api/status/{job_id}
   → Returns current status, progress percentage, stage description

5. GET /api/download/{job_id}
   → Stream result file(s) from storage
```

### 8.4 Database Schema

```sql
-- Jobs table
CREATE TABLE jobs (
    job_id          TEXT PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'uploaded',
    progress        INTEGER NOT NULL DEFAULT 0,
    stage           TEXT,
    error_message   TEXT,
    filename        TEXT NOT NULL,
    original_format TEXT NOT NULL,
    original_faces  INTEGER NOT NULL,
    original_verts  INTEGER NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    bbox_diagonal   REAL,
    has_uvs         BOOLEAN DEFAULT FALSE,
    has_normals     BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Optimization runs (one job can have multiple)
CREATE TABLE optimizations (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id                  TEXT NOT NULL REFERENCES jobs(job_id),
    request_json            TEXT NOT NULL,          -- Full OptimizeRequest
    target_faces_used       INTEGER NOT NULL,
    result_faces            INTEGER NOT NULL,
    result_verts            INTEGER NOT NULL,
    result_file_size        INTEGER,
    result_format           TEXT NOT NULL,
    quality_deviation_pct   REAL,
    quality_guard_relaxed   BOOLEAN DEFAULT FALSE,
    quality_guard_satisfied BOOLEAN DEFAULT TRUE,
    processing_time_seconds REAL NOT NULL,
    reduction_percent       REAL NOT NULL,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Importance scores (stored as BLOB for large arrays)
CREATE TABLE importance_maps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      TEXT NOT NULL REFERENCES jobs(job_id),
    component_index INTEGER NOT NULL,
    scores_blob BLOB NOT NULL,                     -- np.float64 serialized
    vertex_count INTEGER NOT NULL,
    method      TEXT NOT NULL,                      -- 'v1_weighted', 'learned_v2', etc.
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Feedback
CREATE TABLE feedback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT NOT NULL REFERENCES jobs(job_id),
    optimization_id INTEGER REFERENCES optimizations(id),
    satisfied       BOOLEAN NOT NULL,
    preserve_shape  BOOLEAN NOT NULL,
    preserve_vertices BOOLEAN NOT NULL,
    preserve_faces  BOOLEAN NOT NULL,
    rating          INTEGER,
    issues          TEXT,                           -- JSON array
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 8.5 API Contracts (Extended)

| Method | Endpoint | V1 | V2 |
|--------|----------|----|----|
| POST | `/api/upload` | Blocking, returns stats | Same but async metadata extraction |
| POST | `/api/optimize` | Blocking, waits for result | Returns immediately with task_id |
| GET | `/api/status/{job_id}` | Basic status | Detailed: progress%, stage, ETA |
| GET | `/api/download/{job_id}` | Single OBJ or ZIP | Multi-format, multi-file |
| GET | `/api/preview/{job_id}` | Stream file | Same + WebSocket progress |
| POST | `/api/feedback` | Same | Enhanced with component-level ratings |
| POST | `/api/training/bootstrap` | Same | V2 model training |
| GET | `/api/recommend/{job_id}` | Basic heuristic | ML-based recommendation |
| **NEW** | `WS /api/ws/{job_id}` | — | Real-time progress + intermediate preview |
| **NEW** | `POST /api/importance/learn` | — | Trigger model re-training |
| **NEW** | `GET /api/health/workers` | — | Worker pool status |

---

## 9. Mathematical Enhancements

### 9.1 Multi-Resolution Curvature with Automatic Scale Selection

**V1:** Fixed radius r = 0.02 × D_bbox

**V2:** Compute curvature at multiple scales and select dominant scale per vertex:

```
C(v) = max_{s ∈ S} |H_s(v)| · w(s)

where S = {0.005, 0.01, 0.02, 0.04, 0.08} × D_bbox
      w(s) ∝ exp(-(s - s_median)² / 2σ²)   // scale-space normalization
      H_s(v) = discrete mean curvature at scale s
```

This automatically adapts: fine detail uses small radii, broad features use large radii.

### 9.2 Cotangent Laplacian Formulation

**V1:** Simple graph Laplacian: L_ij = 1 if edge, 0 otherwise (unnormalized)

**V2:** Sparse cotangent Laplacian (discrete Laplace-Beltrami):

```
L_ij = ½(cot α_ij + cot β_ij)   for edge (i, j)
L_ii = -∑_j L_ij

where α_ij, β_ij are the angles opposite edge (i, j) in the two adjacent triangles
```

This gives a proper discretization of the Laplace-Beltrami operator on the mesh, with:
- **Better smoothing:** Edge-aware, respects triangle shape
- **Spectral decomposition:** Eigenvalues approximate continuous Laplacian
- **DiffusionNet compatibility:** The LBO is the foundation for geometric deep learning

### 9.3 Vectorized Laplacian Smoothing (Matrix Form)

**V1:** `x_i^(t+1) = (1-α) · x_i^(t) + α · mean(neighbors(x_i)^(t))`

**V2:** `x^(t+1) = (1-α) · x^(t) + α · M⁻¹L x^(t)`

where M is the lumped mass matrix (M_ii = area of vertex i's Voronoi cell) and L is the cotangent Laplacian.

In sparse matrix form:
```
x_t = D_inv @ (L @ x)   // one matrix-vector multiply
x_new = (1 - alpha) * x + alpha * x_t
```

**Expected gain:** 100–1000× faster for large meshes, with physically meaningful diffusion.

### 9.4 Hausdorff Surface Deviation

**V1:** Point-to-point NN at 95th percentile

**V2:** One-sided Hausdorff distance with bootstrapped confidence:

```
δ = max( h(M₁, M₂), h(M₂, M₁) ) / D_bbox × 100

h(M₁, M₂) = max_{p ∈ M₁} min_{q ∈ M₂} ||p - q||

With confidence interval via bootstrapping (B = 1000):
  δ_lower, δ_upper = percentile(δ_bootstrap, [2.5, 97.5])
```

Implementation: Use `scipy.spatial.cKDTree` for O(V log V) nearest neighbor.

### 9.5 Perceptual Error Weighting (CSF)

```
δ_perc(v) = δ_geom(v) · CSF(f_spatial(v) / d_camera)

CSF(f) = a · f^c · exp(-b · f^d)   // Barten's model
a = 2.6, b = 0.019, c = 0.53, d = 1.11  // calibrated parameters

f_spatial(v) = 1 / (2 · ||v - v_neighbor||)   // local spatial frequency
d_camera = platform_typical_distance / D_bbox
```

Platform distances: Web=0.5m, Mobile=0.3m, PC=0.6m, VR=0.2m (interpupillary).

### 9.6 Geodesic-Guided Importance Diffusion (Heat Method)

For artist-directed protection:

```
(I - tL)u = δ_S    // one sparse linear solve
φ = gradient_descent(normalize(gradient(u)))

Protection field: P(v) = exp(-φ(v)² / 2σ²)
Combined importance: I'(v) = I(v) · (1 - P(v)) + P(v)
```

The heat method gives geodesic distance from selected vertices via a single sparse solve — no Dijkstra/A* required.

### 9.7 DiffusionNet-Based Learned Importance

Replace hand-weighted cues with learned per-vertex importance:

```
Input features:  HKS(t₁...t₈) ⊕ WKS(e₁...e₈) ⊕ [x, y, z] ⊕ N_vertex
    ↓
DiffusionNet layer 1:  u¹ = MLP(features, exp(-t¹L)·features, ∇_intr features)
DiffusionNet layer 2:  u² = MLP(u¹, exp(-t²L)·u¹, ∇_intr u¹)
DiffusionNet layer 3:  u³ = MLP(u², exp(-t³L)·u², ∇_intr u²)
    ↓
Output: I(v) = sigmoid(MLP(u³)) ∈ [0, 1]
```

The per-channel diffusion times t^(1), t^(2), t^(3) are learned, not fixed.

### 9.8 Direct Quality Array Injection

**The fundamental math:** QEM collapse cost for edge (i, j):

```
Cost(i, j) = quality(i) · Q_i(v_opt) + quality(j) · Q_j(v_opt)

where v_opt = QEM-optimal vertex position
      quality(v) = importance(v)  // higher = protect
```

**In V2**, we directly set the per-vertex quality scalar in PyMeshLab's vertex container using one of:
1. `mesh.vertex_quality_array()[:] = importance` (PyMeshLab 2025.7+)
2. `compute_scalar_by_function_per_vertex` with formula `q = importance_function(v_index)`
3. Custom C extension that writes to `ml::MeshVertex::Quality()`

This eliminates the PLY round-trip entirely.

### 9.9 SRP (Spectral Redundancy Pruning)

**Novel contribution:** Identify edges that contribute minimal spectral energy to the mesh Laplacian's low-frequency eigenvectors, and mark them for preferential collapse.

```
For edge (i, j):
  ΔΦ_ij = ∑_{k=1}^{K} |φ_k(i) - φ_k(j)|²    // spectral variation across edge
  w_sr(ij) = exp(-ΔΦ_ij² / 2σ²)              // spectral redundancy weight

Modified collapse cost:
  Cost'(i, j) = Cost_QEM(i, j) · (1 - β · w_sr(ij))
```

Edges with low spectral variation (i.e., both endpoints have similar low-frequency eigenvector values) are geometrically redundant and can be collapsed first. This preserves high-frequency detail (features, edges) while simplifying smooth regions.

---

## 10. Engineering Roadmap

### Phase 0: Foundation (Weeks 1–2)

| Task | Effort | Dependencies |
|------|--------|-------------|
| Set up PostgreSQL + Redis + Celery docker-compose | 1 day | None |
| Implement async task queue wrapper | 2 days | Celery |
| Implement persistent job store (SQLAlchemy + PostgreSQL) | 2 days | PostgreSQL |
| Implement scene graph DAG model | 2 days | Trimesh |
| Set up pytest framework, conftest, GitHub Actions CI | 1 day | None |
| Rewrite file_handler with S3-compatible storage | 1 day | None |
| **Deliverable:** CICD pipeline with job persistence, no functionality regression | | |

### Phase 1: Core Decimation Engine Rewrite (Weeks 3–4)

| Task | Effort | Dependencies |
|------|--------|-------------|
| Implement direct PyMeshLab buffer access for quality injection | 3 days | Phase 0 |
| Eliminate all OBJ round-trips (in-memory mesh transfer) | 2 days | Phase 0 |
| Vectorize boundary detection (NumPy bincount) | 1 day | None |
| Vectorize feature density (NumPy bincount) | 0.5 day | None |
| Implement sparse cotangent Laplacian | 2 days | None |
| Implement matrix-form Laplacian smoothing | 1 day | Sparse Laplacian |
| Implement Hausdorff quality guard with bootstrapped CI | 2 days | None |
| **Deliverable:** V2 decimation engine, 10–50× faster than V1, no PLY hacks | | |

### Phase 2: Per-Component Parallelism + Async (Week 5)

| Task | Effort | Dependencies |
|------|--------|-------------|
| Implement Celery chord for parallel component decimation | 2 days | Phase 0–1 |
| Convert API routes to async (return task_id immediately) | 1 day | Phase 0–1 |
| Add WebSocket progress channel | 2 days | Phase 0 |
| Implement progress tracking with ETA estimation | 1 day | WebSocket |
| Handle partial failures (one component fails → log + continue) | 1 day | Phase 0–1 |
| **Deliverable:** Non-blocking server, parallel decimation, real-time WebSocket progress | | |

### Phase 3: Multi-Format Export + Scene Graph (Week 6)

| Task | Effort | Dependencies |
|------|--------|-------------|
| Implement GLB export with scene hierarchy | 2 days | Scene graph |
| Implement GLTF export | 1 day | Scene graph |
| Implement PLY/STL/OBJ export | 1 day | None |
| Implement format auto-detection based on input | 0.5 day | None |
| Texture pass-through (simple copy, no re-encoding) | 1 day | None |
| **Deliverable:** Same-format round-trip (GLB→GLB, FBX→GLB) with maintained hierarchy | | |

### Phase 4: Enhanced Metrics (Weeks 7–8)

| Task | Effort | Dependencies |
|------|--------|-------------|
| Implement multi-resolution curvature (5 scales) | 2 days | Sparse Laplacian |
| Implement HKS + WKS spectral descriptors | 3 days | Sparse eigendecomposition |
| Implement CSF perceptual error weighting | 1 day | Hausdorff (Phase 1) |
| Implement heat-method geodesics for interactive protection | 2 days | Sparse Laplacian |
| Implement spectral redundancy pruning | 2 days | Sparse eigendecomposition |
| **Deliverable:** All mathematical enhancements from §9 integrated and tested | | |

### Phase 5: Learned Importance Model (Weeks 9–11)

| Task | Effort | Dependencies |
|------|--------|-------------|
| Collect/curate training dataset (10K+ meshes with importance annotations) | 1 week | None |
| Implement DiffusionNet backbone in PyTorch | 3 days | Phase 4 (spectral features) |
| Train initial model on synthetic data | 2 days | Dataset + DiffusionNet |
| Validate with ablation study (5-fold cross-validation) | 2 days | Trained model |
| Export to ONNX for inference | 1 day | Trained model |
| Implement CUDA + CPU fallback inference | 2 days | ONNX model |
| **Deliverable:** ONNX-based learned importance predictor, 50–80% better than hand-weighted | | |

### Phase 6: Texture Awareness (Weeks 12–13)

| Task | Effort | Dependencies |
|------|--------|-------------|
| Implement UV distortion analysis | 2 days | None |
| Implement SLIM re-parameterization (wrap existing library) | 3 days | Phase 1 |
| Implement importance-weighted texel density allocation | 2 days | Learned importance |
| Extend quality guard with texture RMS metric | 1 day | Phase 1 |
| **Deliverable:** Texture-preserving decimation with budget reallocation | | |

### Phase 7: Testing + Hardening (Week 14)

| Task | Effort | Dependencies |
|------|--------|-------------|
| Unit tests: 90%+ coverage on all services | 3 days | All phases |
| Integration tests: API endpoints, workflows | 2 days | All phases |
| Performance regression benchmarks | 1 day | All phases |
| Documentation: README, API docs, architecture | 2 days | All phases |
| Load testing: 100 concurrent optimizations | 1 day | All phases |
| **Deliverable:** Ship-ready V2 system | | |

---

## 11. Benchmark Plan

### 11.1 Test Corpus

| Category | Source | Count | Typical Size | Diversity |
|----------|--------|-------|-------------|-----------|
| Organic/Character | Objaverse, Sketchfab | 50 | 200K–800K faces | Human, animal, creature |
| Architectural | Thingi10K, BIM | 50 | 50K–2M faces | Buildings, interiors, components |
| Mechanical | MCB, Fusion360 | 50 | 100K–1.5M faces | Gears, engines, tools |
| AI-Generated | Tripo3D, Meshy | 50 | 300K–800K faces | Text-to-3D outputs |
| Scanned | Stanford, Megascans | 50 | 500K–4M faces | Photogrammetry, LIDAR |
| Non-Manifold | Thingi10K subset | 50 | 10K–500K faces | Multi-body, boundary, T-junctions |

**Total: 300 meshes**

### 11.2 Metrics

| Metric | Tool | Gold Standard |
|--------|------|---------------|
| Surface deviation (max) | Hausdorff distance | ≤ 1% of D_bbox |
| Surface deviation (mean) | Mean Hausdorff | ≤ 0.3% of D_bbox |
| Surface deviation (RMS) | RMS Hausdorff | ≤ 0.5% of D_bbox |
| Perceptual deviation | CSF-weighted Hausdorff | Platform-dependent |
| Face reduction | Count | Matches target ± 2% |
| Processing time | Wall clock | < 30s for 500K faces |
| Memory peak | `memory_profiler` | < 4GB for 1M faces |
| Non-manifold reduction | Count before/after | ≥ 90% reduction |
| UV distortion | Angle/area change | < 10% median |
| Vertex count retention | Ratio | Matches face reduction |
| LOD generation time | Wall clock | < 60s for 4 LODs |

### 11.3 Benchmark Comparisons

| System | Type | License |
|--------|------|---------|
| Crunch3D V1 | Ours (baseline) | Open |
| Crunch3D V2 | Ours (target) | Open |
| PyMeshLab plain QEM | Baseline QEM | Open (GPL) |
| Blender Decimate | Standard tool | Open |
| Simplygon | Commercial | Paid |
| InstaLOD | Commercial | Paid |
| Bo et al. 2026 (if available) | Research | Paper |
| Liu et al. 2025 (if available) | Research | Paper |

### 11.4 Expected Performance Targets

| Metric | V1 | V2 Target | Improvement |
|--------|----|-----------|-------------|
| 95th-pct deviation (organic) | ~1.8% | ~0.8% | 2.3× |
| 95th-pct deviation (mechanical) | ~1.5% | ~0.5% | 3× |
| Processing time (500K faces) | ~180s | ~15s | 12× |
| Processing time (1M faces) | ~360s | ~30s | 12× |
| Detail retention (expert eval) | Good | Excellent | — |
| Non-manifold handling | 60% | 95% | 1.6× |
| Memory (500K faces) | ~2GB | ~1GB | 2× |
| Max concurrent optimizations | 1 (blocking) | 100+ (async) | 100× |

---

## 12. Experimental Plan

### Experiment 1: Ablation of Importance Cues

**Hypothesis:** Each cue contributes non-negligibly to overall quality, but learned fusion outperforms weighted sum.

**Method:** On the 300-mesh corpus, run V2 with:
- All cues (baseline)
- Remove curvature
- Remove normal variation
- Remove boundary
- Remove feature density
- Remove spectral redundancy (SRP)
- Learned fusion (DiffusionNet)
- Random importance (control)

**Metrics:** Hausdorff δ, perceptual δ, processing time, face count accuracy

**Expected outcome:** Learned fusion dominates all hand-weighted variants. Among cues, curvature and SRP are most important.

### Experiment 2: Quality Guard Comparison

**Hypothesis:** Hausdorff-based guard with bootstrapped CI provides tighter error bounds than V1's point-sampled NN.

**Method:** On 50 high-poly meshes:
- Run V1 quality guard (700-point NN, 95th pct)
- Run V2 quality guard (Hausdorff, bootstrapped CI)
- Compare measured deviation vs ground truth (brute-force Hausdorff on all vertices)

**Metrics:** Measurement error (measured vs ground truth), compute time, false positive rate (guard flagged but ground truth OK), false negative rate

### Experiment 3: Learned vs Hand-Weighted Importance

**Hypothesis:** Learned importance from DiffusionNet preserves 50+% more detail at 90% reduction than hand-weighted cues.

**Method:** Train on 80% of dataset (artist-annotated importance), test on 20%. Compare:
- V1 weighted sum (fixed cues)
- V2 weighted sum (all enhancements)
- V2 learned (DiffusionNet, 3 layers)
- V2 learned (DiffusionNet, 6 layers)

**Metrics:** MSE against ground-truth importance, quality retention at 50%/75%/90% reduction

### Experiment 4: Parallel Speedup Scaling

**Hypothesis:** Multi-component decimation scales near-linearly with core count.

**Method:** On 20 multi-component meshes (5–20 components each), measure wall-clock time with:
- 1 worker (serial, V2)
- 2 workers parallel
- 4 workers parallel
- 8 workers parallel
- V1 serial (baseline)

**Metrics:** Speedup vs V1, speedup vs 1-worker V2, overhead of parallel coordination

### Experiment 5: Perceptual Metric Validation

**Hypothesis:** CSF-weighted deviation correlates better with human judgment than raw geometric deviation.

**Method:** 20 expert evaluators rate 50 meshes optimized to 5 different quality levels (1000 rating sessions). Compare:
- V1 geometric δ vs rating correlation
- V2 perceptual δ vs rating correlation
- V2 Hausdorff δ vs rating correlation

**Metrics:** Spearman rank correlation, Pearson R², inter-rater agreement (Krippendorff's α)

### Experiment 6: Non-Manifold Robustness

**Hypothesis:** V2's hybrid approach (split + local repair) handles 95%+ of Thingi10K non-manifold cases without failure.

**Method:** Test on Liu et al.'s Thingi10K subset (documented non-manifold rates). Compare:
- V1 (split-only)
- V2 hybrid
- Liu et al. simplicial (if available)

**Metrics:** Success rate (no crash), output manifoldness, quality at target face count

---

## 13. Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| PyMeshLab buffer access not available | High | High | Fallback: C extension or compile custom PyMeshLab |
| Learning model overfits to training data | Medium | High | Cross-validation, data augmentation, diverse corpus |
| Async queue adds latency for small meshes | Medium | Low | Fast-path for <50K face meshes (sync bypass) |
| PostgreSQL becomes bottleneck at scale | Low | Medium | Read replicas, Redis caching layer |
| Hausdorff distance is expensive for large meshes | Medium | Low | GPU-accelerated KD-tree, progressive sampling |
| Texture re-parameterization fails on extreme UV distortion | Low | Medium | Fallback: skip re-parameterization, keep original UV |
| Cross-platform CSF calibration unreliable | Medium | Low | Make CSF weight configurable; default to geometric |
| On-device (ONNX) inference too heavy for CPU | Medium | Medium | Fallback to hand-weighted cues; GPU optional |

---

## 14. Tradeoffs

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| Importance injection | Direct buffer (fragile API) | PLY hack (works but slow) | **Direct buffer** | The PLY hack is the #1 technical debt |
| Non-manifold handling | Per-component split (simple) | Simplicial 2-complex (rigorous) | **Hybrid** | Rigor of Liu + simplicity of split |
| Async queue | Celery (heavy but proven) | RQ (lightweight, fewer features) | **Celery** | Production-grade, flower monitoring, chords |
| Storage | PostgreSQL | SQLite | **PostgreSQL** | Concurrent access, migration-friendly |
| Task format | Synchronous request-response | Immediate-return with polling | **Immediate-return + WS** | Non-blocking + real-time progress |
| Learned model | PyTorch (training + inference) | ONNX (inference only) | **Both** | PyTorch for training, ONNX for inference |
| Texture awareness | SLIM re-parameterization | Simple UV copy | **SLIM** | Quality matters, SLIM library exists |
| Perceptual metric | Full HDR-VDP | Simplified CSF | **CSF** | Computationally practical, still principled |

---

## 15. Final Recommendation

**Crunch3D V2 should be built as described above, in order of priority:**

1. **P0: Decimation engine rewrite** — Direct buffer access, no file round-trips, vectorized all-python loops
2. **P0: Async task queue** — Non-blocking server with Celery + Redis
3. **P0: Persistent storage** — PostgreSQL for production reliability
4. **P1: Hausdorff quality guard** — Proper surface deviation measurement with bootstrapped confidence
5. **P1: Spectral cues + multi-resolution curvature** — Mathematically rigorous importance
6. **P1: Scene graph preservation + multi-format export** — Production-ready output
7. **P2: Learned importance via DiffusionNet** — Only after the above is solid
8. **P2: Texture budget reallocation** — When UV analysis is needed
9. **P3: Perceptual CSF metric** — When expert validation data is available

The key insight from V1 is: **infrastructure overhead dominates computation time.** The top priority is eliminating the PLY/OBJ round-trips and Python loops — not adding more sophisticated mathematics. Once the engine is clean, the mathematical enhancements stack naturally on top.

### V2 Mathematical Novelty Summary

The following formulations are, to our knowledge, not present in any existing open-source mesh decimation system:

1. **Direct buffer quality injection** for PyMeshLab QEM (enables real importance-weighting without hacks)
2. **Multi-resolution curvature with automatic scale selection** per vertex (not fixed-radius)
3. **Spectral redundancy pruning** — collapse order guided by Laplacian eigenvector variation
4. **CSF-weighted perceptual deviation metric** for quality guard (bridging vision science and mesh decimation)
5. **Hybrid non-manifold handling** — per-component split + local manifold repair + importance-aware collapse ordering
6. **Heat-method geodesic protection field** — artist-controlled importance override via single sparse solve
7. **Vectorized Laplacian smoothing** using sparse cotangent Laplacian (not iterative Python loops)
8. **DiffusionNet-based learned importance** specifically trained for decimation (not classification/segmentation)

---

*End of plan.md — Crunch3D V2 Design Document*
