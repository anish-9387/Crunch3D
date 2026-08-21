# Crunch3D 

> **Goal:** turn Crunch3D from a promising mesh-optimization prototype into a technically rigorous, measurable, reproducible system that learns which mesh collapses are safe and useful, then uses those learned priorities to guide a topology-aware QEM simplifier.

---

## 0. Executive Direction

The strongest version of Crunch3D should **not** be:

```text
19 edge features
        ↓
generic GNN
        ↓
importance
        ↓
QEM
```

The better architecture is:

```text
                         INPUT ASSET
                    OBJ / FBX / glTF / GLB
                             │
                             ▼
                    Mesh normalization
                             │
                             ▼
                    Half-edge structure
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
       Vertex features                Edge features
              │                             │
              ▼                             │
         Mesh graph ───────────────────────┘
              │
       ┌──────┴──────┐
       │             │
       ▼             ▼
    1-hop GNN     2-hop / wider
       │             │
       └──────┬──────┘
              ▼
      Vertex embeddings
              │
              ▼
      Edge decoder for (u,v)
              │
      h_u || h_v || |h_u-h_v|
              || edge features
              ▼
       Edge importance [0,1]
              │
              ▼
     AI-modulated QEM cost
              │
              ▼
         Min-heap / PQ
              │
              ▼
        Safe edge collapse
              │
              ▼
      Local topology repair
              │
              ▼
        Recompute local state
              │
              ▼
      next simplification stage
              │
              └──────────────→ GNN
```

### The core principle

**The GNN should learn _which collapses are undesirable_, while QEM remains responsible for geometric placement/error minimization.**

Do not let the neural network replace geometry. Let it **prioritize the geometry-aware optimizer**.

That gives Crunch3D a much more defensible ML story:

> **A learned structural importance estimator guides classical QEM rather than replacing it.**

This is also the key idea to preserve from the 2026 GNN-guided QEM paper.

---

# 1. What You Are Building

## 1.1 Final Crunch3D objective

Given a high-poly triangular mesh:

```text
M_original
```

and a requested target:

```text
target_faces = N
```

produce:

```text
M_simplified
```

while maximizing:

- geometric fidelity
- normal consistency
- feature preservation
- texture/UV consistency
- material consistency
- animation safety
- topology integrity
- runtime efficiency

subject to:

```text
faces(M_simplified) <= target_faces
```

---

# 2. The Three Systems You Must Build

Crunch3D should be developed as three connected systems.

## System A — Deterministic Geometry Engine

This is the non-ML foundation.

```text
Mesh Loader
    ↓
Mesh Validator
    ↓
Half-edge Mesh
    ↓
Curvature / normals / QEM
    ↓
Edge-collapse engine
    ↓
Topology repair
    ↓
Export
```

This system must work **without a neural network**.

You need this because:

1. it becomes your baseline,
2. it creates training data,
3. it gives you an interpretable fallback,
4. it lets you measure whether ML actually improves anything.

---

## System B — Feature Extraction Engine

This converts the mesh into:

```text
Vertex Feature Matrix
Edge Feature Matrix
Graph Connectivity
```

The extractor must be modular.

Suggested interface:

```python
features = extractor.extract(mesh)

features.vertex
features.edge
features.graph
features.metadata
```

Do **not** hard-code 19 features into one giant function.

Use:

```text
features/
├── geometry.py
├── topology.py
├── material.py
├── texture.py
├── animation.py
├── visibility.py
└── registry.py
```

Each feature should have:

```python
class FeatureExtractor:
    name: str
    requires: list[str]
    output_dim: int

    def compute(self, mesh):
        ...
```

This makes the pipeline extensible.

---

## System C — Learned Importance Engine

This is the ML component:

```text
graph
+ vertex features
+ edge features
        ↓
GNN
        ↓
vertex embeddings
        ↓
edge decoder
        ↓
importance score
```

The model should predict:

```text
importance(edge) ∈ [0,1]
```

where:

```text
1.0 = strongly preserve
0.0 = safe simplification candidate
```

---

# 3. Important Architecture Correction

The research material you provided already identifies the most important correction:

**vertices should be GNN nodes and mesh edges should be graph connections.**

The 2026 GNN-QEM paper describes this representation, with GNN processing producing vertex embeddings before edge-level importance prediction. The edge decoder combines endpoint embeddings, their absolute difference, and geometric edge features. fileciteturn0file0L42-L64 fileciteturn0file0L200-L235

So Crunch3D should use:

```text
Vertex = graph node
Mesh edge = graph edge
```

not:

```text
Edge feature matrix → generic MLP
```

as the entire model.

---

# 4. Input Formats

Supported inputs should be:

- OBJ
- FBX
- glTF
- GLB

Recommended internal representation:

```text
Mesh
├── vertices
├── faces
├── edges
├── half_edges
├── vertex_normals
├── face_normals
├── uv
├── materials
├── vertex_colors
├── skin_weights
├── bones
└── metadata
```

Normalize every asset into a common internal format before feature extraction.

---

# 5. Mesh Preprocessing

Before ML:

## 5.1 Triangulate

The current architecture should operate on triangular meshes.

```text
quad / ngon
    ↓
triangulation
```

Keep a mapping to original face IDs.

---

## 5.2 Remove / detect invalid geometry

Detect:

- NaN vertices
- duplicate vertices
- zero-area triangles
- duplicate faces
- inconsistent winding
- isolated vertices
- non-manifold edges
- loose geometry
- disconnected components

Do not blindly delete everything.

Store a validation report:

```json
{
  "vertices": 124832,
  "faces": 248910,
  "boundary_edges": 123,
  "non_manifold_edges": 4,
  "degenerate_faces": 19,
  "components": 3
}
```

---

## 5.3 Normalize scale for ML

Use a scale-normalized copy for feature computation.

Example:

```text
centroid → origin
bounding box diagonal → 1
```

Store the original transform separately.

This prevents the GNN from learning:

```text
"large object = important"
```

instead of actual structure.

---

# 6. Half-Edge Structure

Use a half-edge representation because the simplifier repeatedly needs local adjacency.

Recommended conceptual objects:

```text
Vertex
HalfEdge
Edge
Face
```

Each half-edge should provide:

```text
origin
destination
next
prev
twin
face
edge
```

This gives O(1)-style local navigation for:

- one-ring extraction
- adjacent face lookup
- edge collapse
- topology validation
- curvature calculations
- local graph updates

---

# 7. Feature Extraction Plan

Do not enable every feature immediately.

Use three tiers.

---

# 8. Tier A — Core Features

These should be computed for every triangular mesh.

## 8.1 Edge length

```text
L(e) = ||v1 - v2||
```

Normalize:

```text
L_norm = edge_length / mesh_bbox_diagonal
```

Why:

- long edges are often candidates for reduction,
- short dense edges often carry detail,
- normalized length prevents scale leakage.

---

## 8.2 Dihedral angle

For adjacent face normals:

```text
theta = acos(clamp(n1 · n2, -1, 1))
```

This is a very important feature.

Interpretation:

```text
small angle  → similar normals
large change → crease / sharp feature
```

Use a numerically stable implementation.

---

## 8.3 Normal difference

```text
normal_diff = 1 - dot(n1, n2)
```

This is closely related to sharpness.

Do not assume both are redundant until an ablation confirms it.

---

## 8.4 Mean curvature

```text
H = (k1 + k2) / 2
```

Use a robust discrete curvature estimator.

Store:

```text
signed_mean_curvature
absolute_mean_curvature
```

if implementation permits.

For ML, use normalized values.

---

## 8.5 Gaussian curvature

```text
K = k1 * k2
```

Useful for distinguishing:

```text
flat
elliptic
hyperbolic
```

regions.

For stability:

```text
log_abs_K
sign_K
```

can be useful as additional normalized inputs.

---

## 8.6 Boundary flag

```text
boundary = 1
```

if the edge has only one incident face.

Boundary edges should receive a strong protection prior.

---

## 8.7 Surface-area contribution

For adjacent faces:

```text
area_contribution =
    area(face_a) + area(face_b)
```

Also consider normalized:

```text
area_fraction =
    local_area / total_mesh_area
```

---

# 9. Tier B — Asset-Aware Features

Compute these when the source asset contains them.

## 9.1 UV seam

For an edge, compare UV coordinates across its two incident faces.

Do not compare only the 3D vertex IDs.

The same geometric vertex can correspond to multiple UV corners.

