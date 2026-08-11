import React, { useRef, useState, useLayoutEffect, useMemo, Suspense, useEffect } from 'react'
import * as THREE from 'three'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Environment, OrbitControls, useGLTF, Float, ContactShadows } from '@react-three/drei'

// Preload the specific hero models
useGLTF.preload('/models/herodemoreal.glb')
useGLTF.preload('/models/herodemoreal_optimized.glb')

function Models({ sliderRef }) {
  const { scene: sceneOriginal } = useGLTF('/models/herodemoreal.glb')
  const { scene: sceneOptimized } = useGLTF('/models/herodemoreal_optimized.glb')
  
  const { camera } = useThree()
  const groupRef = useRef()
  
  const clipRight = useMemo(() => new THREE.Plane(new THREE.Vector3(-1, 0, 0), 0), [])
  const clipLeft = useMemo(() => new THREE.Plane(new THREE.Vector3(1, 0, 0), 0), [])

  useLayoutEffect(() => {
    sceneOriginal.traverse((child) => {
      if (child.isMesh) {
        child.material = child.material.clone()
        child.material.clippingPlanes = [clipRight]
        child.material.clipShadows = true
        child.material.needsUpdate = true
      }
    })
    
    sceneOptimized.traverse((child) => {
      if (child.isMesh) {
        // Create a bright, unlit material for the wireframe so it pops against the dark bg
        child.material = new THREE.MeshBasicMaterial({
          color: new THREE.Color('#00E5FF'), // Neon Cyan for stark contrast
          wireframe: true,
          transparent: true,
          opacity: 0.4, // Slight transparency so it's not overwhelmingly dense
          clippingPlanes: [clipLeft]
        })
      }
    })
  }, [sceneOriginal, sceneOptimized, clipRight, clipLeft])

  useFrame((state) => {
    // Read directly from ref to avoid React render cycle overhead (zero lag)
    const val = sliderRef.current
    const screenX = (val / 100) * 2 - 1
    
    const vec = new THREE.Vector3(screenX, 0, 0.5)
    vec.unproject(camera)
    vec.sub(camera.position).normalize()
    
    const t = -camera.position.z / vec.z
    const worldX = camera.position.x + vec.x * t
    
    clipRight.constant = worldX
    clipLeft.constant = -worldX
  })

  return (
    <group ref={groupRef} position={[0, -1.3, 0]} scale={3.8}>
      <primitive object={sceneOriginal} />
      <primitive object={sceneOptimized} />
    </group>
  )
}

function Loader() {
  return (
    <mesh>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color="#FF3B3B" wireframe />
    </mesh>
  )
}

export default function Hero3DComparison() {
  // Use refs instead of state for buttery-smooth native DOM updates without re-renders
  const sliderRef = useRef(50)
  const thumbRef = useRef(null)

  const [inViewRef, setInViewRef] = useState(null)
  const [inView, setInView] = useState(true)

  useEffect(() => {
    if (!inViewRef) return
    const observer = new IntersectionObserver(([entry]) => {
      setInView(entry.isIntersecting)
    }, { rootMargin: '400px' })
    observer.observe(inViewRef)
    return () => observer.disconnect()
  }, [inViewRef])

  return (
    <div ref={setInViewRef} className="absolute inset-0 w-full h-full z-0 overflow-hidden pointer-events-auto">
      
      {/* 3D Canvas */}
      {!inView && (
        <div className="absolute inset-0 flex flex-col items-center justify-center z-10 pointer-events-none">
          <div className="w-8 h-8 border-4 border-[#FF3B3B]/20 border-t-[#FF3B3B] rounded-full animate-spin" />
        </div>
      )}

      {inView && (
        <Canvas
          camera={{ position: [0, 0, 5], fov: 45 }}
          gl={{ antialias: true, alpha: true, localClippingEnabled: true, powerPreference: "default" }}
          dpr={[1, 1.5]}
        >
          <ambientLight intensity={1.5} />
          <spotLight position={[5, 10, 5]} intensity={3} penumbra={1} angle={0.5} />
          <directionalLight position={[-5, 5, -5]} intensity={1} />
          
          <Suspense fallback={<Loader />}>
            <Models sliderRef={sliderRef} />
          </Suspense>
          
          <ContactShadows position={[0, -2.6, 0]} opacity={0.5} scale={10} blur={2} />
          <Environment preset="city" />
        </Canvas>
      )}

      {/* HTML Slider UI Overlay */}
      <div className="absolute top-1/2 left-0 w-full -translate-y-1/2 z-20 px-[20px] md:px-[50px]">
        <input
          type="range"
          min="0"
          max="100"
          defaultValue={50}
          onInput={(e) => {
            const val = e.target.value
            sliderRef.current = val
            e.target.style.background = `linear-gradient(to right, rgba(255,59,59,0.2) ${val}%, rgba(255,255,255,0.1) ${val}%)`
            if (thumbRef.current) {
              thumbRef.current.style.left = `calc(${val}% + 20px - (${val} * 0.4px))`
            }
          }}
          className="comparison-slider w-full h-2 bg-white/10 rounded-full appearance-none cursor-ew-resize outline-none"
          style={{
            WebkitAppearance: 'none',
            background: `linear-gradient(to right, rgba(255,59,59,0.2) 50%, rgba(255,255,255,0.1) 50%)`
          }}
        />
        
        <div 
          ref={thumbRef}
          className="absolute top-1/2 -translate-y-1/2 w-[2px] h-[200px] bg-[#FF3B3B] pointer-events-none"
          style={{ left: `calc(50% + 20px - (50 * 0.4px))` }}
        >
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-8 rounded-full border-2 border-[#FF3B3B] bg-[#0A0A0A] flex flex-col items-center justify-center gap-[2px] shadow-[0_0_15px_rgba(255,59,59,0.5)]">
            <div className="w-[2px] h-3 bg-[#FF3B3B] opacity-80" />
          </div>
        </div>

        <div className="absolute top-[20px] w-full left-0 px-[20px] md:px-[50px] flex justify-between pointer-events-none">
           <span className="text-[12px] font-bold tracking-widest text-[#F2F2F2] uppercase bg-[#0A0A0A]/50 backdrop-blur-md px-3 py-1 rounded border border-white/5 shadow-lg">Original Scan</span>
           <span className="text-[12px] font-bold tracking-widest text-[#FF3B3B] uppercase bg-[#0A0A0A]/50 backdrop-blur-md px-3 py-1 rounded border border-[#FF3B3B]/30 shadow-[0_0_10px_rgba(255,59,59,0.2)]">Optimized LOD</span>
        </div>
      </div>

      <style jsx>{`
        .comparison-slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          width: 32px;
          height: 32px;
          border-radius: 50%;
          background: transparent;
          cursor: ew-resize;
        }
        .comparison-slider::-moz-range-thumb {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          background: transparent;
          cursor: ew-resize;
          border: none;
        }
      `}</style>
    </div>
  )
}
