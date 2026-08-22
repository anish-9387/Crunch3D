import { useEffect, useMemo, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import {
  SELECTION_THRESHOLD,
  applyStamp,
  normalizedFrame,
  selectionCounts,
} from '../lib/brushSelection'

/**
 * Refactor brush — in-scene painting layer.
 *
 * Lets the user mark the surface the whole-model pass left denser than they
 * wanted, and hands the marked region to `/api/brush/refine`.
 *
 * Everything here is additive to the viewer: the loaded model's own materials,
 * geometry and transforms are never reassigned. The highlight is drawn by
 * sibling overlay meshes that share the model's geometry buffers and track its
 * world matrices, and the only data written onto that geometry is one extra
 * `aBrushWeight` attribute the base materials ignore.
 */

const HIGHLIGHT_COLOR = '#ff3b3b'
const WEIGHT_ATTRIBUTE = 'aBrushWeight'

const OVERLAY_VERTEX_SHADER = /* glsl */ `
  attribute float ${WEIGHT_ATTRIBUTE};
  varying float vWeight;
  void main() {
    vWeight = ${WEIGHT_ATTRIBUTE};
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`

const OVERLAY_FRAGMENT_SHADER = /* glsl */ `
  uniform vec3 uColor;
  uniform float uOpacity;
  varying float vWeight;
  void main() {
    // Below the visible floor the vertex is simply unpainted — discarding
    // rather than blending keeps the model's own shading untouched there.
    if (vWeight < 0.02) discard;
    float w = clamp(vWeight, 0.0, 1.0);
    gl_FragColor = vec4(uColor, uOpacity * (0.35 + 0.65 * w));
  }
`

function makeOverlayMaterial() {
  return new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: new THREE.Color(HIGHLIGHT_COLOR) },
      uOpacity: { value: 0.62 },
    },
    vertexShader: OVERLAY_VERTEX_SHADER,
    fragmentShader: OVERLAY_FRAGMENT_SHADER,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    // The overlay shares the model's triangles exactly, so it needs a depth
    // nudge or it z-fights with the surface it is meant to tint.
    polygonOffset: true,
    polygonOffsetFactor: -2,
    polygonOffsetUnits: -2,
  })
}
/**
 * Build the paintable representation of a loaded model.
 *
 * Positions are resolved into the *root-local* frame — the model's own space,
 * with the <Center> offset and any loader scaling divided out — because that is
 * the frame trimesh sees once it bakes node transforms, and then normalised by
 * the bounding box so neither side has to agree on units at all.
 */