Feature:

```text
uv_seam ∈ {0,1}
```

A seam should strongly increase preservation priority.

---

## 9.2 Material boundary

Each face gets:

```text
material_id
```

For edge e:

```text
material_boundary =
    material(face_a) != material(face_b)
```

Use this to prevent collapsing across material transitions.

---

## 9.3 Vertex color difference

Example:

```text
color_delta =
    ||color(v1) - color(v2)||_2
```

Normalize to:

```text
[0,1]
```

---

## 9.4 Bone-weight difference

For skinned meshes:

```text
W(v) = [w1, w2, ..., wk]
```

Use aligned bone-index vectors.

Feature:

```text
bone_delta = ||W(v1) - W(v2)||_2
```

Important:

You must handle sparse bone influences and differing bone sets correctly.

A character's joint regions should receive stronger preservation.

---

## 9.5 Sharp-edge flag

If imported from Blender or another DCC:

```text
sharp_edge ∈ {0,1}
```

Use the source annotation when available.

---

# 10. Tier C — Expensive Features

Do not compute these for every mesh by default.

## 10.1 Texture gradient

Project the UV edge into texture space.

Sample image gradients:

```text
Sobel
Scharr
Laplacian
```

Compute local texture variation.

High gradient:

```text
eyes
logos
text
fine decals
```

Low gradient:

```text
flat walls
smooth color regions
```

This is especially useful for production assets.

---

## 10.2 Ambient occlusion

Compute or bake AO.

Then estimate:

```text
AO_edge =
    average AO around edge neighborhood
```

High AO regions often correspond to:

- cavities
- creases
- contact regions

Do not make AO an unconditional "preserve" rule; validate this empirically.

---

## 10.3 Visibility

For a camera:

```text
camera
  ↓
ray
  ↓
mesh
```

Estimate whether the edge is:

- visible
- occluded
- frequently visible
- rarely visible

Useful libraries:

- Intel Embree
- OptiX
- Blender ray casting
- Open3D

For training, store visibility statistics generated from multiple sampled cameras rather than relying on one arbitrary camera.

---

## 10.4 Screen-space importance

Project the edge into image space.

Example:

```text
screen_length_px =
    ||project(v1) - project(v2)||
```

Use:

```text
screen_length
depth
distance
visibility
```

to estimate view-dependent importance.

This should be optional because it is camera-dependent.

---

## 10.5 Silhouette score

For a camera, compare face orientations against the camera direction.

An edge between:

```text
front-facing face
```

and

```text
back-facing face
```

is a silhouette candidate.

Silhouette destruction is highly visible, so this should be strongly weighted in view-dependent simplification.

---

## 10.6 Animation influence

For animated assets:

```text
vertex_displacement(v)
```

over sampled frames.

Compute:

```text
mean displacement
max displacement
variance
```

and compare endpoints.

This helps preserve deformation-critical regions.

---

# 11. Feature Vector Recommendation

Do **not** start with 19+ features.

Start with:

## Vertex features

```text
[x, y, z]
[nx, ny, nz]
normalized_valence
boundary_flag
vertex_mean_curvature
vertex_gaussian_curvature
Laplacian positional encoding (8–16 dims)
```

## Edge features

```text
normalized_edge_length
dihedral_angle
normal_difference
curvature_difference
boundary_flag
surface_area_contribution
```

Then add:

```text
uv_seam
material_boundary
sharp_edge
vertex_color_difference
bone_weight_difference
```

Then optional:

```text
texture_gradient
AO
visibility
screen_space_importance
silhouette_score
animation_influence
```

This is much safer than immediately giving the network every feature you can invent.

---

# 12. Why Compact Features First?

Because otherwise you will not know:

```text
which feature helped,
which feature hurt,
which feature leaked information,
which feature is redundant,
which feature is expensive,
```

A strong ML system is not one with the largest feature vector.

A strong ML system is one where:

```text
feature → hypothesis → experiment → measurement
```

is traceable.

---

# 13. Graph Construction

Graph:

```text
G = (V,E)
```

where:

```text
V = mesh vertices
E = mesh edges
```

Add local relationships.

At minimum:

```text
1-hop adjacency
```

Recommended:

```text
1-hop graph
+
2-hop graph
```

The 2026 paper uses multi-scale neighborhood information and a dual-path GNN design. Its reported implementation uses GCNConv layers with hidden dimension 64, LayerNorm and dropout 0.15. citeturn481706search2turn481706search0

---

# 14. Vertex Encoder

Recommended first model:

```text
Input
  ↓
Linear projection
  ↓
GCNConv
  ↓
LayerNorm
  ↓
ReLU
  ↓
Dropout
  ↓
GCNConv
  ↓
LayerNorm
  ↓
ReLU
  ↓
GCNConv
  ↓
Vertex embedding
```

Suggested starting values:

```text
GNN layers = 3
hidden dim = 64
dropout = 0.15
Laplacian PE = 16
optimizer = Adam
```

These are close to the reported 2026 configuration and therefore make a useful reproduction baseline. citeturn481706search0

---

# 15. Multi-Scale Branch

Use:

```text
                vertex features
                      │
             ┌────────┴────────┐
             ▼                 ▼
         1-hop GCN         2-hop GCN
             │                 │
             └────────┬────────┘
                      ▼
                    fusion
                      │
                      ▼
              vertex embedding
```

Conceptually:

```python
h = h_1hop + lambda_2hop * h_2hop
```

A starting value:

```text
lambda_2hop = 0.5
```

matches the reported research configuration. citeturn481706search0

---

# 16. Edge Decoder

For every edge:

```text
e = (u,v)
```

construct:

```python
edge_input = concat(
    h_u,
    h_v,
    abs(h_u - h_v),
    edge_features
)
```

Then:

```text
edge_input
     ↓
Linear
     ↓
ReLU
     ↓
Linear
     ↓
Sigmoid
     ↓
importance
```

This endpoint + difference + edge-feature late-fusion approach is one of the most useful ideas to preserve from the 2026 architecture. fileciteturn0file0L200-L235

---

# 17. Important ML Design Decision

Do not make the GNN predict:

```text
"collapse this edge"
```

as a hard binary classification problem.

Predict:

```text
importance / desirability / expected preservation cost
```

as a continuous value.

Example:

```text
edge A → 0.01
edge B → 0.24
edge C → 0.87
edge D → 0.96
```

Then use:

```text
QEM + learned importance
```

to decide which candidate should collapse.

This produces a smoother optimization problem.

---

# 18. The Most Important Missing Piece: Labels

The biggest ML challenge is not the GNN.

It is:

> **Where do the training targets come from?**

You need a defensible label-generation strategy.

---

# 19. Recommended Label Strategy — Collapse Utility

Instead of manually labeling edges, generate labels offline.

For every valid candidate edge:

```text
simulate collapse
      ↓
measure resulting local damage
```

Compute a multi-objective collapse cost.

Example:

```text
oracle_cost =
    w_qem      * normalized_qem_error
  + w_normal   * normal_change
  + w_feature  * feature_breakage
  + w_topology * topology_penalty
  + w_uv       * uv_seam_penalty
  + w_material * material_penalty
  + w_skin     * skinning_penalty
```

Then normalize candidate costs within a local neighborhood.

Convert to importance:

```text
importance = 1 - normalized_oracle_cost
```

or use the raw normalized score directly as a regression target.

---

# 20. Better Than a Single Oracle Label

Create multiple supervision signals.

## Signal A — Regression

Predict:

```text
oracle_importance
```

Loss:

```text
Huber / SmoothL1
```

---

## Signal B — Pairwise ranking

For edges:

```text
e1
e2
```

if:

```text
importance(e1) > importance(e2)
```

train:

```text
score(e1) > score(e2)
```

Use a pairwise ranking loss.

This is extremely appropriate because the simplifier primarily needs to know:

```text
which edge should go first?
```

not necessarily the exact numerical score.

---

## Signal C — Hard safety constraints

Some edges should not be aggressively collapsed:

```text
boundary
UV seam
material seam
sharp feature
skin-weight discontinuity
silhouette
```

Add a constrained penalty so the model does not learn to destroy them.

---

# 21. Recommended Loss

Start with:

```text
L =
    λ_reg   L_regression
  + λ_rank  L_pairwise
  + λ_safe  L_safety
```

Then add local smoothness only after the basic system is stable.

