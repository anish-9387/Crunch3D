import { useState, Suspense, useEffect, useMemo, useRef, useCallback } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, Center, Grid } from '@react-three/drei'
import * as THREE from 'three'
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js'
import { STLLoader } from 'three/addons/loaders/STLLoader.js'
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import ModelInspector from './ModelInspector'

function collectModelSummary(rootObject) {
  if (!rootObject) return null

  let meshCount = 0
  let materialCount = 0
  let vertexCount = 0
  let faceCount = 0
  let hasNormals = false
  let hasUVs = false
  const meshNames = []
  const materialSet = new Set()

  rootObject.traverse((child) => {
    if (!child.isMesh || !child.geometry) return
    meshCount += 1
    const geom = child.geometry
    const pos = geom.getAttribute('position')
    if (pos) vertexCount += pos.count
    if (geom.index) {
      faceCount += Math.floor(geom.index.count / 3)
    } else if (pos) {
      faceCount += Math.floor(pos.count / 3)
    }
    hasNormals = hasNormals || !!geom.getAttribute('normal')
    hasUVs = hasUVs || !!geom.getAttribute('uv')
    meshNames.push(child.name || `${child.type}_${meshCount}`)

    const materials = Array.isArray(child.material) ? child.material : [child.material]
    materials.forEach((mat) => {
      if (mat) materialSet.add(mat.uuid)
    })
  })
  materialCount = materialSet.size

  const box = new THREE.Box3().setFromObject(rootObject)
  const size = new THREE.Vector3()
  box.getSize(size)

  return {
    type: rootObject.type || 'Mesh',
    meshCount,
    materialCount,
    vertexCount,
    faceCount,
    hasNormals,
    hasUVs,
    position: rootObject.position ? rootObject.position.clone() : null,
    rotation: rootObject.rotation
      ? {
          x: THREE.MathUtils.radToDeg(rootObject.rotation.x),
          y: THREE.MathUtils.radToDeg(rootObject.rotation.y),
          z: THREE.MathUtils.radToDeg(rootObject.rotation.z),
        }
      : null,
    scale: rootObject.scale ? rootObject.scale.clone() : null,
    bounds: {
      size: { x: size.x, y: size.y, z: size.z },
      min: box.min.toArray(),
      max: box.max.toArray(),
      diagonal: size.length(),
    },
    meshNames,
  }
}

function CameraReporter({ onCameraChange }) {
  const { camera } = useThree()
  const lastReportRef = useRef({
    time: 0,
    x: null,
    y: null,
    z: null,
    fov: null,
    near: null,
    far: null,
  })

  useFrame(() => {
    const now = performance.now()
    const current = {
      x: camera.position.x,
      y: camera.position.y,
      z: camera.position.z,
      fov: camera.fov,
      near: camera.near,
      far: camera.far,
    }

    const prev = lastReportRef.current
    const moved =
      prev.x === null ||
      Math.abs(current.x - prev.x) > 0.001 ||
      Math.abs(current.y - prev.y) > 0.001 ||
      Math.abs(current.z - prev.z) > 0.001 ||
      Math.abs(current.fov - prev.fov) > 0.001 ||
      Math.abs(current.near - prev.near) > 0.001 ||
      Math.abs(current.far - prev.far) > 0.001

    const shouldReport = moved && now - prev.time > 120
    if (!shouldReport) return

    lastReportRef.current = { ...current, time: now }
    onCameraChange({
      position: camera.position.clone(),
      fov: camera.fov,
      near: camera.near,
      far: camera.far,
    })
  })
  return null
}

