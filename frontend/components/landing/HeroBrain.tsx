"use client";

import { Bounds, Center, OrbitControls, useGLTF } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { Component, ReactNode, Suspense, useEffect, useMemo, useState } from "react";
import * as THREE from "three";
import { BrainCircuit } from "lucide-react";

type HemisphereSide = "left" | "right";

const HEMISPHERE_PATHS: Record<HemisphereSide, string> = {
  left: "/brain/fsaverage5_left.gltf",
  right: "/brain/fsaverage5_right.gltf"
};

export function HeroBrain() {
  const [webglAvailable, setWebglAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    setWebglAvailable(canCreateWebGLContext());
  }, []);

  if (webglAvailable === false) {
    return <HeroBrainFallback />;
  }

  return (
    <div className="landing-brain-canvas" aria-label="Interactive fsaverage5 cortical surface">
      <HeroBrainErrorBoundary>
        <Suspense fallback={<HeroBrainLoading />}>
          <Canvas
            camera={{ position: [0, -172, 64], fov: 40 }}
            dpr={[1, 1.75]}
            gl={{ antialias: true, preserveDrawingBuffer: true }}
          >
            <color attach="background" args={["#f4f8fb"]} />
            <ambientLight intensity={1.08} />
            <hemisphereLight args={["#eff3ff", "#25182b", 1.2]} />
            <directionalLight color="#ffffff" intensity={2.6} position={[3, 4, 5]} />
            <directionalLight color="#ee506a" intensity={1.3} position={[-4, -2, 3]} />
            <directionalLight color="#4f80ed" intensity={1.3} position={[3, -3, 2]} />
            <pointLight color="#e63f63" intensity={11} position={[0, -2, 4]} />
            <pointLight color="#5d86f2" intensity={10} position={[1, 3, -1]} />
            <Bounds fit clip observe margin={0.84}>
              <Center>
                <group rotation={[0.1, 0.42, 0]}>
                  <HeroHemisphere path={HEMISPHERE_PATHS.left} side="left" />
                  <HeroHemisphere path={HEMISPHERE_PATHS.right} side="right" />
                </group>
              </Center>
            </Bounds>
            <OrbitControls
              autoRotate
              autoRotateSpeed={0.52}
              enablePan={false}
              enableZoom
              maxDistance={480}
              minDistance={36}
              minPolarAngle={0.75}
              maxPolarAngle={2.35}
            />
          </Canvas>
        </Suspense>
      </HeroBrainErrorBoundary>
    </div>
  );
}

function HeroHemisphere({ path, side }: { path: string; side: HemisphereSide }) {
  const gltf = useGLTF(path);
  const brain = useMemo(() => createPresentationBrain(gltf.scene, side), [gltf.scene, side]);

  useEffect(() => {
    return () => disposePresentationBrain(brain);
  }, [brain]);

  return <primitive object={brain} />;
}

function createPresentationBrain(source: THREE.Object3D, side: HemisphereSide) {
  const clone = source.clone(true);
  const baseColor = side === "left" ? "#e54862" : "#4f7ee8";
  const emissiveColor = side === "left" ? "#4c0718" : "#10185e";

  clone.traverse((node) => {
    if (!(node instanceof THREE.Mesh) || !(node.geometry instanceof THREE.BufferGeometry)) {
      return;
    }

    node.geometry = node.geometry.clone();
    node.material = new THREE.MeshPhysicalMaterial({
      color: baseColor,
      emissive: emissiveColor,
      emissiveIntensity: 0.14,
      roughness: 0.27,
      metalness: 0.08,
      clearcoat: 0.48,
      clearcoatRoughness: 0.3,
      transparent: true,
      opacity: 0.93
    });
    node.castShadow = true;
    node.receiveShadow = true;
  });

  return clone;
}

function disposePresentationBrain(brain: THREE.Object3D) {
  brain.traverse((node) => {
    if (!(node instanceof THREE.Mesh)) {
      return;
    }

    node.geometry.dispose();
    const materials = Array.isArray(node.material) ? node.material : [node.material];
    materials.forEach((material) => material.dispose());
  });
}

class HeroBrainErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return <HeroBrainFallback />;
    }

    return this.props.children;
  }
}

function HeroBrainLoading() {
  return (
    <div className="landing-brain-fallback landing-brain-loading" role="status">
      <BrainCircuit aria-hidden="true" size={30} strokeWidth={1.35} />
      <span>Loading cortical surface</span>
    </div>
  );
}

function HeroBrainFallback() {
  return (
    <div className="landing-brain-fallback" role="img" aria-label="Cortical surface preview unavailable">
      <BrainCircuit aria-hidden="true" size={46} strokeWidth={1.15} />
      <span>Interactive cortical surface</span>
    </div>
  );
}

function canCreateWebGLContext() {
  if (typeof document === "undefined") {
    return false;
  }

  const canvas = document.createElement("canvas");
  const context = canvas.getContext("webgl2") ?? canvas.getContext("webgl") ?? canvas.getContext("experimental-webgl");
  if (context && "getExtension" in context) {
    context.getExtension("WEBGL_lose_context")?.loseContext();
  }
  return Boolean(context);
}

useGLTF.preload(HEMISPHERE_PATHS.left);
useGLTF.preload(HEMISPHERE_PATHS.right);