The 2026 paper uses a richer combination including structural contrastive, geometric hinge, pairwise ranking and local smoothness terms. citeturn481706search0

Do not copy all four losses blindly.

First prove that:

```text
regression + ranking + safety
```

works.

Then ablate additional losses.

---

# 22. Dataset Strategy

## Do NOT download and train on all of Objaverse.

That is unnecessary for the first serious version.

Objaverse 1.0 contains about 800K objects, and Objaverse-XL contains 10M+ objects. The official documentation provides a Python API and metadata/download workflows. citeturn927351search10

That is far beyond what you need for laptop-scale experimentation.

---

# 23. Dataset Philosophy

You want:

```text
clean data
+
diverse data
+
controlled supervision
+
held-out categories
+
held-out objects
```

not:

```text
millions of random meshes
```

A few hundred high-quality training assets with generated simplification trajectories can be more useful than tens of thousands of poorly controlled samples.

---

# 24. Dataset Mix

Recommended starting corpus:

## Dataset A — ShapeNetCore

Use as the clean geometry base.

ShapeNetCore contains approximately 51,300 models across 55 common object categories and provides manually verified category/alignment annotations. citeturn927351search11

Use it for:

- clean training examples
- controlled experiments
- category-balanced splits
- geometry-only features
- repeatable benchmarks

Do not download everything initially.

Start with a curated subset.

Suggested:

```text
300–800 models
```

distributed across categories.

---

# 25. Dataset B — Objaverse

Use as the diversity/generalization set.

Official Objaverse information:

https://objaverse.allenai.org/docs/intro/

Objaverse is much more diverse than ShapeNetCore and contains annotated 3D objects; Objaverse 1.0 is listed as ~800K objects and Objaverse-XL as 10M+ objects. citeturn927351search10

Use a filtered subset.

Suggested:

```text
300–1000 assets
```

with diversity across:

- organic
- furniture
- vehicles
- tools
- characters
- household objects
- architectural objects
- hard-surface props

Do not select random assets blindly.

Filter for:

```text
triangularizable
readable geometry
reasonable file size
valid normals
no catastrophic corruption
```

---

# 26. Dataset C — Human / Deformable Meshes

For characters and animation-aware features, add a dedicated human/deformable collection.

Useful references include TOSCA, FAUST, SCAPE and related human-shape datasets. A SHREC dataset index provides links and mesh characteristics for TOSCA, FAUST, SCAPE, SMPL and other human datasets. citeturn562969search8

Use this split primarily for:

```text
curvature
joints
deformation
skin weights
animation sensitivity
```

Do not mix this data into the general corpus without tracking its source category.

---

# 27. Why TOSCA Matters

The 2026 GNN-QEM work uses TOSCA in its training/evaluation setup. fileciteturn0file0L429-L463

TOSCA is therefore useful for:

- reproducing the research setup,
- checking whether your implementation behaves on deformable human-like surfaces,
- sanity-checking curvature and structural features.

It should **not** become your only benchmark.

---

# 28. Train/Validation/Test Split

This is extremely important.

Do not randomly split individual generated simplification stages from the same source object.

That causes leakage.

Correct split:

```text
original object
     ↓
all simplification trajectories
     ↓
same split
```

Example:

```text
Train:
70%

Validation:
15%

Test:
15%
```

But ideally also use:

```text
category-held-out test
```

For example:

```text
train:
chairs, tables, cars, lamps

test:
tools, instruments, characters
```

This measures generalization.

---

# 29. Dataset Size That Is Realistic on a Laptop

Start with:

```text
500–1,000 total meshes
```

not millions.

For each mesh generate:

```text
3–5 target reduction ratios
```

For example:

```text
10%
25%
50%
75%
```

Then generate candidate/importance information offline.

The number of training graphs can therefore become large even with a modest number of original assets.

---

# 30. Generate Many Examples From One Mesh

Instead of needing 100,000 unique meshes:

```text
1 mesh
 ↓
100% original
 ↓
95%
 ↓
90%
 ↓
80%
 ↓
70%
 ↓
50%
 ↓
...
```

Each stage produces training candidates.

This is much more compute-efficient.

---

# 31. But Avoid Data Leakage

Do not let:

```text
chair_A at 90%
chair_A at 80%
```

appear in train and test separately.

All versions of:

```text
chair_A
```

must stay in exactly one split.

---

# 32. Dataset Preprocessing Pipeline

Build:

```text
raw/
├── shapenet/
├── objaverse/
└── human/

processed/
├── train/
├── val/
└── test/
```

For every mesh generate one cached graph package:

```text
sample_000123.pt
```

containing:

```python
{
    "pos": ...,
    "normals": ...,
    "vertex_features": ...,
    "edge_index": ...,
    "edge_features": ...,
    "labels": ...,
    "face_count": ...,
    "metadata": ...
}
```

This is critical.

The training loop should NOT repeatedly recompute:

```text
curvature
UV parsing
graph construction
```

every epoch.

---

# 33. Cache Everything Expensive

Cache:

- normals
- curvature
- graph connectivity
- Laplacian positional encodings
- edge features
- target labels
- collapse metadata

Training should become:

```text
load .pt
→ GNN
→ loss
→ backward
```

rather than:

```text
load mesh
→ rebuild half-edge
→ compute curvature
→ compute graph
→ compute Laplacian
→ train
```

---

# 34. How to Create Training Labels Efficiently

Do not run an expensive full simplification trajectory for every edge.

Use a sampled candidate strategy.

For each mesh state:

```text
select K valid candidate edges
```

Then compute simulated collapse quality only for those candidates.

Example:

```text
K = 32 / 64 / 128
```

depending on mesh size.

Store:

```text
edge_id
oracle_score
```

This creates a manageable offline labeling pipeline.

---

# 35. Better Oracle: Multi-Objective Collapse Damage

For a candidate collapse:

```text
e=(u,v)
```

simulate:

```text
u,v → new vertex
```

Then locally measure:

```text
ΔQEM
Δnormal
Δcurvature
Δtopology
ΔUV
Δmaterial
Δskin
```

Final oracle:

```text
oracle =
    α Δgeometry
  + β Δnormal
  + γ Δfeature
  + δ Δtopology
```

This makes the ML target directly tied to the actual product objective.

---

# 36. What the Model Should Actually Learn

The learned task is:

> **Given the current local/global mesh context, predict the relative structural danger of collapsing each valid edge.**

Not:

> "Reconstruct the simplified mesh."

Not:

> "Generate a new mesh."

Not:

> "Replace QEM."

The model is a **collapse-priority estimator**.

---

# 37. QEM Layer

Implement standard QEM first.

QEM is based on iterative vertex-pair/edge contractions and accumulated quadric error matrices. The original Garland–Heckbert work is the canonical reference. citeturn927351search5turn927351search6

Reference:

https://doi.org/10.1145/258734.258849

Reference page:

https://www.cs.cmu.edu/~garland/quadrics/

---

# 38. AI + QEM Cost

Do not replace QEM with:

```text
cost = 1 - importance
```

Instead:

```text
final_cost =
    qem_cost × importance_penalty
```

or a numerically stable additive formulation:

```text
final_cost =
    normalized_qem
    +
    λ × learned_penalty
```

The exact formulation should be tuned experimentally.

The 2026 paper uses learned structural importance to soft-modulate QEM rather than replacing QEM completely. citeturn481706search4

---

# 39. Why Soft Modulation Is Better

Suppose:

```text
Edge A:
QEM = 0.01
Importance = 0.95

Edge B:
QEM = 0.04
Importance = 0.03
```

Pure QEM selects:

```text
Edge A
```

AI alone may select:

```text
Edge B
```

AI + QEM can reason:

```text
Edge A is geometrically cheap
BUT structurally important

Edge B is geometrically slightly worse
BUT structurally redundant
```

This is exactly the behavior you want.

---

# 40. Staged Inference

Do not compute the GNN once and collapse the entire mesh.

Use:

```text
Stage 1
GNN
→ importance
→ several safe collapses
→ rebuild local graph

Stage 2
GNN
→ new importance
→ more collapses
→ rebuild

Stage 3
...
```

The 2026 paper explicitly uses staged inference because topology changes as edges collapse; importance is recomputed for later stages. citeturn481706search4

This should be one of Crunch3D's core design decisions.

---

# 41. Recommended Simplification Loop