function buildBrushTarget(root) {
  if (!root) return null
  root.updateWorldMatrix(true, true)

  const toRootLocal = new THREE.Matrix4().copy(root.matrixWorld).invert()
  const relative = new THREE.Matrix4()
  const scratch = new THREE.Vector3()

  const min = [Infinity, Infinity, Infinity]
  const max = [-Infinity, -Infinity, -Infinity]
  const parts = []
  let totalVertices = 0
  let totalFaces = 0

  root.traverse((child) => {
    if (!child.isMesh || !child.geometry) return
    const position = child.geometry.getAttribute('position')
    if (!position || position.count === 0) return

    relative.multiplyMatrices(toRootLocal, child.matrixWorld)
    const count = position.count
    const unit = new Float32Array(count * 3)

    for (let i = 0; i < count; i++) {
      scratch.fromBufferAttribute(position, i).applyMatrix4(relative)
      const o = i * 3
      unit[o] = scratch.x
      unit[o + 1] = scratch.y
      unit[o + 2] = scratch.z
      if (scratch.x < min[0]) min[0] = scratch.x
      if (scratch.y < min[1]) min[1] = scratch.y
      if (scratch.z < min[2]) min[2] = scratch.z
      if (scratch.x > max[0]) max[0] = scratch.x
      if (scratch.y > max[1]) max[1] = scratch.y
      if (scratch.z > max[2]) max[2] = scratch.z
    }

    const index = child.geometry.index ? child.geometry.index.array : null
    totalVertices += count
    totalFaces += index ? Math.floor(index.length / 3) : Math.floor(count / 3)
    parts.push({ mesh: child, count, unit, index, weights: new Float32Array(count) })
  })

  if (parts.length === 0 || !Number.isFinite(min[0])) return null

  const { origin, scale } = normalizedFrame(min, max)
  for (const part of parts) {
    const { unit, count } = part
    for (let i = 0, o = 0; i < count; i++, o += 3) {
      unit[o] = (unit[o] - origin[0]) / scale
      unit[o + 1] = (unit[o + 1] - origin[1]) / scale
      unit[o + 2] = (unit[o + 2] - origin[2]) / scale
    }
  }

  // Attach the weight attribute the overlay shader reads. Base materials do
  // not declare it, so it is inert for normal rendering.
  for (const part of parts) {
    const existing = part.mesh.geometry.getAttribute(WEIGHT_ATTRIBUTE)
    if (existing && existing.count === part.count) {
      existing.array.fill(0)
      existing.needsUpdate = true
      part.attribute = existing
    } else {
      part.attribute = new THREE.BufferAttribute(part.weights, 1)
      part.mesh.geometry.setAttribute(WEIGHT_ATTRIBUTE, part.attribute)
    }
    part.weights = part.attribute.array
  }

  return {
    parts,
    toRootLocal,
    frame: {
      origin,
      scale,
      extents: [
        (max[0] - min[0]) / scale,
        (max[1] - min[1]) / scale,
        (max[2] - min[2]) / scale,
      ],
    },
    totalVertices,
    totalFaces,
  }
}
const STAMP_SPACING = 0.34
/** Minimum gap between stamps, as a fraction of brush radius. Matches
 *  `thinStroke` so the stroke sent over the wire is the stroke painted. */

const COUNT_REPORT_INTERVAL_MS = 140

/**
 * In-scene brush: raycasts the model, accumulates stamps, draws the highlight.
 *
 * `strokeRef` is a plain mutable ref rather than React state on purpose — a
 * drag produces stamps far faster than a re-render can keep up with, and the
 * parent only needs the accumulated stroke when the user commits it.
 */