function MeshFromUrl({ url, filename, wireframe, onModelReady, onModelError }) {
  const [object, setObject] = useState(null)

  useEffect(() => {
    if (!url) return
    let cancelled = false
    setObject(null)
    onModelError?.(null)
    const ext = filename?.split('.').pop()?.toLowerCase()
    const manager = new THREE.LoadingManager()

    function onSuccess(obj) {
      if (cancelled) return
      setObject(obj)
      onModelReady?.(collectModelSummary(obj))
    }

    function onError(err) {
      if (cancelled) return
      onModelError?.(err)
    }

    if (ext === 'obj') {
      new OBJLoader(manager).load(url, (obj) => onSuccess(obj), undefined, onError)
    } else if (ext === 'stl') {
      new STLLoader(manager).load(url, (geometry) => {
        geometry.computeVertexNormals()
        const mesh = new THREE.Mesh(geometry)
        onSuccess(mesh)
      }, undefined, onError)
    } else if (ext === 'ply') {
      new PLYLoader(manager).load(url, (geometry) => {
        geometry.computeVertexNormals()
        const mesh = new THREE.Mesh(geometry)
        onSuccess(mesh)
      }, undefined, onError)
    } else if (ext === 'glb' || ext === 'gltf') {
      new GLTFLoader(manager).load(url, (gltf) => onSuccess(gltf.scene), undefined, onError)
    } else {
      onError(new Error(`Unsupported preview format: ${ext || 'unknown'}`))
    }

    return () => {
      cancelled = true
    }
  }, [url, filename, onModelReady, onModelError])

  const material = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: '#d4d4d4',
        wireframe,
        flatShading: !wireframe,
        side: THREE.DoubleSide,
        roughness: 0.78,
        metalness: 0.05,
      }),
    [wireframe]
  )

  useEffect(() => {
    if (!object) return
    object.traverse((child) => {
      if (child.isMesh) {
        child.material = material
      }
    })
  }, [object, material])

  useEffect(() => {
    return () => {
      material.dispose()
    }
  }, [material])

  if (!object) return null

  return (
    <Center>
      <primitive object={object} />
    </Center>
  )
}

function Scene({ url, filename, wireframe, onModelReady, onModelError, onCameraChange, performanceMode }) {
  return (
    <>
      <ambientLight intensity={0.7} />
      <directionalLight position={[4, 5, 4]} intensity={0.85} color="#ffffff" />
      {!performanceMode && <directionalLight position={[-2, -2, 1]} intensity={0.4} color="#e6e6e6" />}
      <Suspense fallback={null}>
        {url && (
          <MeshFromUrl
            url={url}
            filename={filename}
            wireframe={wireframe}
            onModelReady={onModelReady}
            onModelError={onModelError}
          />
        )}
      </Suspense>
      <CameraReporter onCameraChange={onCameraChange} />
      <OrbitControls makeDefault enableDamping dampingFactor={0.1} />
      {!performanceMode && (
        <Grid
          args={[10, 10]}
          cellSize={0.5}
          cellThickness={0.5}
          cellColor="#4a4a4a"
          sectionSize={2}
          sectionThickness={1}
          sectionColor="#7a7a7a"
          fadeDistance={15}
          infiniteGrid
          position={[0, -1, 0]}
        />
      )}
    </>
  )
}