```python
while face_count > target_faces:

    if stage_finished:
        graph = rebuild_graph(mesh)
        features = extract_features(mesh)
        importance = gnn(graph, features)

    for edge in valid_candidate_edges:

        qem = compute_qem(edge)

        ai_penalty = importance[edge]

        cost = combine(qem, ai_penalty)

        heap.push(edge, cost)

    edge = heap.pop()

    if not is_valid_collapse(edge):
        continue

    collapse(edge)

    update_local_quadrics()

    update_local_features()

    update_heap()
```

Do not rebuild everything after every single collapse unless necessary.

Use local updates.

---

# 42. Topology Safety Rules

Before a collapse:

```text
check boundary
check manifoldness
check link condition
check degenerate triangles
check face flips
check normal inversion
check material constraints
check UV constraints
check skinning constraints
```

A high-scoring ML model cannot save you from a broken collapse validator.

The validator must be deterministic.

---

# 43. Mesh Quality Constraints

Reject or penalize a collapse if it creates:

- flipped faces
- zero-area faces
- extreme aspect ratios
- non-manifold edges
- unexpected connected-component changes
- UV explosions
- material crossing
- forbidden boundary destruction

This is where the classical geometry system acts as a **hard safety layer** around ML.

---

# 44. Important Safety Hierarchy

Use:

```text
HARD CONSTRAINTS
      ↓
VALID COLLAPSE CANDIDATES
      ↓
QEM + GNN SCORE
      ↓
PRIORITY QUEUE
```

not:

```text
GNN
 ↓
do whatever the model says
```

---

# 45. Baselines You Must Build

Before claiming ML improvement, benchmark against:

## Baseline 1

Random valid edge collapse.

Purpose:

sanity check.

---

## Baseline 2

Pure QEM.

Purpose:

primary classical baseline.

---

## Baseline 3

QEM + handcrafted feature penalty.

Example:

```text
QEM
+
sharpness penalty
+
boundary penalty
+
UV penalty
```

Purpose:

prove ML beats a good heuristic.

---

## Baseline 4

QEM + learned importance.

This is your primary model.

---

## Optional Baseline 5

MeshCNN-style learned edge processing.

Use mainly as a research comparison / conceptual baseline.

---

# 46. MeshCNN — What It Gives Crunch3D

MeshCNN is an edge-centric mesh neural network. It performs convolution and pooling directly on mesh edges and uses edge collapse as its pooling operation. citeturn927351search3

Official project:

https://ranahanocka.github.io/MeshCNN/

GitHub:

https://github.com/ranahanocka/MeshCNN

Wiki:

https://github.com/ranahanocka/MeshCNN/wiki

MeshCNN's core lesson for Crunch3D:

```text
mesh connectivity itself is valuable information
```

Its published implementation uses edge-based geometric inputs and dynamic mesh neighborhoods. citeturn927351search3

Do not blindly transplant its old architecture into Crunch3D.

Use it for:

- mesh learning concepts
- edge neighborhoods
- edge features
- task-driven simplification ideas
- implementation references

---

# 47. MeshCNN Codebase — What to Study

Repository:

https://github.com/ranahanocka/MeshCNN

Important folders:

```text
data/
models/
options/
scripts/
util/
train.py
test.py
```

Study:

```text
data/base_dataset.py
```

because it is useful for understanding:

- dataset organization
- preprocessing conventions
- mesh loading
- training sample structure

The repository also contains scripts for SHREC and human segmentation experiments. citeturn927351search1

---

# 48. ShapeNetCore — What to Use

Official:

https://www.shapenet.org/

ShapeNetCore is particularly useful because it provides cleaner, category-oriented 3D objects and manually verified annotations. The official overview lists about 51,300 unique models across 55 common categories. citeturn927351search11

Use ShapeNetCore for:

```text
controlled experiments
category-balanced training
clean geometry
baseline comparison
```

Do not rely on it alone.

---

# 49. Objaverse — What to Use

Official:

https://objaverse.allenai.org/docs/intro/

Use Objaverse for:

```text
messy real-world diversity
unexpected topology
different object styles
different mesh densities
generalization tests
```

Official docs provide Python API installation and dataset metadata/download workflows. citeturn927351search10

Start with a filtered subset.

Do not download the entire collection.

---

# 50. TOSCA / Human Data — What to Use

Reference index:

https://profs.scienze.univr.it/~marin/shrec19/datasets

Use human/deformable meshes for:

```text
curvature
joint structure
thin features
non-rigid geometry
animation-related experiments
```

The listed collection includes TOSCA, FAUST, SCAPE and SMPL references. citeturn562969search8

---

# 51. 2026 GNN-QEM Paper — Primary Research Reference

Paper:

https://www.mdpi.com/2227-7390/14/10/1610

Preprint:

https://www.preprints.org/manuscript/202604.1809

The paper's main relevance to Crunch3D is the combination:

```text
mesh graph
+
GNN structural importance
+
edge-level decoder
+
soft QEM modulation
+
staged simplification
```

The reported setup includes:

```text
GCNConv
3 GNN layers
hidden dimension 64
LayerNorm
dropout 0.15
Adam
learning rate 1e-3
50 epochs
batch size 1
```

and uses multiple losses including structural contrastive, geometric hinge, pairwise ranking and local smoothness. citeturn481706search0turn562969search2

### Important research hygiene

The preprint version is explicitly marked as **not peer-reviewed** on Preprints.org. Treat it as an important recent reference, not as unquestionable ground truth. citeturn562969search45

For the implementation, reproduce its strong ideas and independently validate them on your own dataset.

---

# 52. The Evaluation Framework

You need more than:

```text
"Looks good."
```

Use quantitative evaluation.

The 2026 paper reports a protocol including:

- percentage of wrong adjacency
- point-wise Chamfer distance
- point-sampled normal error
- Laplacian spectrum error
- simplification time

These measure topology, geometry, normals, global structure and speed. citeturn562969search0

---

# 53. Metric 1 — Compression Ratio

Report:

```text
compression_ratio =
    1 - simplified_faces / original_faces
```

Example:

```text
90% reduction
```

But never report this alone.

---

# 54. Metric 2 — Chamfer Distance

Measure surface deviation between:

```text
original mesh
```

and:

```text
simplified mesh
```

Lower:

```text
better
```

Sample points on both surfaces.

Use the same sampling protocol across methods.

---

# 55. Metric 3 — Normal Error

Compare surface normals at corresponding / sampled surface points.

Lower:

```text
better
```

This is particularly important around:

- curved regions
- sharp features
- silhouettes

---

# 56. Metric 4 — Topology / Wrong Adjacency

Track:

```text
non-manifold edges
boundary changes
connected-component changes
```

The 2026 paper uses percentage of wrong adjacency as a topology metric. citeturn562969search0

Crunch3D should additionally show:

```text
invalid collapses rejected
topology violations created
topology violations repaired
```

---

# 57. Metric 5 — Laplacian Spectrum Error

Use the normalized graph Laplacian.

This captures global/intrinsic structural changes.

The 2026 paper uses the low-frequency Laplacian spectrum as a global structural descriptor. citeturn562969search0

This is especially good for demonstrating:

```text
"the mesh got smaller but the overall shape structure remained similar."
```

---

# 58. Metric 6 — Runtime

Report:

```text
preprocessing_time
feature_time
gnn_inference_time
qem_time
total_time
```

Use:

```text
milliseconds / seconds
```

consistently.

Also report:

```text
triangles per second
```

where useful.

---

# 59. Metric 7 — Feature Preservation

Create explicit metrics for:

```text
sharp edges retained
UV seams retained
material boundaries retained
silhouette retained
high-curvature regions retained
```

Example:

```text
sharp_feature_recall =
    preserved sharp edges /
    original sharp edges
```

This is highly relevant to a production mesh optimizer.

---

# 60. Metric 8 — Visual Evaluation

Create fixed camera views.

For every test asset render:

```text
Original
QEM 90% reduction
Heuristic-QEM 90%
Crunch3D 90%
```

Use exactly the same:

- camera
- lighting
- material
- background
- resolution

This eliminates subjective presentation bias.

---

# 61. Mandatory Ablation Study

This is one of the most important things to do.

Test:

```text
A. QEM only
B. QEM + handcrafted features
C. GNN without edge features
D. GNN + core edge features
E. GNN + asset-aware features
F. GNN + all optional features
G. final model + staged inference
H. final model without staged inference
```

Measure:

```text
Chamfer
normal error
topology
feature recall
runtime
```

