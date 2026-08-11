import React, { useRef, useLayoutEffect, useMemo, useState, useEffect, Suspense } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { useGLTF, Float, Environment, ContactShadows, Html, Center, PerspectiveCamera } from '@react-three/drei'
import * as THREE from 'three'

// Optimization: Only run WebGL context and render loop when the canvas is actually visible on screen
function ViewportCanvas({ children, ...props }) {
  const [ref, setRef] = useState(null)
  const [inView, setInView] = useState(false)

  useEffect(() => {
    if (!ref) return
    const observer = new IntersectionObserver(([entry]) => {
      setInView(entry.isIntersecting)
    }, { rootMargin: '200px' }) // Start rendering 200px before it comes into view
    observer.observe(ref)
    return () => observer.disconnect()
  }, [ref])

  return (
    <div ref={setRef} className="absolute inset-0 z-0 w-full h-full flex items-center justify-center">
      {/* Show loading spinner while mounting or if unmounted */}
      {!inView && (
        <div className="absolute inset-0 flex flex-col items-center justify-center z-10 pointer-events-none">
          <div className="w-6 h-6 border-2 border-[#FF3B3B]/20 border-t-[#FF3B3B] rounded-full animate-spin mb-2" />
          <span className="text-white/30 text-[10px] tracking-widest font-bold">STANDBY</span>
        </div>
      )}
      
      {/* Conditionally mount to completely free WebGL context on mobile/low-end devices */}
      {inView && (
        <Canvas dpr={[1, 1.5]} {...props}>
          <Suspense fallback={
            <Html center>
              <div className="flex flex-col items-center justify-center">
                <div className="w-6 h-6 border-2 border-[#00E5FF]/20 border-t-[#00E5FF] rounded-full animate-spin mb-2" />
                <span className="text-white/50 text-[10px] tracking-widest font-bold">LOADING</span>
              </div>
            </Html>
          }>
            {children}
          </Suspense>
        </Canvas>
      )}
    </div>
  )
}

function WireframeModel({ url, position = [0,0,0], scale = 1, color = '#FF3B3B', rotation = [0,0,0], speed = 0.2, label, opacity = 0.3 }) {
  const { scene } = useGLTF(url)
  const clone = useMemo(() => scene.clone(), [scene])
  const meshRef = useRef()

  useLayoutEffect(() => {
    clone.traverse((child) => {
      if (child.isMesh) {
        child.material = new THREE.MeshBasicMaterial({
          color: color,
          wireframe: true,
          transparent: true,
          opacity: opacity
        })
      }
    })
  }, [clone, color, opacity])

  // Removed animation for performance

  return (
    <group position={position}>
      <group ref={meshRef} rotation={rotation}>
        <Center scale={scale}>
          <primitive object={clone} />
        </Center>
      </group>
    </group>
  )
}

export function LODShowcase() {
  return (
    <div className="w-full h-full grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
      
      {/* Sub Card LOD 0 */}
      <div className="bg-white/5 border border-white/10 rounded-2xl relative overflow-hidden flex flex-col items-center justify-center min-h-[250px] hover:bg-white/10 transition-colors group/sub">
        <ViewportCanvas camera={{ position: [0, 0, 8], fov: 40 }}>
          <WireframeModel url="/models/optimised lods/lodmain_LOD0.glb" scale={4} color="#FF3B3B" opacity={0.4} />
        </ViewportCanvas>
        <div className="absolute bottom-4 z-10 px-4 py-1.5 rounded-full border border-white/20 bg-black/80 backdrop-blur-md shadow-2xl flex items-center justify-center whitespace-nowrap group-hover/sub:border-[#FF3B3B]/50 transition-colors">
          <span className="text-white font-bold text-[11px] tracking-widest uppercase">LOD 0 - 100%</span>
        </div>
      </div>

      {/* Sub Card LOD 1 */}
      <div className="bg-white/5 border border-white/10 rounded-2xl relative overflow-hidden flex flex-col items-center justify-center min-h-[250px] hover:bg-white/10 transition-colors group/sub">
        <ViewportCanvas camera={{ position: [0, 0, 8], fov: 40 }}>
          <WireframeModel url="/models/optimised lods/lodmain_LOD1.glb" scale={4} color="#00E5FF" opacity={0.6} />
        </ViewportCanvas>
        <div className="absolute bottom-4 z-10 px-4 py-1.5 rounded-full border border-white/20 bg-black/80 backdrop-blur-md shadow-2xl flex items-center justify-center whitespace-nowrap group-hover/sub:border-[#00E5FF]/50 transition-colors">
          <span className="text-white font-bold text-[11px] tracking-widest uppercase">LOD 1 - 50%</span>
        </div>
      </div>

      {/* Sub Card LOD 2 */}
      <div className="bg-white/5 border border-white/10 rounded-2xl relative overflow-hidden flex flex-col items-center justify-center min-h-[250px] hover:bg-white/10 transition-colors group/sub">
        <ViewportCanvas camera={{ position: [0, 0, 8], fov: 40 }}>
          <WireframeModel url="/models/optimised lods/lodmain_LOD2.glb" scale={4} color="#FF3B3B" opacity={0.8} />
        </ViewportCanvas>
        <div className="absolute bottom-4 z-10 px-4 py-1.5 rounded-full border border-white/20 bg-black/80 backdrop-blur-md shadow-2xl flex items-center justify-center whitespace-nowrap group-hover/sub:border-[#FF3B3B]/50 transition-colors">
          <span className="text-white font-bold text-[11px] tracking-widest uppercase">LOD 2 - 25%</span>
        </div>
      </div>

    </div>
  )
}

export function FeatureAwareShowcase() {
  return (
    <div className="absolute inset-0 w-full h-full pointer-events-none z-0 overflow-hidden rounded-[32px]">
      <ViewportCanvas camera={{ position: [0, 0, 5], fov: 45 }}>
        <Float speed={2} rotationIntensity={1} floatIntensity={1}>
           <WireframeModel url="/models/shoe.glb" position={[0, -0.5, 0]} scale={2} color="#FF3B3B" speed={0.5} />
        </Float>
      </ViewportCanvas>
    </div>
  )
}

export function PreprocessingShowcase() {
  return (
    <div className="absolute inset-0 w-full h-full pointer-events-none z-0 overflow-hidden rounded-[32px]">
      <ViewportCanvas camera={{ position: [0, 0, 5], fov: 45 }}>
        <Float speed={1.5} rotationIntensity={0.5} floatIntensity={1}>
           <WireframeModel url="/models/arvr.glb" position={[2, -1, -1]} scale={1.5} color="#ffffff" speed={0.3} />
        </Float>
      </ViewportCanvas>
      <div className="absolute inset-0 bg-gradient-to-r from-[#0A0A0A] via-[#0A0A0A]/80 to-transparent w-full md:w-1/2 z-10" />
    </div>
  )
}