export default function ModelViewer({
  originalUrl,
  optimizedUrl,
  filename,
  optimizedFilename,
  originalStats,
  optimizedStats,
  darkMode,
  processing,
  stage,
  performanceMode,
}) {
  const [wireframe, setWireframe] = useState(false)
  const [splitView, setSplitView] = useState(false)
  const [modelSummary, setModelSummary] = useState(null)
  const [cameraInfo, setCameraInfo] = useState(null)
  const [viewerError, setViewerError] = useState(null)
  const cameraCacheRef = useRef({})

  const showSplit = splitView && optimizedUrl
  const activeFilename = optimizedUrl ? optimizedFilename : filename
  const activeStats = optimizedUrl ? optimizedStats : originalStats

  const inspectorMode = showSplit ? 'Comparison' : optimizedUrl ? 'Optimized' : 'Original'

  const handleCameraChange = useCallback((next) => {
    const rounded = {
      fov: Number(next.fov.toFixed(2)),
      near: Number(next.near.toFixed(4)),
      far: Number(next.far.toFixed(2)),
      x: Number(next.position.x.toFixed(3)),
      y: Number(next.position.y.toFixed(3)),
      z: Number(next.position.z.toFixed(3)),
    }

    const prev = cameraCacheRef.current
    if (
      prev.fov === rounded.fov &&
      prev.near === rounded.near &&
      prev.far === rounded.far &&
      prev.x === rounded.x &&
      prev.y === rounded.y &&
      prev.z === rounded.z
    ) {
      return
    }
    cameraCacheRef.current = rounded
    setCameraInfo({
      position: new THREE.Vector3(rounded.x, rounded.y, rounded.z),
      fov: rounded.fov,
      near: rounded.near,
      far: rounded.far,
    })
  }, [])

  const handleModelError = useCallback((err) => {
    if (!err) {
      setViewerError(null)
      return
    }
    setViewerError(err?.message || 'Could not load this mesh in the viewer')
  }, [])

  const handleModelReady = useCallback((summary) => {
    setViewerError(null)
    setModelSummary(summary)
  }, [])

  return (
    <div className="viewer-layout">
      <div className="viewer-area">
        <div className="viewer-controls">
          <button
            className={`viewer-btn ${wireframe ? 'active' : ''}`}
            onClick={() => setWireframe(!wireframe)}
          >
            Wireframe
          </button>
          {optimizedUrl && (
            <button
              className={`viewer-btn ${splitView ? 'active' : ''}`}
              onClick={() => setSplitView(!splitView)}
            >
              Split View
            </button>
          )}
        </div>

      {showSplit ? (
        <div className="viewer-split">
          <div className="viewer-container">
            <div className="viewer-label">Original</div>
            <Canvas
              camera={{ position: [3, 2, 3], fov: 50 }}
              dpr={performanceMode ? [0.8, 1.25] : [1, 2]}
              gl={{ antialias: !performanceMode, powerPreference: 'high-performance' }}
            >
              <Scene
                url={originalUrl}
                filename={filename}
                wireframe={wireframe}
                onModelReady={handleModelReady}
                onModelError={handleModelError}
                onCameraChange={handleCameraChange}
                performanceMode={performanceMode}
              />
            </Canvas>
          </div>
          <div className="viewer-container">
            <div className="viewer-label">Optimized</div>
            <Canvas
              camera={{ position: [3, 2, 3], fov: 50 }}
              dpr={performanceMode ? [0.8, 1.25] : [1, 2]}
              gl={{ antialias: !performanceMode, powerPreference: 'high-performance' }}
            >
              <Scene
                url={optimizedUrl}
                filename={optimizedFilename}
                wireframe={wireframe}
                onModelReady={handleModelReady}
                onModelError={handleModelError}
                onCameraChange={handleCameraChange}
                performanceMode={performanceMode}
              />
            </Canvas>
          </div>
        </div>
      ) : (
        <div className="viewer-container">
          {processing && (
            <div className="processing-overlay">
              <div className="spinner" />
              <p>{stage || 'Processing...'}</p>
            </div>
          )}
          <div className="viewer-label">
            {optimizedUrl && !splitView ? 'Optimized' : 'Original'}
          </div>
          <Canvas
            camera={{ position: [3, 2, 3], fov: 50 }}
            dpr={performanceMode ? [0.8, 1.25] : [1, 2]}
            gl={{ antialias: !performanceMode, powerPreference: 'high-performance' }}
          >
            <Scene
              url={optimizedUrl || originalUrl}
              filename={optimizedUrl ? optimizedFilename : filename}
              wireframe={wireframe}
              onModelReady={handleModelReady}
              onModelError={handleModelError}
              onCameraChange={handleCameraChange}
              performanceMode={performanceMode}
            />
          </Canvas>
        </div>
      )}

        {viewerError && <div className="error-msg" style={{ marginTop: 12 }}>{viewerError}</div>}
      </div>

      <ModelInspector
        modelSummary={modelSummary}
        fileStats={activeStats}
        camera={cameraInfo}
        mode={inspectorMode}
        currentFilename={activeFilename}
        darkMode={darkMode}
      />
    </div>
  )
}