This tells you what actually matters.

---

# 62. Feature Ablation

Run:

```text
all features

- curvature
- sharpness
- UV
- material
- color
- skin
- texture
- AO
- visibility
- silhouette
- animation
```

Measure delta.

Then you can honestly say:

```text
"Silhouette preservation improved X while adding only Y ms."
```

rather than merely claiming the feature is useful.

---

# 63. Model Ablation

Compare:

```text
MLP
GCN
GraphSAGE
GATv2
```

Keep everything else fixed.

Start with:

```text
GCN
```

because it is directly supported by the recent GNN-QEM reference.

Then test a stronger attention-based model as a challenger.

Do not choose architecture based on novelty.

Choose it based on:

```text
quality / runtime / robustness
```

---

# 64. Loss Ablation

Compare:

```text
Regression only
Regression + ranking
Regression + ranking + safety
Full loss
```

This answers:

```text
Does each loss actually help?
```

---

# 65. Data Ablation

Train on:

```text
ShapeNet only
Objaverse only
ShapeNet + Objaverse
ShapeNet + Objaverse + human
```

Then test on:

```text
seen categories
unseen categories
unseen data source
```

This is a strong way to measure generalization.

---

# 66. Do Not Leak Simplification Trajectories

Very important.

Suppose:

```text
car_001
```

generates:

```text
90%
80%
70%
60%
50%
```

all derived from one original.

Every version stays in one split.

Otherwise your test score can become artificially high.

---

# 67. Reproducibility

Every experiment should store:

```text
seed
dataset version
feature config
model config
learning rate
epochs
batch size
target ratio
GPU/CPU
git commit
```

Create:

```text
runs/
└── 2026-xx-xx_001/
    ├── config.yaml
    ├── metrics.json
    ├── model.pt
    ├── predictions.pt
    ├── stdout.log
    └── visualizations/
```

This is mandatory for trustworthy ML comparisons.

---

# 68. Experiment Tracking

Use a simple system at first.

Options:

```text
Weights & Biases
MLflow
TensorBoard
plain JSON + CSV
```

The important part is not the tool.

The important part is:

```text
every run is reproducible.
```

---

# 69. Model Checkpoints

Save:

```text
best_val_loss.pt
best_chamfer.pt
best_feature_preservation.pt
```

Do not choose a model only from training loss.

---

# 70. Normalize Features Correctly

For training features:

```text
fit normalization on TRAIN only
```

Then apply the same statistics to:

```text
validation
test
production
```

Never compute normalization statistics from the full dataset before splitting.

---

# 71. Handle Class / Importance Imbalance

You may have many:

```text
low-importance edges
```

and few:

```text
high-importance edges
```

For this reason:

- pairwise ranking is useful,
- hard-example mining is useful,
- stratified sampling of important regions is useful.

Do not rely only on raw MSE against importance labels.

---

# 72. Hard-Negative Mining

During training:

1. find edges the model ranks incorrectly,
2. pair them with nearby correct edges,
3. train strongly on those pairs.

Example:

```text
predicted:
cheek > eye

ground truth:
eye > cheek
```

This pair is highly informative.

---

# 73. Curriculum Training

Start with:

```text
easy clean meshes
```

then introduce:

```text
messy meshes
non-manifold-ish inputs
dense topology
multiple disconnected components
textures
characters
```

Suggested schedule:

```text
Phase 1:
clean geometry

Phase 2:
mixed geometry

Phase 3:
asset-aware features

Phase 4:
messy real-world assets
```

---

# 74. Data Augmentation

Safe augmentations:

- rotation
- translation
- uniform scaling
- vertex ordering permutations
- graph ordering permutations

Be careful with:

```text
non-uniform scaling
```

because it changes actual geometry and curvature.

For texture/UV experiments, do not randomly destroy the semantics of UV seams.

---

# 75. Rotational Robustness

Your model should not learn:

```text
x-axis = special
```

Randomly rotate training meshes.

Because mesh simplification should be invariant to:

```text
translation
rotation
uniform scale
```

This should also be included in an invariance test.

---

# 76. Generalization Test

Take an unseen mesh.

Rotate it:

```text
0°
90°
180°
random
```

Scale it:

```text
0.1×
1×
10×
```

Expected:

```text
same structural decisions
```

after appropriate normalization.

---

# 77. Feature Importance Analysis

Once your model works, analyze:

```text
which features matter?
```

Use:

- permutation importance
- feature masking
- integrated gradients where appropriate
- SHAP on the edge decoder if feasible

Do not automatically claim SHAP is valid for the complete graph process.

Use it selectively.

---

# 78. Explainability Output

For each collapsed edge, store:

```json
{
  "edge": [124, 128],
  "qem_cost": 0.011,
  "predicted_importance": 0.07,
  "final_cost": 0.013,
  "dihedral": 0.12,
  "curvature": 0.03,
  "uv_seam": 0,
  "material_boundary": 0,
  "reason": "low structural importance"
}
```

This is excellent for debugging and visualization.

---

# 79. Build an Edge Decision Viewer

This should become part of Crunch3D.

Render the mesh with edge colors:

```text
blue → low importance
yellow → medium
red → high importance
```

Then visualize:

```text
QEM score
AI score
combined score
collapse order
```

Use it to diagnose failures.

---

# 80. Failure Cases You Should Intentionally Test

Build a special evaluation set:

```text
cube
sphere
torus
cylinder
thin sheet
chair
car
character
mechanical part
object with UV seams
object with materials
object with textures
skinned character
highly detailed sculpture
messy imported mesh
```

If Crunch3D fails on these, do not hide it.

Use them to improve the system.

---

# 81. Thin Geometry Is a Special Case

Things like:

- blades
- leaves
- ears
- wires
- chair legs
- thin panels

can disappear under naïve QEM.

Add explicit tests for:

```text
minimum thickness
double-sided surfaces
nearby parallel surfaces
```

Potential future feature:

```text
local thickness
```

This is a very useful additional structural feature.

---

# 82. A Strong Future Feature: Local Thickness

For each edge/vertex estimate local feature thickness.

Example applications:

```text
leaf
sheet metal
ear
finger
blade
cloth
```

If an edge lies on a thin structure:

```text
preserve more
```

This can be added later as a new plugin-style extractor.

---

# 83. Another Strong Future Feature: Curvature Gradient

Instead of just:

```text
curvature
```

also compute:

```text
|curvature(v1) - curvature(v2)|
```

High curvature discontinuity often indicates a structural transition.

Potential edge feature:

```text
curvature_jump
```

---

# 84. Another Strong Future Feature: Local Feature Density

Estimate:

```text
triangles per local area
```

or local vertex density.

Useful because dense geometry can mean:

```text
intentional detail
```

or:

```text
bad triangulation
```

The ML model should learn the difference.

---

# 85. Another Strong Future Feature: Geometric Saliency

A later feature extractor can estimate local surface saliency.

Combine:

```text
curvature
curvature gradient
view dependence
local contrast
```

Use this as an optional feature, not a hard rule.

---

# 86. Production-Aware Objective

Crunch3D should optimize:

```text
quality
+
compression
+
runtime
```

not quality alone.

A final objective can be thought of as:

```text
Score =
    λ1 * geometric_quality
  + λ2 * feature_preservation
  + λ3 * topology_quality
  + λ4 * animation_quality
  - λ5 * runtime
```

The exact weights should be learned / validated through experiments rather than selected arbitrarily.

---

# 87. Recommended Repository Structure

```text
crunch3d/
│
├── core/
│   ├── mesh.py
│   ├── halfedge.py
│   ├── validation.py
│   └── topology.py
│
├── io/
│   ├── obj.py
│   ├── fbx.py
│   └── gltf.py
│
├── features/
│   ├── base.py
│   ├── geometry.py
│   ├── curvature.py
│   ├── topology.py
│   ├── uv.py
│   ├── material.py
│   ├── skinning.py
│   ├── texture.py
│   ├── ao.py
│   ├── visibility.py
│   ├── silhouette.py
│   └── animation.py
│
├── graph/
│   ├── builder.py
│   ├── positional_encoding.py
│   └── batching.py
│
├── ml/
│   ├── encoder.py
│   ├── edge_decoder.py
│   ├── model.py
│   ├── losses.py
│   ├── sampler.py
│   └── train.py
│
├── qem/
│   ├── quadric.py
│   ├── collapse.py
│   ├── heap.py
│   ├── constraints.py
│   └── simplifier.py
│
├── labels/
│   ├── oracle.py
│   ├── collapse_simulator.py
│   └── generate.py
│
├── evaluation/
│   ├── chamfer.py
│   ├── normals.py
│   ├── topology.py
│   ├── laplacian.py
│   ├── features.py
│   └── benchmark.py
│
├── datasets/
│   ├── prepare_shapenet.py
│   ├── prepare_objaverse.py
│   ├── prepare_tosca.py
│   └── cache.py
│
├── experiments/
│   ├── configs/
│   ├── baselines/
│   ├── ablations/
│   └── reports/
│
├── visualization/
│   ├── edge_heatmap.py
│   ├── collapse_sequence.py
│   └── comparisons.py
│
└── tests/
    ├── test_halfedge.py
    ├── test_qem.py
    ├── test_features.py
    ├── test_graph.py
    └── test_topology.py
```