export function BrushLayer({ object, active, settings, strokeRef, onCounts }) {
  const { camera, gl } = useThree()
  const controls = useThree((s) => s.controls)
  const cursorRef = useRef(null)
  const paintingRef = useRef(false)
  const pointerRef = useRef(null)
  const lastStampRef = useRef(null)
  const lastReportRef = useRef(0)
  const settingsRef = useRef(settings)
  settingsRef.current = settings

  const target = useMemo(() => (object ? buildBrushTarget(object) : null), [object])

  const overlays = useMemo(() => {
    if (!target) return []
    return target.parts.map((part) => {
      const overlay = new THREE.Mesh(part.mesh.geometry, makeOverlayMaterial())
      overlay.matrixAutoUpdate = false
      overlay.frustumCulled = false
      overlay.renderOrder = 3
      return overlay
    })
  }, [target])

  // Publish the frame as soon as the model is paintable: the parent needs it to
  // tell the backend which axes the stroke was painted against.
  useEffect(() => {
    if (!strokeRef) return
    strokeRef.current = { stamps: [], frame: target ? target.frame : null }
    lastStampRef.current = null
    onCounts?.({ vertices: 0, faces: 0, totalFaces: target?.totalFaces ?? 0 })
  }, [target, strokeRef, onCounts])

  useEffect(() => () => {
    for (const overlay of overlays) overlay.material.dispose()
  }, [overlays])

  // Clearing is driven by the parent bumping `settings.clearToken`, so the
  // painted state lives in one place (the geometry attribute) and the panel
  // does not have to own a copy of it.
  useEffect(() => {
    if (!target) return
    for (const part of target.parts) {
      part.weights.fill(0)
      part.attribute.needsUpdate = true
    }
    if (strokeRef) strokeRef.current = { stamps: [], frame: target.frame }
    lastStampRef.current = null
    onCounts?.({ vertices: 0, faces: 0, totalFaces: target.totalFaces })
  }, [settings.clearToken, target, strokeRef, onCounts])
  const raycaster = useMemo(() => new THREE.Raycaster(), [])
  const ndc = useMemo(() => new THREE.Vector2(), [])

  const pickSurface = (clientX, clientY) => {
    if (!object) return null
    const rect = gl.domElement.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return null
    ndc.x = ((clientX - rect.left) / rect.width) * 2 - 1
    ndc.y = -((clientY - rect.top) / rect.height) * 2 + 1
    raycaster.setFromCamera(ndc, camera)
    const hits = raycaster.intersectObject(object, true)
    return hits.length > 0 ? hits[0] : null
  }

  const stampAt = (hit) => {
    if (!target || !hit || !object) return
    const { radius, erase, falloff, strength } = settingsRef.current
    // Recompute root-local matrix live — the cached target.toRootLocal can be
    // stale after <Center> re-centers or the loader applies a new transform.
    // Using the current object.matrixWorld guarantees the hit point converts
    // to the exact same bbox-normalised frame the backend builds from trimesh.
    const liveToRootLocal = new THREE.Matrix4().copy(object.matrixWorld).invert()
    const local = hit.point.clone().applyMatrix4(liveToRootLocal)
    const center = [
      (local.x - target.frame.origin[0]) / target.frame.scale,
      (local.y - target.frame.origin[1]) / target.frame.scale,
      (local.z - target.frame.origin[2]) / target.frame.scale,
    ]

    const previous = lastStampRef.current
    if (previous && previous.erase === !!erase) {
      const dx = center[0] - previous.center[0]
      const dy = center[1] - previous.center[1]
      const dz = center[2] - previous.center[2]
      const step = STAMP_SPACING * Math.min(previous.radius, radius)
      if (dx * dx + dy * dy + dz * dz < step * step) return
    }

    const stamp = { center, radius, erase: !!erase, strength, falloff }
    let changed = false
    for (const part of target.parts) {
      if (applyStamp(part.unit, part.weights, stamp)) {
        part.attribute.needsUpdate = true
        changed = true
      }
    }
    if (!changed) return

    lastStampRef.current = stamp
    if (strokeRef) {
      const state = strokeRef.current || { stamps: [], frame: target.frame }
      state.frame = target.frame
      state.stamps = [...state.stamps, stamp]
      strokeRef.current = state
    }

    const now = performance.now()
    if (onCounts && now - lastReportRef.current > COUNT_REPORT_INTERVAL_MS) {
      lastReportRef.current = now
      let vertices = 0
      let faces = 0
      for (const part of target.parts) {
        const counts = selectionCounts(part.weights, part.index, SELECTION_THRESHOLD)
        vertices += counts.vertices
        faces += counts.faces
      }
      onCounts({ vertices, faces, totalFaces: target.totalFaces })
    }
  }

  const reportFinalCounts = () => {
    if (!target || !onCounts) return
    let vertices = 0
    let faces = 0
    for (const part of target.parts) {
      const counts = selectionCounts(part.weights, part.index, SELECTION_THRESHOLD)
      vertices += counts.vertices
      faces += counts.faces
    }
    lastReportRef.current = performance.now()
    onCounts({ vertices, faces, totalFaces: target.totalFaces })
  }

  // Changing edge softness re-evaluates the stroke already painted rather than
  // only affecting the next dab. Without this the highlight would show one
  // falloff while the request carries another, and the region the engine picks
  // would not be the region on screen.
  useEffect(() => {
    if (!target) return
    const painted = strokeRef?.current?.stamps
    if (!painted || painted.length === 0) return

    const restamped = painted.map((stamp) => ({ ...stamp, falloff: settings.falloff }))
    strokeRef.current = { stamps: restamped, frame: target.frame }
    for (const part of target.parts) {
      part.weights.fill(0)
      for (const stamp of restamped) applyStamp(part.unit, part.weights, stamp)
      part.attribute.needsUpdate = true
    }
    reportFinalCounts()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings.falloff, target])
  // Pointer wiring. Listeners are registered in the capture phase so that a
  // drag which starts *on the model* can switch OrbitControls off before its
  // own handler sees the event — that is what lets left-drag paint while
  // left-drag on the background still orbits, with no mode switch to explain.
  useEffect(() => {
    if (!active || !target) return
    const element = gl.domElement
    const previousCursor = element.style.cursor
    element.style.cursor = 'crosshair'

    const stopOrbit = () => {
      if (controls && controls.enabled) {
        controls.enabled = false
        return true
      }
      return false
    }
    let orbitWasEnabled = false

    const onPointerDown = (event) => {
      if (event.button !== 0 || !event.isPrimary) return
      const hit = pickSurface(event.clientX, event.clientY)
      if (!hit) return
      orbitWasEnabled = stopOrbit()
      paintingRef.current = true
      lastStampRef.current = null
      pointerRef.current = { x: event.clientX, y: event.clientY }
      element.setPointerCapture?.(event.pointerId)
      stampAt(hit)
      event.preventDefault()
      event.stopPropagation()
    }

    const onPointerMove = (event) => {
      pointerRef.current = { x: event.clientX, y: event.clientY }
      if (!paintingRef.current) return
      event.preventDefault()
      event.stopPropagation()
    }

    const endStroke = (event) => {
      if (!paintingRef.current) return
      paintingRef.current = false
      lastStampRef.current = null
      if (orbitWasEnabled && controls) controls.enabled = true
      orbitWasEnabled = false
      element.releasePointerCapture?.(event.pointerId)
      reportFinalCounts()
    }

    const onPointerLeave = () => {
      pointerRef.current = null
    }

    element.addEventListener('pointerdown', onPointerDown, { capture: true })
    element.addEventListener('pointermove', onPointerMove, { capture: true })
    element.addEventListener('pointerup', endStroke, { capture: true })
    element.addEventListener('pointercancel', endStroke, { capture: true })
    element.addEventListener('pointerleave', onPointerLeave)

    return () => {
      element.removeEventListener('pointerdown', onPointerDown, { capture: true })
      element.removeEventListener('pointermove', onPointerMove, { capture: true })
      element.removeEventListener('pointerup', endStroke, { capture: true })
      element.removeEventListener('pointercancel', endStroke, { capture: true })
      element.removeEventListener('pointerleave', onPointerLeave)
      element.style.cursor = previousCursor
      paintingRef.current = false
      pointerRef.current = null
      // Never leave the viewer unable to orbit because a stroke was cut short
      // by a re-render or a mode toggle.
      if (controls) controls.enabled = true
    }
  }, [active, target, gl, camera, controls, object])

  // One raycast per frame: enough for a smooth stroke, and it keeps a heavy
  // mesh from being re-picked on every one of the dozens of pointermove events
  // a browser fires per frame.
  useFrame(() => {
    if (!target) return

    for (let i = 0; i < overlays.length; i++) {
      const overlay = overlays[i]
      overlay.matrix.copy(target.parts[i].mesh.matrixWorld)
      overlay.matrixWorldNeedsUpdate = true
    }

    const cursor = cursorRef.current
    if (!active) {
      if (cursor) cursor.visible = false
      return
    }

    const pointer = pointerRef.current
    const hit = pointer ? pickSurface(pointer.x, pointer.y) : null

    if (cursor) {
      if (hit) {
        cursor.visible = true
        cursor.position.copy(hit.point)
        const normal = hit.face
          ? hit.face.normal.clone().transformDirection(hit.object.matrixWorld)
          : camera.getWorldDirection(new THREE.Vector3()).negate()
        cursor.lookAt(hit.point.clone().add(normal))
        const worldRadius = settingsRef.current.radius * target.frame.scale
        cursor.scale.setScalar(Math.max(worldRadius, 1e-4))
      } else {
        cursor.visible = false
      }
    }

    if (paintingRef.current && hit) stampAt(hit)
  })

  if (!target) return null

  return (
    <>
      <group>
        {overlays.map((overlay, index) => (
          <primitive key={index} object={overlay} />
        ))}
      </group>
      <mesh ref={cursorRef} visible={false} renderOrder={4}>
        {/* Unit-radius ring, scaled to the brush footprint each frame. */}
        <ringGeometry args={[0.88, 1.0, 48]} />
        <meshBasicMaterial
          color={settings.erase ? '#8adb00' : HIGHLIGHT_COLOR}
          transparent
          opacity={0.9}
          side={THREE.DoubleSide}
          depthTest={false}
        />
      </mesh>
    </>
  )
}
/**
 * Brush settings and the commit action, as a panel docked in the viewer.
 *
 * Lives next to the canvas rather than in the sidebar because it is a direct
 * manipulation tool: the size slider and the mode toggle only mean anything
 * while the user is looking at the surface they are painting.
 */
