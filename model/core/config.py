"""
Centralized configuration for Crunch3D / OptiMesh.

All hyperparameters from the research paper (Topology-Gated QEM)
live here, plus feature flags that control which pipeline stages
are active.

Set ENABLE_* flags to True once the corresponding dependency
(gudhi, torch, etc.) is installed and the module is ready.
"""

from __future__ import annotations

# ── Feature flags ───────────────────────────────────────────────────────────
# These are OFF by default so the existing V1 pipeline works unchanged.

ENABLE_PERSISTENCE_GATE: bool = True
"""Enable persistent homology gate (§IV-A).  Requires `gudhi`."""

ENABLE_GNN_IMPORTANCE: bool = True
"""Enable GNN edge importance predictor (§IV-B).  Requires `torch`, `torch-geometric`."""

ENABLE_TEXTURE_REALLOCATION: bool = True
"""Enable persistence-gated texture reallocation (§IV-C)."""


# ── Paper hyperparameters ───────────────────────────────────────────────────

TAU_TOPO: float = 0.05
"""Persistence gate threshold (Eq. 1):
   Admissible(σ) ⟺ pers(σ) ≤ τ_topo
   Lower → more conservative (protects more topological features).
"""

KAPPA: float = 1.0
"""GNN cost modulation strength (Eq. 2):
   Cost(σ) = Cost_QEM(σ) · (1 + κ · ŷ_σ)
   Higher → GNN has more influence over collapse ordering.
"""

GAMMA: float = 1.5
"""Texel density exponent (Eq. 3):
   texel_density(f) ∝ ŷ^γ · 𝟙[pers(f) > τ_topo]
   Higher → concentrates texels more aggressively onto important faces.
"""

# ── Existing configuration (migrated) ─────────────────────────────────────

MAX_FILE_SIZE_MB: int = 50
"""Maximum upload file size in megabytes."""

BACKEND_PORT: int = 8000
"""Default port for the uvicorn server."""