---

# 88. Technology Stack

Recommended:

## Core

```text
C++
```

or

```text
C++ core + Python bindings
```

for the high-performance geometry/QEM portion.

---

## ML

```text
Python
PyTorch
PyTorch Geometric
NumPy
SciPy
```

---

## Geometry

Good options to evaluate:

```text
libigl
Geometry Central
CGAL
Open3D
trimesh
```

Use one main geometry representation rather than five partially overlapping systems.

---

## Rendering / visibility

Evaluate:

```text
Embree
Blender
Open3D
```

---

## Image processing

```text
OpenCV
```

for texture-gradient calculations.

---

# 89. Why C++ + Python Is Attractive

A practical architecture:

```text
C++:
half-edge
QEM
collapse
topology
feature geometry

        ↕ bindings

Python:
PyTorch
PyG
training
experiments
evaluation
```

This keeps:

```text
slow iterative mesh operations
```

out of the Python hot path.

But do not rewrite everything in C++ immediately.

First get the algorithm correct.

---

# 90. First Implementation Order

Do this in exactly this order.

## Step 1

Build robust mesh loader.

---

## Step 2

Build half-edge mesh.

---

## Step 3

Implement pure QEM.

---

## Step 4

Implement collapse validation.

---

## Step 5

Implement evaluation metrics.

---

## Step 6

Implement core feature extraction.

---

## Step 7

Implement graph conversion.

---

## Step 8

Implement tiny GCN importance model.

---

## Step 9

Generate oracle labels.

---

## Step 10

Train on a small dataset.

---

## Step 11

Integrate GNN with QEM.

---

## Step 12

Add staged inference.

---

## Step 13

Add asset-aware features.

---

## Step 14

Add expensive view-dependent features.

---

## Step 15

Run ablations.

---

# 91. Phase 1 — Deterministic Baseline

Target:

```text
Original mesh
      ↓
QEM
      ↓
target triangle count
```

Deliver:

```text
stable simplification
repeatable output
no catastrophic topology failures
```

Do not touch ML until this is reliable.

---

# 92. Phase 2 — Evaluation Harness

Build one command:

```bash
python benchmark.py \
    --input mesh.obj \
    --target-ratio 0.1 \
    --method qem
```

Output:

```json
{
  "compression": 0.90,
  "chamfer": ...,
  "normal_error": ...,
  "wrong_adjacency": ...,
  "laplacian_error": ...,
  "time_ms": ...
}
```

This becomes the central benchmark API.

---

# 93. Phase 3 — Feature Engine

Implement only:

```text
edge length
dihedral
normal difference
curvature
boundary
area
```

Visualize them.

Example:

```text
feature = curvature
```

then color the mesh.

Do the same for every feature.

If a feature visualization is nonsense, do not feed it to the model.

---

# 94. Phase 4 — Dataset Generator

Pipeline:

```text
raw mesh
   ↓
validation
   ↓
normalization
   ↓
half-edge
   ↓
features
   ↓
graph
   ↓
oracle candidate simulation
   ↓
labels
   ↓
cached .pt
```

Make this fully automated.

---

# 95. Phase 5 — Small GNN

Start with:

```text
100–200 meshes
```

Train until the entire ML loop works.

Do not spend days generating a huge dataset before discovering:

```text
shape of edge_index is wrong
```

or:

```text
labels are inverted.
```

---

# 96. Phase 6 — Proper Dataset

Move to:

```text
500–1,000 meshes
```

with:

```text
ShapeNet
Objaverse
human/deformable
```

and strict train/val/test splits.

---

# 97. Phase 7 — Model Upgrade

Compare:

```text
GCN
GCN + 2hop
GATv2
```

Keep the best configuration based on:

```text
validation simplification quality
```

not:

```text
training accuracy
```

---

# 98. Phase 8 — Integrate QEM

Implement:

```text
QEM score
+
AI importance
```

Then verify:

```text
AI does not cause instability
```

---

# 99. Phase 9 — Staged Inference

Compare:

```text
one-shot GNN
```

against:

```text
staged GNN re-evaluation
```

This should be an explicit experiment.

---

# 100. Phase 10 — Production Features

Add:

```text
UV
materials
skin weights
sharp edges
texture gradients
AO
visibility
silhouette
animation
```

one by one.

Every addition requires an ablation.

---

# 101. What "ML Is Good" Actually Means

Do not measure the GNN using only:

```text
loss
accuracy
F1
```

Those do not directly measure simplification quality.

The real model success condition is:

```text
same compression target
+
lower geometric error
+
better feature preservation
+
better topology
+
acceptable runtime
```

---

# 102. Main ML Scorecard

For every model report:

| Metric | QEM | Heuristic | Crunch3D |
|---|---:|---:|---:|
| Compression | | | |
| Chamfer ↓ | | | |
| Normal error ↓ | | | |
| Wrong adjacency ↓ | | | |
| Laplacian error ↓ | | | |
| Sharp-feature recall ↑ | | | |
| UV seam preservation ↑ | | | |
| Silhouette preservation ↑ | | | |
| Runtime ↓ | | | |

Add confidence intervals where feasible.

---

# 103. Statistical Rigor

Run each major experiment with:

```text
3 random seeds
```

at minimum.

Report:

```text
mean ± std
```

for validation/test aggregates.

For expensive full-mesh runs, use a fixed test set and keep the protocol identical.

---

# 104. Do Not Tune on the Test Set

Use:

```text
train → model learning
val   → hyperparameter selection
test  → final report
```

Once test evaluation starts:

```text
freeze the model.
```

---

# 105. Important Dataset Generalization Experiment

Train:

```text
ShapeNet + Objaverse subset
```

Test on:

```text
unseen human shapes
unseen object classes
```

Then:

```text
train on clean data
test on messy data
```

This tells you whether Crunch3D learned:

```text
mesh simplification
```

or merely:

```text
dataset-specific geometry patterns.
```

---

# 106. Research Positioning

Crunch3D can be framed as:

```text
Classical Geometry
        +
Learned Structural Importance
        +
Topology-Constrained Optimization
```

More specifically:

```text
MeshCNN:
mesh-aware learning inspiration

QEM:
geometric error minimization

2026 GNN-QEM:
structure-aware learned guidance

Crunch3D:
asset-aware + modular + staged + production-focused learned simplification
```

This is a much stronger technical narrative than claiming:

```text
"we used GNN to simplify meshes."
```

---

# 107. What Is Actually Novel in Crunch3D

The safest novelty claims should come from what you actually implement and measure.

Potentially strong contributions:

## 1. Modular asset-aware feature extraction

One model can consume additional signals when available.

---

## 2. Learned importance + QEM

Neural guidance without abandoning deterministic geometry.

---

## 3. Multi-stage re-evaluation

Importance is updated as topology evolves.

---

## 4. Multi-objective supervision

Training targets can incorporate:

```text
geometry
topology
features
```

instead of a single arbitrary label.

---

## 5. Diverse dataset validation

Train on controlled + messy meshes and test cross-domain generalization.

---

# 108. What NOT to Do

Do not:

```text
download entire Objaverse immediately
```

Do not:

```text
train on 19 features without feature normalization
```

Do not:

```text
randomly split simplification stages
```

Do not:

```text
claim improvement without QEM baseline
```

Do not:

```text
use test set to tune hyperparameters
```

Do not:

```text
use GNN score as the only collapse criterion
```

Do not:

```text
recompute every expensive feature after every collapse
```

Do not:

```text
add texture/AO/animation before geometry-only ML works
```

Do not:

