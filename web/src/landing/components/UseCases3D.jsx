import React, { useRef, Suspense, useState, useEffect } from 'react'
import * as THREE from 'three'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Environment, Float, useGLTF, ContactShadows } from '@react-three/drei'

// Preload models
useGLTF.preload('/models/gaming.glb')
useGLTF.preload('/models/shoe.glb')
useGLTF.preload('/models/arvr.glb')
useGLTF.preload('/models/house.glb')

// Custom Loader
function Loader() {
  return (
    <mesh position={[-0.5, 0, 0]}>
      <boxGeometry args={[0.5, 0.5, 0.5]} />
      <meshStandardMaterial color="#FF3B3B" wireframe />
    </mesh>
  )
}

// 1. Gaming Scene (using DamagedHelmet)
export function GamingScene() {
  const { scene } = useGLTF('/models/gaming.glb')
  const ref = useRef()
  
  return (
    <>
      <ambientLight intensity={1} />
      <directionalLight position={[5, 5, 5]} intensity={2} />
      <Suspense fallback={<Loader />}>
        <primitive ref={ref} object={scene} scale={1.2} position={[0, 0, 0]} />
      </Suspense>
      <Environment preset="city" />
      <OrbitControls enableZoom={false} target={[0, 0, 0]} />
    </>
  )
}

// 2. Ecommerce Scene (using Shoe)
export function EcommerceScene() {
  const { scene } = useGLTF('/models/shoe.glb')
  const ref = useRef()
  
  return (
    <>
      <ambientLight intensity={2} />
      <spotLight position={[0, 5, 5]} intensity={3} angle={0.5} penumbra={1} />
      <Suspense fallback={<Loader />}>
        <primitive ref={ref} object={scene} scale={14} position={[0, -0.8, 0]} />
      </Suspense>
      <ContactShadows position={[0, -1.8, 0]} opacity={0.5} scale={5} blur={2} />
      <Environment preset="studio" />
      <OrbitControls enableZoom={false} target={[0, 0, 0]} />
    </>
  )
}

// 3. AR/VR Scene (using ToyCar)
export function ARVRScene() {
  const { scene } = useGLTF('/models/arvr.glb')
  const ref = useRef()
  
  return (
    <>
      <ambientLight intensity={1} />
      <directionalLight position={[5, 10, 5]} intensity={1.5} />
      <Suspense fallback={<Loader />}>
        <primitive ref={ref} object={scene} scale={80} position={[0, 0, 0]} />
      </Suspense>
      <ContactShadows position={[0, -0.5, 0]} opacity={0.4} scale={5} blur={1} />
      <Environment preset="city" />
      <OrbitControls enableZoom={false} target={[0, 0, 0]} />
    </>
  )
}

// 4. Archviz Scene (using LittlestTokyo)
export function ArchvizScene() {
  const { scene } = useGLTF('/models/house.glb')
  const ref = useRef()

  return (
    <>
      <ambientLight intensity={2} />
      <directionalLight position={[5, 10, 5]} intensity={1.5} />
      <Suspense fallback={<Loader />}>
         <primitive ref={ref} object={scene} scale={0.005} position={[0, -0.3, 0]} />
      </Suspense>
      <Environment preset="city" />
      <OrbitControls enableZoom={false} target={[0, 0, 0]} maxPolarAngle={Math.PI / 2} />
    </>
  )
}

export function UseCaseCanvas({ type }) {
  const [inViewRef, setInViewRef] = useState(null)
  const [inView, setInView] = useState(false)

  useEffect(() => {
    if (!inViewRef) return
    const observer = new IntersectionObserver(([entry]) => {
      setInView(entry.isIntersecting)
    }, { rootMargin: '200px' })
    observer.observe(inViewRef)
    return () => observer.disconnect()
  }, [inViewRef])

  return (
    <div ref={setInViewRef} className="w-full h-full absolute inset-0 rounded-[24px] overflow-hidden pointer-events-auto cursor-grab active:cursor-grabbing opacity-90 transition-opacity hover:opacity-100 z-0 flex items-center justify-center">
      {!inView && (
        <div className="absolute inset-0 flex flex-col items-center justify-center z-10 pointer-events-none">
          <div className="w-6 h-6 border-2 border-[#FF3B3B]/20 border-t-[#FF3B3B] rounded-full animate-spin mb-2" />
          <span className="text-white/30 text-[10px] tracking-widest font-bold">STANDBY</span>
        </div>
      )}

      {inView && (
        <Canvas camera={{ position: [0, 0, 5], fov: 45 }} gl={{ antialias: true, alpha: true, powerPreference: "default" }} dpr={[1, 1.5]}>
          {type === 'gaming' && <GamingScene />}
          {type === 'ecommerce' && <EcommerceScene />}
          {type === 'arvr' && <ARVRScene />}
          {type === 'archviz' && <ArchvizScene />}
        </Canvas>
      )}
    </div>
  )
}
