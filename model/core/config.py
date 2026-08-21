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

ENABLE_EDGE_FEATURES: bool = True
"""Enable the 19-cue edge-feature importance descriptor.  Requires `numpy`
and is the only edge-importance source when `ENABLE_GNN_IMPORTANCE` is off.
When disabled, edge protection falls back to GNN / QEM only."""


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

KAPPA_EDGE: float = 0.75
"""Edge-feature cost modulation strength (edge-protection analogue of Eq. 2):

   Cost(σ) = Cost_QEM(σ) · (1 + κ_edge · ī_edge)

where ī_edge is the fused 19-cue edge importance in [0, 1].  Higher values
protect sharp creases, silhouettes, UV seams and rig-deformed regions more
aggressively during decimation."""

GAMMA: float = 1.5
"""Texel density exponent (Eq. 3):
   texel_density(f) ∝ ŷ^γ · 𝟙[pers(f) > τ_topo]
   Higher → concentrates texels more aggressively onto important faces.
"""

# ── Native simplifier (Action_Plan §37–44) ─────────────────────────────────

SIMPLIFIER_METHOD: str = "pymeshlab"
"""Default decimation backend.  ``"pymeshlab"`` keeps the production path;
``"crunch3d"`` routes through the native staged half-edge simplifier."""

COST_MODE: str = "multiplicative"
"""Eq. 2 combination form.  ``"multiplicative"``: Cost = QEM·(1 + κ·I).
``"additive"``: Cost = QEM_norm + λ·I (numerically stable alternative, §38)."""

COST_LAMBDA: float = 1.0
"""λ for the additive cost form."""

IMPORTANCE_AGGREGATE: str = "max"
"""How per-vertex importance becomes per-edge importance: ``max`` follows
crunch3d-v2 Eq. 5 (I(e) = max(I(v_i), I(v_j))); ``mean`` is the softer variant."""

STAGES: int = 4
"""Staged-inference tranches (§40).  1 = one-shot prediction (control arm)."""

FLIP_THRESHOLD: float = 0.2
"""Reject a collapse when any surviving face normal turns by more than
acos(0.2) ≈ 78°."""

MIN_AREA_RATIO: float = 1e-4
"""Reject a collapse producing a face smaller than this fraction of the mean
original face area."""

MAX_ASPECT_RATIO: float = 50.0
"""Reject a collapse producing a sliver with max_edge² / (2·area) above this."""

BOUNDARY_QUADRIC_WEIGHT: float = 1000.0
"""Weight of the virtual boundary plane added to the quadrics (§8.6)."""

# ── Graph / model (Action_Plan §13–16, §127) ───────────────────────────────

LAP_PE_DIM: int = 16
"""Laplacian positional-encoding dimensions."""

TWO_HOP_WEIGHT: float = 0.5
"""λ_2hop in the dual-path fusion h = h_1hop + λ·h_2hop (§15)."""

TWO_HOP_MAX_DEGREE: int = 32
"""Per-node cap on 2-hop neighbours, to bound graph memory (§114)."""

CONV_TYPE: str = "gcn"
"""Vertex-encoder convolution: gcn | sage | gatv2 | mlp (§63 ablation)."""

HIDDEN_DIM: int = 64
GNN_LAYERS: int = 3
DROPOUT: float = 0.15

# ── Losses (§21, §127) ─────────────────────────────────────────────────────

LOSS_REGRESSION: float = 1.0
LOSS_RANKING: float = 0.25
LOSS_SAFETY: float = 1.0
RANK_MARGIN: float = 0.05
SAFETY_FLOOR: float = 0.7
"""Minimum importance the model must predict on hard-constraint edges (§20 C)."""

# ── Oracle label weights (§35) ─────────────────────────────────────────────

ORACLE_WEIGHTS: dict[str, float] = {
    "qem": 0.35,
    "normal": 0.20,
    "curvature": 0.15,
    "topology": 0.15,
    "uv": 0.05,
    "material": 0.05,
    "skin": 0.05,
}
"""α/β/γ/δ of §35, extended with the asset-aware penalties of §19."""

ORACLE_CANDIDATES: tuple[int, int, int] = (32, 64, 128)
"""K candidate edges per mesh state, by size bucket (§34)."""

STAGE_RATIOS: tuple[float, ...] = (1.0, 0.75, 0.5, 0.25)
"""Simplification stages sampled per source mesh for the dataset (§29–30)."""

SEED: int = 42

# ── Existing configuration (migrated) ─────────────────────────────────────


MAX_FILE_SIZE_MB: int = 50
"""Maximum upload file size in megabytes."""

BACKEND_PORT: int = 8000
"""Default port for the uvicorn server."""