```text
optimize the demo before the evaluation harness exists
```

---

# 109. Laptop-Friendly Strategy

The entire research workflow should be split into:

```text
OFFLINE
```

and:

```text
ONLINE
```

## Offline

Expensive:

```text
dataset download
mesh preprocessing
oracle label generation
curvature
texture analysis
AO
visibility
training
```

---

## Online

Fast:

```text
load mesh
feature extraction
GNN inference
QEM
simplification
export
```

Cache all reusable offline work.

---

# 110. Smart Subset Selection

Instead of random dataset sampling, select based on:

```text
triangle count
category
geometry type
complexity
asset quality
feature availability
```

Example balanced corpus:

```text
25% hard-surface
25% organic
20% architectural/furniture
15% vehicles/tools
15% characters/deformable
```

This is only a starting distribution.

Use your actual data distribution and report it.

---

# 111. Complexity Buckets

Split assets into:

```text
small:
<10K faces

medium:
10K–100K

large:
100K–500K

extreme:
>500K
```

Then benchmark runtime separately.

This prevents a model from looking fast because most test assets are tiny.

---

# 112. Stress Testing

At minimum test:

```text
10K
50K
100K
500K
1M+
```

triangle inputs where hardware permits.

Measure:

```text
RAM
VRAM
runtime
peak graph memory
peak heap size
```

For very large assets, use graph sampling/chunking or staged local processing where necessary.

---

# 113. Large Mesh Training Strategy

Do not force a 1M-face graph into the GNN during training.

Instead:

```text
full mesh
   ↓
sample local subgraphs
   ↓
train edge importance
   ↓
aggregate / evaluate
```

Possible sampling:

- local k-hop neighborhoods
- random edge-centered patches
- curvature-stratified sampling
- importance-stratified sampling

Full-mesh inference can be handled separately once the model is trained.

---

# 114. Graph Memory Is a Real Constraint

Because:

```text
N vertices
+
E edges
+
2-hop connections
+
Laplacian PE
+
batching
```

can consume significant memory.

Start with:

```text
single-graph batch
```

for large meshes.

Use gradient accumulation if needed.

---

# 115. Model Complexity Target

A useful first model is intentionally small.

Example:

```text
~100K–500K trainable parameters
```

is preferable to an enormous model.

The geometry and simplifier should remain the heavy-lifting part.

The GNN should be a compact structural scorer.

---

# 116. Why This Is Better for Practical Deployment

A small model means:

```text
fast inference
low memory
easy reproducibility
easy debugging
```

and makes it easier to demonstrate:

```text
"the ML component adds value without making simplification impractical."
```

---

# 117. Visualization Suite

Build these views:

## A. Original vs simplified

```text
side-by-side
```

## B. Edge importance heatmap

```text
red = preserve
blue = collapse candidate
```

## C. Collapse sequence

Show edges disappearing over time.

## D. Feature visualization

Display:

```text
curvature
dihedral
UV seams
material boundaries
```

## E. Error map

Display:

```text
local geometric error
```

These visuals are extremely useful for debugging.

---

# 118. Debugging the GNN

When predictions are bad, inspect:

```text
feature distributions
label distributions
graph connectivity
normalization
target ordering
```

Do not immediately increase model size.

Common bugs are:

```text
wrong edge indexing
feature leakage
label sign inversion
bad normalization
```

---

# 119. Feature Distribution Dashboard

For every feature report:

```text
min
max
mean
median
std
p1
p99
```

before and after normalization.

You may discover:

```text
curvature has huge outliers
```

or:

```text
dihedral is almost constant
```

which should trigger preprocessing changes.

---

# 120. Label Distribution Dashboard

Plot:

```text
oracle importance histogram
```

and:

```text
importance vs:
edge length
curvature
dihedral
```

This tells you whether labels are meaningful or simply duplicate one handcrafted feature.

---

# 121. Check for Shortcut Learning

For example:

If the model learns:

```text
importance ≈ 1 - edge_length
```

then it is not really learning structural importance.

Test:

```text
feature masking
```

and:

```text
correlation
```

between predictions and individual features.

---

# 122. Strong Experiment: Remove Edge Features

Run:

```text
GNN with vertex features only
```

Then:

```text
GNN + edge features
```

If edge features give a clear improvement:

```text
good evidence
```

that the edge-aware design is useful.

---

# 123. Strong Experiment: Remove Graph Context

Run:

```text
edge MLP only
```

versus:

```text
GNN + edge decoder
```

This answers:

> Does graph connectivity actually matter?

It should.

But measure it.

---

# 124. Strong Experiment: Remove QEM

Compare:

```text
GNN-only priority
```

versus:

```text
GNN + QEM
```

The objective is not to prove GNN can simplify alone.

The objective is to prove:

```text
learned structure + geometry optimizer
```

works better.

---

# 125. Strong Experiment: One-Shot vs Staged

Compare:

```text
single GNN prediction
```

against:

```text
recompute every stage
```

Expected benefit:

```text
better adaptation after topology changes
```

but measure runtime cost.

---

# 126. Suggested Final Model

After the experiments, a likely final architecture is:

```text
Vertex input:
XYZ
Normals
Valence
Boundary
Curvature
Laplacian PE

        ↓

2-branch GCN

        ↓

Vertex embedding

        ↓

Edge decoder:
h_u
h_v
|h_u-h_v|
edge features

        ↓

MLP

        ↓

Importance [0,1]

        ↓

Dynamic soft QEM modulation

        ↓

Topology-constrained heap

        ↓

Staged edge collapse
```

The exact final feature list should be determined experimentally.

---

# 127. Recommended Initial Hyperparameters

Start with:

```yaml
model:
  gnn: GCNConv
  layers: 3
  hidden_dim: 64
  dropout: 0.15
  laplacian_pe: 16
  two_hop_weight: 0.5

training:
  optimizer: Adam
  lr: 1e-3
  batch_size: 1
  epochs: 50
  seed: 42

loss:
  regression: 1.0
  ranking: 0.25
  safety: 1.0
```

These are starting values, not sacred constants.

The 2026 reference reports similar GNN architecture/training values, but your final configuration should come from validation experiments. citeturn481706search0

---

# 128. What to Implement This Week

## Milestone 1

```text
[ ] Half-edge mesh
[ ] validation
[ ] pure QEM
[ ] collapse heap
[ ] topology checks
```

## Milestone 2

```text
[ ] evaluation harness
[ ] Chamfer
[ ] normal error
[ ] topology metrics
[ ] Laplacian metric
```

## Milestone 3

```text
[ ] edge length
[ ] dihedral
[ ] normal difference
[ ] curvature
[ ] boundary
[ ] area
```

## Milestone 4

```text
[ ] graph builder
[ ] vertex feature matrix
[ ] edge feature matrix
[ ] Laplacian PE
```

## Milestone 5

```text
[ ] GCN encoder
[ ] edge decoder
[ ] importance output
[ ] loss
```

---

# 129. What to Implement After the First Working Model

```text
[ ] oracle labels
[ ] 500+ mesh dataset
[ ] QEM + AI integration
[ ] staged GNN inference
[ ] ablation runner
[ ] baseline runner
[ ] visualization
```

Then:

```text
[ ] UV
[ ] materials
[ ] skin weights
[ ] sharp edges
```

Then:

```text
[ ] texture
[ ] AO
[ ] visibility
[ ] silhouette
[ ] animation
```

---

# 130. Final Benchmark Protocol

For each test mesh:

```text
Input:
original mesh

Target:
90%, 75%, 50%, 25% of original faces

Methods:
1. QEM
2. Heuristic QEM
3. Crunch3D
```

Measure:

```text
faces
compression
Chamfer
normal error
wrong adjacency
Laplacian error
feature recall
runtime
```

Repeat for:

```text
clean
messy
organic
hard-surface
characters
textured
skinned
```

---

# 131. Final Results Table

The final report should contain something like:

| Dataset | Method | Reduction | Chamfer ↓ | Normal ↓ | Topology ↓ | Feature Recall ↑ | Time ↓ |
|---|---|---:|---:|---:|---:|---:|---:|
| ShapeNet | QEM | 90% | | | | | |
| ShapeNet | Heuristic | 90% | | | | | |
| ShapeNet | Crunch3D | 90% | | | | | |
| Objaverse | QEM | 90% | | | | | |
| Objaverse | Crunch3D | 90% | | | | | |
| Human | QEM | 90% | | | | | |
| Human | Crunch3D | 90% | | | | | |

