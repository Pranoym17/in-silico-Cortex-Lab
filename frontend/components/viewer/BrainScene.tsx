"use client";

import { Bounds, Center, OrbitControls, useGLTF } from "@react-three/drei";
import { Canvas, ThreeEvent } from "@react-three/fiber";
import { Component, ReactNode, Suspense, useEffect, useMemo, useState } from "react";
import * as THREE from "three";
import { BrainMeshManifest, HemisphereKey } from "@/lib/brainAssets";
import { ActivationDomain, buildHemisphereVertexColors } from "@/lib/brainActivation";
import { DecodedActivationChunk } from "@/lib/sse";

export type BrainPointerPosition = {
  x: number;
  y: number;
};

type BrainSceneProps = {
  manifest: BrainMeshManifest;
  chunk: DecodedActivationChunk | null;
  frameIndex?: number;
  showLeft?: boolean;
  showRight?: boolean;
  colorDomain?: ActivationDomain | null;
  onVertexClick?: (vertexIndex: number) => void;
  onVertexHover?: (vertexIndex: number | null, position: BrainPointerPosition | null) => void;
};

type HemisphereMeshProps = {
  colors: Float32Array;
  hemisphere: HemisphereKey;
  manifest: BrainMeshManifest;
  onVertexClick?: (vertexIndex: number) => void;
  onVertexHover?: (vertexIndex: number | null, position: BrainPointerPosition | null) => void;
  path: string;
};

export function BrainScene({
  manifest,
  chunk,
  frameIndex = 0,
  showLeft = true,
  showRight = true,
  colorDomain = null,
  onVertexClick,
  onVertexHover
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
          <Canvas camera={{ position: [0, -180, 70], fov: 42 }}>
            <color attach="background" args={["#101114"]} />
            <ambientLight intensity={0.85} />
            <directionalLight position={[2, 4, 5]} intensity={1.4} />
            <directionalLight position={[-4, -2, 3]} intensity={0.45} />
            <Bounds fit clip observe margin={1.75}>
              <Center>
                {showLeft ? (
                  <HemisphereMesh
                    colors={leftColors}
                    hemisphere="left"
                    manifest={manifest}
                    onVertexClick={onVertexClick}
                    onVertexHover={onVertexHover}
                    path={manifest.hemispheres.left.path}
                  />
                ) : null}
                {showRight ? (
                  <HemisphereMesh
                    colors={rightColors}
                    hemisphere="right"
                    manifest={manifest}
                    onVertexClick={onVertexClick}
                    onVertexHover={onVertexHover}
                    path={manifest.hemispheres.right.path}
                  />
                ) : null}
              </Center>
            </Bounds>
            <OrbitControls enableDamping makeDefault maxDistance={500} minDistance={10} />
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

function HemisphereMesh({ colors, hemisphere, manifest, onVertexClick, onVertexHover, path }: HemisphereMeshProps) {
  const gltf = useGLTF(path);
  const sourceMesh = useMemo(() => findFirstMesh(gltf.scene), [gltf.scene]);
  const geometry = useMemo(() => sourceMesh?.geometry.clone() ?? null, [sourceMesh]);
  const vertexStart = manifest.hemispheres[hemisphere].vertex_start;

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
    <mesh
      geometry={geometry}
      name={`${hemisphere}-hemisphere`}
      onClick={(event) => {
        const vertexIndex = getGlobalVertexIndexFromPointerEvent(event, vertexStart);
        if (vertexIndex === null) {
          return;
        }
        event.stopPropagation();
        onVertexClick?.(vertexIndex);
      }}
      onPointerMove={(event) => {
        const vertexIndex = getGlobalVertexIndexFromPointerEvent(event, vertexStart);
        if (vertexIndex === null) {
          onVertexHover?.(null, null);
          return;
        }
        event.stopPropagation();
        onVertexHover?.(vertexIndex, { x: event.nativeEvent.offsetX, y: event.nativeEvent.offsetY });
      }}
      onPointerOut={() => onVertexHover?.(null, null)}
    >
      <meshStandardMaterial roughness={0.82} metalness={0.03} vertexColors />
    </mesh>
  );
}

function getGlobalVertexIndexFromPointerEvent(
  event: ThreeEvent<PointerEvent | MouseEvent>,
  vertexStart: number
): number | null {
  const face = event.face;
  const mesh = event.object;
  if (!face || !(mesh instanceof THREE.Mesh) || !(mesh.geometry instanceof THREE.BufferGeometry)) {
    return null;
  }

  const localPoint = mesh.worldToLocal(event.point.clone());
  const localVertexIndex = getClosestFaceVertexIndex(mesh.geometry, face, localPoint);
  return localVertexIndex === null ? null : vertexStart + localVertexIndex;
}

function getClosestFaceVertexIndex(
  geometry: THREE.BufferGeometry,
  face: THREE.Face,
  localPoint: THREE.Vector3
): number | null {
  const position = geometry.getAttribute("position");
  if (!position) {
    return null;
  }

  const candidates = [face.a, face.b, face.c];
  let closestIndex: number | null = null;
  let closestDistance = Number.POSITIVE_INFINITY;
  const candidatePosition = new THREE.Vector3();

  for (const candidate of candidates) {
    if (candidate < 0 || candidate >= position.count) {
      continue;
    }
    candidatePosition.fromBufferAttribute(position, candidate);
    const distance = candidatePosition.distanceToSquared(localPoint);
    if (distance < closestDistance) {
      closestDistance = distance;
      closestIndex = candidate;
    }
  }

  return closestIndex;
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
