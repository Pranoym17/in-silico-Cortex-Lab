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
            camera={{ position: [0, -185, 68], fov: 42 }}
            dpr={[1, 1.75]}
            gl={{ antialias: true, preserveDrawingBuffer: true }}
          >
            <color attach="background" args={["#f5f6f1"]} />
            <ambientLight intensity={1.5} />
            <directionalLight color="#fff7ec" intensity={2.1} position={[3, 4, 5]} />
            <directionalLight color="#9bb6d3" intensity={0.8} position={[-4, -2, 3]} />
            <pointLight color="#d66a48" intensity={14} position={[0, -2, 4]} />
            <Bounds fit clip observe margin={1.16}>
              <Center>
                <group rotation={[0.1, 0.42, 0]}>
                  <HeroHemisphere path={HEMISPHERE_PATHS.left} side="left" />
                  <HeroHemisphere path={HEMISPHERE_PATHS.right} side="right" />
                </group>
              </Center>
            </Bounds>
            <OrbitControls
              autoRotate
              autoRotateSpeed={0.42}
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
  const baseColor = side === "left" ? "#d4e4db" : "#e9d9c6";

  clone.traverse((node) => {
    if (!(node instanceof THREE.Mesh) || !(node.geometry instanceof THREE.BufferGeometry)) {
      return;
    }

    node.geometry = node.geometry.clone();
    node.material = new THREE.MeshPhysicalMaterial({
      color: baseColor,
      roughness: 0.54,
      metalness: 0.02,
      clearcoat: 0.12,
      clearcoatRoughness: 0.6
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
