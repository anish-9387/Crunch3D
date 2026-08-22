/**
 * brushSelection.js — refactor-brush selection maths (viewer side)
 *
 * Deliberate mirror of `model/engine/brush_selection.py`. The two must agree
 * exactly: the highlight the user paints in the viewer is the promise, and the
 * region the engine decimates is the delivery. Any drift between these kernels
 * shows up as "it optimised somewhere else than I painted", which is the one
 * failure this feature cannot afford.
 *
 * Coordinates are bbox-normalised — origin at the model's bbox minimum, one
 * unit being its bbox diagonal — so nothing here depends on the model's units,
 * on how <Center> offsets it for display, or on the loader's scale conventions.
 */

export const FALLOFF_KERNELS = ['smooth', 'linear', 'hard']
export const DEFAULT_FALLOFF = 'smooth'
export const SELECTION_THRESHOLD = 0.5

/** Brush profile as a function of distance / radius. Mirrors `_kernel`. */
export function brushKernel(ratio, falloff = DEFAULT_FALLOFF) {
  if (falloff === 'hard') return ratio <= 1 ? 1 : 0
  const t = Math.min(Math.max(1 - ratio, 0), 1)
  if (falloff === 'linear') return t
  return t * t * (3 - 2 * t) // smoothstep
}

/**
 * Normalised frame for a set of vertex positions.
 *
 * `positions` is a flat [x,y,z,...] array in the space the stamps will live in
 * (root-local, matching what trimesh sees after it bakes node transforms).
 */
export function normalizedFrame(min, max) {
  const dx = max[0] - min[0]
  const dy = max[1] - min[1]
  const dz = max[2] - min[2]
  let diagonal = Math.sqrt(dx * dx + dy * dy + dz * dz)
  if (!Number.isFinite(diagonal) || diagonal <= 1e-12) diagonal = 1
  return { origin: [min[0], min[1], min[2]], scale: diagonal }
}

/**
 * Apply one stamp to a weight buffer in place; returns true if anything changed.
 *
 * `unit` holds bbox-normalised positions as a flat Float32Array, so the caller
 * pays the normalisation cost once per model rather than once per dab. The
 * per-axis reject before the square root is what keeps a large mesh painting at
 * interactive rates without a spatial index.
 */
export function applyStamp(unit, weights, stamp) {
  const { center, radius, erase = false, strength = 1 } = stamp
  const [cx, cy, cz] = center
  const r = Math.max(radius, 1e-6)
  const r2 = r * r
  let touched = false

  for (let i = 0, v = 0; i < weights.length; i++, v += 3) {
    const dx = unit[v] - cx
    if (dx > r || dx < -r) continue
    const dy = unit[v + 1] - cy
    if (dy > r || dy < -r) continue
    const dz = unit[v + 2] - cz
    if (dz > r || dz < -r) continue

    const d2 = dx * dx + dy * dy + dz * dz
    if (d2 > r2) continue

    const profile = brushKernel(Math.sqrt(d2) / r, stamp.falloff || DEFAULT_FALLOFF) * strength
    const before = weights[i]
    const next = erase
      ? Math.max(before - profile, 0)
      : Math.max(before, profile)
    if (next !== before) {
      weights[i] = next
      touched = true
    }
  }

  return touched
}

/** Rebuild a weight buffer from scratch. Mirrors `build_vertex_weights`. */
export function buildWeights(unit, vertexCount, stamps) {
  const weights = new Float32Array(vertexCount)
  for (const stamp of stamps) applyStamp(unit, weights, stamp)
  return weights
}

/** Selected vertex / face counts at the shared threshold. */
export function selectionCounts(weights, indices, threshold = SELECTION_THRESHOLD) {
  let vertices = 0
  for (let i = 0; i < weights.length; i++) if (weights[i] >= threshold) vertices++

  let faces = 0
  if (indices) {
    for (let i = 0; i + 2 < indices.length; i += 3) {
      const mean = (weights[indices[i]] + weights[indices[i + 1]] + weights[indices[i + 2]]) / 3
      if (mean >= threshold) faces++
    }
  } else {
    for (let i = 0; i + 2 < weights.length; i += 3) {
      const mean = (weights[i] + weights[i + 1] + weights[i + 2]) / 3
      if (mean >= threshold) faces++
    }
  }
  return { vertices, faces }
}

/**
 * Thin a stroke down to the stamps worth sending.
 *
 * The pointer fires far more often than the brush footprint changes, so most
 * dabs in a drag are redundant. Keeping one per `spacing` fraction of a brush
 * width preserves the painted shape while holding the request — and the
 * engine's per-stamp neighbour queries — to a sane size.
 */
export function thinStroke(stamps, limit = 4000, spacing = 0.34) {
  if (stamps.length <= limit) return stamps

  const kept = []
  let last = null
  for (const stamp of stamps) {
    if (last && last.erase === stamp.erase) {
      const dx = stamp.center[0] - last.center[0]
      const dy = stamp.center[1] - last.center[1]
      const dz = stamp.center[2] - last.center[2]
      const minStep = spacing * Math.min(last.radius, stamp.radius)
      if (dx * dx + dy * dy + dz * dz < minStep * minStep) continue
    }
    kept.push(stamp)
    last = stamp
  }

  // Still over budget after spacing: keep an even sample so the stroke's shape
  // survives rather than truncating it and losing the tail entirely.
  if (kept.length <= limit) return kept
  const step = kept.length / limit
  const sampled = []
  for (let i = 0; sampled.length < limit && Math.floor(i) < kept.length; i += step) {
    sampled.push(kept[Math.floor(i)])
  }
  return sampled
}
