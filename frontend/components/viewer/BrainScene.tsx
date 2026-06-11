"use client";

import { OrbitControls, useGLTF } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { Component, ReactNode, Suspense, useEffect, useMemo, useState } from "react";
import * as THREE from "three";
import { BrainMeshManifest, HemisphereKey } from "@/lib/brainAssets";
import { ActivationDomain, buildHemisphereVertexColors } from "@/lib/brainActivation";
import { DecodedActivationChunk } from "@/lib/sse";

type BrainSceneProps = {
  manifest: BrainMeshManifest;
  chunk: DecodedActivationChunk | null;
  frameIndex?: number;
  showLeft?: boolean;
  showRight?: boolean;
  colorDomain?: ActivationDomain | null;
};

type HemisphereMeshProps = {
  colors: Float32Array;
  hemisphere: HemisphereKey;
  path: string;
  position: [number, number, number];
};

export function BrainScene({
  manifest,
  chunk,
  frameIndex = 0,
  showLeft = true,
  showRight = true,
  colorDomain = null
}: BrainSceneProps) {
  const leftColors = useMemo(
    () => buildHemisphereVertexColors(chunk, manifest, "left", frameIndex, colorDomain),
    [chunk, colorDomain, frameIndex, manifest]
  );
  const rightColors = useMemo(
    () => buildHemisphereVertexColors(chunk, manifest, "right", frameIndex, colorDomain),
    [chunk, colorDomain, frameIndex, manifest]
  );
  const [webglAvailable, setWebglAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    setWebglAvailable(canCreateWebGLContext());
  }, []);

  if (webglAvailable === false) {
    return <BrainSceneFallback reason="WebGL is unavailable in this browser session." />;
  }

  return (
    <div className="brain-scene" aria-label="3D brain activation viewer">
      <WebGLErrorBoundary>
        <Suspense fallback={<div className="brain-loading">Loading brain mesh</div>}>
          <Canvas camera={{ position: [0, 0.5, 5.25], fov: 42 }}>
            <color attach="background" args={["#101114"]} />
            <ambientLight intensity={0.85} />
            <directionalLight position={[2, 4, 5]} intensity={1.4} />
            <directionalLight position={[-4, -2, 3]} intensity={0.45} />
            {showLeft ? (
              <HemisphereMesh
                colors={leftColors}
                hemisphere="left"
                path={manifest.hemispheres.left.path}
                position={showRight ? [-0.72, 0, 0] : [0, 0, 0]}
              />
            ) : null}
            {showRight ? (
              <HemisphereMesh
                colors={rightColors}
                hemisphere="right"
                path={manifest.hemispheres.right.path}
                position={showLeft ? [0.72, 0, 0] : [0, 0, 0]}
              />
            ) : null}
            <OrbitControls enableDamping makeDefault maxDistance={8} minDistance={2.1} />
          </Canvas>
        </Suspense>
      </WebGLErrorBoundary>
    </div>
  );
}

class WebGLErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error): { error: Error } {
    return { error };
  }

  render() {
    if (this.state.error) {
      return <BrainSceneFallback reason={this.state.error.message} />;
    }

    return this.props.children;
  }
}

function BrainSceneFallback({ reason }: { reason: string }) {
  return (
    <div className="brain-webgl-fallback" role="status">
      <strong>3D viewer unavailable</strong>
      <p>{reason}</p>
      <p>Streaming diagnostics remain available in the sidebar.</p>
    </div>
  );
}

function HemisphereMesh({ colors, hemisphere, path, position }: HemisphereMeshProps) {
  const gltf = useGLTF(path);
  const sourceMesh = useMemo(() => findFirstMesh(gltf.scene), [gltf.scene]);
  const geometry = useMemo(() => sourceMesh?.geometry.clone() ?? null, [sourceMesh]);

  useEffect(() => {
    if (!geometry) {
      return;
    }

    const positionAttribute = geometry.getAttribute("position");
    if (!positionAttribute || positionAttribute.count !== colors.length / 3) {
      return;
    }

    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geometry.attributes.color.needsUpdate = true;
    geometry.computeVertexNormals();
  }, [colors, geometry]);

  useEffect(() => {
    return () => {
      geometry?.dispose();
    };
  }, [geometry]);

  if (!geometry) {
    return null;
  }

  return (
    <mesh geometry={geometry} name={`${hemisphere}-hemisphere`} position={position}>
      <meshStandardMaterial roughness={0.82} metalness={0.03} vertexColors />
    </mesh>
  );
}

function findFirstMesh(object: THREE.Object3D): THREE.Mesh<THREE.BufferGeometry> | null {
  let mesh: THREE.Mesh<THREE.BufferGeometry> | null = null;

  object.traverse((child) => {
    if (!mesh && child instanceof THREE.Mesh && child.geometry instanceof THREE.BufferGeometry) {
      mesh = child as THREE.Mesh<THREE.BufferGeometry>;
    }
  });

  return mesh;
}

function canCreateWebGLContext() {
  if (typeof document === "undefined") {
    return false;
  }

  const canvas = document.createElement("canvas");
  const context = canvas.getContext("webgl2") ?? canvas.getContext("webgl") ?? canvas.getContext("experimental-webgl");
  if (context && "getExtension" in context) {
    const loseContext = context.getExtension("WEBGL_lose_context");
    loseContext?.loseContext();
  }
  return Boolean(context);
}