Do not cherry-pick attractive examples.

Use a fixed test set.

---

# 132. Final Research Checklist

## Geometry

- [ ] QEM implemented correctly
- [ ] collapse validation works
- [ ] normals stable
- [ ] curvature stable
- [ ] topology checks correct

## Features

- [ ] core features implemented
- [ ] optional features modular
- [ ] normalization documented
- [ ] feature statistics checked

## Dataset

- [ ] ShapeNet subset
- [ ] Objaverse subset
- [ ] human/deformable subset
- [ ] no train/test leakage
- [ ] cached graphs
- [ ] reproducible splits

## ML

- [ ] baseline MLP
- [ ] GCN baseline
- [ ] 2-hop branch
- [ ] edge decoder
- [ ] regression loss
- [ ] ranking loss
- [ ] safety loss
- [ ] ablations
- [ ] multiple seeds

## Simplifier

- [ ] QEM + AI
- [ ] min heap
- [ ] local updates
- [ ] topology safety
- [ ] staged inference

## Evaluation

- [ ] Chamfer
- [ ] normal error
- [ ] wrong adjacency
- [ ] Laplacian error
- [ ] feature preservation
- [ ] runtime
- [ ] visual comparison

## Engineering

- [ ] tests
- [ ] configs
- [ ] experiment tracking
- [ ] checkpoints
- [ ] logs
- [ ] CLI
- [ ] visualization

---

# 133. The Most Important Strategic Decision

Do not try to make Crunch3D impressive by adding every possible feature.

Make it impressive by proving this chain:

```text
QEM
 ↓
good baseline

Handcrafted feature-aware QEM
 ↓
better

GNN importance
 ↓
better still

GNN + QEM
 ↓
better than both individually

Staged GNN + QEM
 ↓
better / more stable

Optional asset-aware features
 ↓
further gains on relevant assets
```

That progression is scientifically much stronger than:

```text
"We added AI."
```

---

# 134. The Crunch3D ML Thesis

The complete system can be summarized as:

> **Crunch3D learns structural importance on a mesh graph and uses that learned importance to guide topology-constrained QEM simplification, preserving high-value geometric and asset-specific features while aggressively removing redundant geometry.**

Architecture:

```text
Mesh
 ↓
Half-edge
 ↓
Feature extraction
 ↓
Graph
 ↓
GNN vertex embeddings
 ↓
Edge importance
 ↓
AI-modulated QEM
 ↓
Safe edge collapse
 ↓
Topology repair
 ↓
Staged re-inference
 ↓
Optimized mesh
```

---

# 135. Source / Research Reading List

## A. 2026 GNN-guided QEM paper

Primary reference:

https://www.mdpi.com/2227-7390/14/10/1610

Preprint:

https://www.preprints.org/manuscript/202604.1809

What to study:

- graph representation
- vertex features
- 1-hop / 2-hop processing
- edge decoder
- importance prediction
- QEM modulation
- staged inference
- loss functions
- evaluation metrics
- ablation tables
- experimental setup

Especially inspect the architecture and training tables before choosing your first implementation. The reported configuration uses a 3-layer GCNConv network, hidden dimension 64, LayerNorm, dropout 0.15, and a 16-dimensional Laplacian positional encoding. citeturn481706search2turn481706search0

---

## B. MeshCNN

Project:

https://ranahanocka.github.io/MeshCNN/

GitHub:

https://github.com/ranahanocka/MeshCNN

Wiki:

https://github.com/ranahanocka/MeshCNN/wiki

Key things to learn:

- edge-centric mesh learning
- mesh neighborhoods
- edge geometric inputs
- dynamic edge-collapse pooling
- dataset setup
- mesh preprocessing

MeshCNN's published project describes direct convolution and pooling on mesh edges, with pooling based on edge collapse. citeturn927351search3

---

## C. MeshCNN base dataset implementation

File:

https://github.com/ranahanocka/MeshCNN/blob/master/data/base_dataset.py

Read it for:

- dataset conventions
- sample loading
- preprocessing patterns
- how the original code organizes mesh samples

---

## D. ShapeNet

Official:

https://www.shapenet.org/

Use for:

- clean category-oriented models
- balanced benchmark subsets
- controlled experiments

ShapeNetCore's official overview lists about 51,300 models and 55 common object categories. citeturn927351search11

---

## E. Objaverse

Official documentation:

https://objaverse.allenai.org/docs/intro/

Use for:

- diversity
- messy real-world assets
- cross-domain testing

The documentation provides the Python API and describes Objaverse 1.0 (~800K objects) and Objaverse-XL (10M+ objects). citeturn927351search10

---

## F. TOSCA / SHREC human datasets

Dataset index:

https://profs.scienze.univr.it/~marin/shrec19/datasets

Use for:

- human/deformable geometry
- structural tests
- curvature-heavy assets

The index includes references to TOSCA, FAUST, SCAPE and SMPL. citeturn562969search8

---

## G. QEM

CMU reference:

https://www.cs.cmu.edu/~garland/quadrics/

Paper:

https://doi.org/10.1145/258734.258849

Use this to implement the classical geometric baseline correctly.

QEM remains the non-ML geometric foundation of Crunch3D. citeturn927351search5turn927351search6

---

## H. Neural Mesh Simplification

CVPR 2022:

https://openaccess.thecvf.com/content/CVPR2022/html/Potamias_Neural_Mesh_Simplification_CVPR_2022_paper.html

Supplement:

https://openaccess.thecvf.com/content/CVPR2022/supplemental/Potamias_Neural_Mesh_Simplification_CVPR_2022_supplemental.pdf

Use for:

- alternative learned simplification ideas
- benchmark terminology
- appearance error evaluation
- comparison against traditional greedy simplification

The paper presents a learnable mesh simplification approach that differs from Crunch3D's iterative QEM-guided approach, but its evaluation ideas are useful. citeturn562969search4

---

# 136. Final Recommendation

Build Crunch3D in this order:

```text
                ┌─────────────────┐
                │   DATASETS      │
                │                 │
                │ ShapeNet        │
                │ Objaverse       │
                │ Human meshes    │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ PREPROCESSING   │
                │                 │
                │ validation      │
                │ half-edge       │
                │ normalization   │
                └────────┬────────┘
                         │
                         ▼
              ┌───────────────────────┐
              │ FEATURE ENGINE        │
              │                       │
              │ geometry              │
              │ topology              │
              │ UV/material           │
              │ skinning              │
              │ optional rendering    │
              └──────────┬────────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ GRAPH BUILDER   │
                │                 │
                │ nodes = verts   │
                │ edges = mesh    │
                └────────┬────────┘
                         │
                         ▼
             ┌─────────────────────────┐
             │ EDGE IMPORTANCE GNN     │
             │                         │
             │ 1-hop GCN               │
             │ 2-hop GCN               │
             │ vertex embeddings       │
             │ edge decoder            │
             └────────────┬────────────┘
                          │
                          ▼
                 importance [0,1]
                          │
                          ▼
                ┌─────────────────┐
                │ AI + QEM        │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ SAFE COLLAPSE   │
                │                 │
                │ topology        │
                │ UV              │
                │ material        │
                │ feature checks  │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ STAGE UPDATE    │
                │                 │
                │ rebuild graph   │
                │ rerun GNN       │
                └────────┬────────┘
                         │
                         ▼
                optimized mesh
                         │
                         ▼
                quantitative eval
```

## The practical priority order

```text
1. QEM + topology correctness
2. evaluation harness
3. core geometry features
4. graph construction
5. GCN edge-importance model
6. oracle label generation
7. QEM + GNN integration
8. staged inference
9. ShapeNet + Objaverse diversity
10. ablation studies
11. UV/material/skinning
12. view-dependent features
13. performance optimization
14. production polish
```

Do not reverse this order.

The single biggest mistake would be spending time on:

```text
texture gradients
AO
visibility
animation
million-object datasets
```

before you have proven:

```text
Crunch3D > QEM
```

on a clean, controlled, statistically defensible test set.

The strongest version of Crunch3D is therefore **not the one with the most features or the biggest model**.

It is the one that can demonstrate:

```text
Same compression
        ↓
Less geometric error
        ↓
Better feature preservation
        ↓
Better topology
        ↓
Acceptable runtime
        ↓
Across unseen meshes
```

with a reproducible experimental pipeline.