export function BrushPanel({
  settings,
  onSettingsChange,
  counts,
  onClear,
  onApply,
  applying,
  error,
  result,
}) {
  const set = (patch) => onSettingsChange({ ...settings, ...patch })
  const regionPercent =
    counts.totalFaces > 0 ? (counts.faces / counts.totalFaces) * 100 : 0
  const hasSelection = counts.faces > 0

  return (
    <div className="brush-panel">
      <div className="brush-panel-title">Refactor Brush</div>

      <p className="brush-hint">
        Drag on the model to mark the area that is still too dense. Drag the
        background to orbit.
      </p>

      <div className="brush-mode-row">
        <button
          type="button"
          className={`viewer-btn ${settings.erase ? '' : 'active'}`}
          onClick={() => set({ erase: false })}
        >
          Paint
        </button>
        <button
          type="button"
          className={`viewer-btn ${settings.erase ? 'active' : ''}`}
          onClick={() => set({ erase: true })}
        >
          Erase
        </button>
      </div>

      <label className="brush-field">
        <span>
          Brush size <b>{(settings.radius * 100).toFixed(1)}%</b>
        </span>
        <input
          type="range"
          min={1}
          max={30}
          step={0.5}
          value={settings.radius * 100}
          onChange={(e) => set({ radius: Number(e.target.value) / 100 })}
        />
      </label>

      <label className="brush-field">
        <span>
          Edge softness <b>{settings.falloff}</b>
        </span>
        <select
          className="config-select"
          value={settings.falloff}
          onChange={(e) => set({ falloff: e.target.value })}
        >
          <option value="smooth">Smooth</option>
          <option value="linear">Linear</option>
          <option value="hard">Hard</option>
        </select>
      </label>

      <label className="brush-field">
        <span>
          Reduce region by <b>{settings.reductionPercent}%</b>
        </span>
        <input
          type="range"
          min={5}
          max={90}
          step={5}
          value={settings.reductionPercent}
          onChange={(e) => set({ reductionPercent: Number(e.target.value) })}
        />
      </label>

      <div className="brush-readout">
        {hasSelection ? (
          <>
            <b>{counts.faces.toLocaleString()}</b> faces marked
            {counts.totalFaces > 0 && ` · ${regionPercent.toFixed(1)}% of mesh`}
          </>
        ) : (
          'Nothing marked yet'
        )}
      </div>

      <div className="brush-actions">
        <button
          type="button"
          className="viewer-btn"
          onClick={onClear}
          disabled={!hasSelection || applying}
        >
          Clear
        </button>
        <button
          type="button"
          className="brush-apply-btn"
          onClick={onApply}
          disabled={!hasSelection || applying}
        >
          {applying ? 'Optimizing region...' : 'Optimize Region'}
        </button>
      </div>

      {error && <div className="brush-error">{error}</div>}
      {result && !error && <div className="brush-result">{result}</div>}
    </div>
  )
}

export default BrushLayer
