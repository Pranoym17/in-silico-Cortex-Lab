import { getActivationFrame, validateActivationChunkAgainstManifest } from "./brainActivation";
import { BrainMeshManifest, DesikanKillianyAtlas, HemisphereKey } from "./brainAssets";
import { DecodedActivationChunk } from "./sse";

export type BrainRegionInfo = {
  vertexIndex: number;
  label: string;
  hemisphere: HemisphereKey;
};

export type BrainRegionActivationStats = {
  label: string;
  hemisphere: HemisphereKey | "bilateral";
  vertexCount: number;
  min: number;
  max: number;
  mean: number;
  absoluteMax: number;
};

export type BrainRegionTimecoursePoint = {
  timestep: number;
  mean: number;
  vertexCount: number;
};

const EMPTY_STATS = {
  vertexCount: 0,
  min: 0,
  max: 0,
  mean: 0,
  absoluteMax: 0
};

export function getHemisphereForVertex(
  vertexIndex: number,
  manifest: BrainMeshManifest
): HemisphereKey | null {
  if (!Number.isInteger(vertexIndex) || vertexIndex < 0) {
    return null;
  }

  for (const hemisphere of ["left", "right"] as const) {
    const metadata = manifest.hemispheres[hemisphere];
    const end = metadata.vertex_start + metadata.vertex_count;
    if (vertexIndex >= metadata.vertex_start && vertexIndex < end) {
      return hemisphere;
    }
  }

  return null;
}

export function getRegionForVertex(
  atlas: DesikanKillianyAtlas,
  manifest: BrainMeshManifest,
  vertexIndex: number
): BrainRegionInfo | null {
  const hemisphere = getHemisphereForVertex(vertexIndex, manifest);
  const label = atlas[String(vertexIndex)];
  if (!hemisphere || !label) {
    return null;
  }

  return { vertexIndex, label, hemisphere };
}

export function getRegionVertices(atlas: DesikanKillianyAtlas, regionLabel: string): number[] {
  return Object.entries(atlas)
    .filter(([, label]) => label === regionLabel)
    .map(([vertexIndex]) => Number(vertexIndex))
    .filter(Number.isInteger)
    .sort((left, right) => left - right);
}

export function getRegionLabels(atlas: DesikanKillianyAtlas): string[] {
  return [...new Set(Object.values(atlas))].sort((left, right) => left.localeCompare(right));
}

export function getRegionActivationStats(
  regionLabel: string,
  atlas: DesikanKillianyAtlas,
  manifest: BrainMeshManifest,
  chunk: DecodedActivationChunk | null,
  frameIndex = 0
): BrainRegionActivationStats {
  const vertices = getRegionVertices(atlas, regionLabel);
  if (!chunk || vertices.length === 0 || !validateActivationChunkAgainstManifest(chunk, manifest).valid) {
    return { label: regionLabel, hemisphere: inferRegionHemisphere(vertices, manifest), ...EMPTY_STATS };
  }

  const frame = getActivationFrame(chunk, frameIndex);
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  let sum = 0;
  let absoluteMax = 0;
  let counted = 0;

  for (const vertexIndex of vertices) {
    const value = frame[vertexIndex];
    if (!Number.isFinite(value)) {
      continue;
    }
    min = Math.min(min, value);
    max = Math.max(max, value);
    sum += value;
    absoluteMax = Math.max(absoluteMax, Math.abs(value));
    counted += 1;
  }

  if (counted === 0) {
    return { label: regionLabel, hemisphere: inferRegionHemisphere(vertices, manifest), ...EMPTY_STATS };
  }

  return {
    label: regionLabel,
    hemisphere: inferRegionHemisphere(vertices, manifest),
    vertexCount: counted,
    min,
    max,
    mean: sum / counted,
    absoluteMax
  };
}

export function getRegionTimecourse(
  regionLabel: string,
  atlas: DesikanKillianyAtlas,
  manifest: BrainMeshManifest,
  chunks: readonly DecodedActivationChunk[]
): BrainRegionTimecoursePoint[] {
  const points: BrainRegionTimecoursePoint[] = [];

  for (const chunk of chunks) {
    if (!validateActivationChunkAgainstManifest(chunk, manifest).valid) {
      continue;
    }

    for (let frameIndex = 0; frameIndex < chunk.timestep_count; frameIndex += 1) {
      const stats = getRegionActivationStats(regionLabel, atlas, manifest, chunk, frameIndex);
      points.push({
        timestep: chunk.timestep_start + frameIndex,
        mean: stats.mean,
        vertexCount: stats.vertexCount
      });
    }
  }

  return points;
}

function inferRegionHemisphere(
  vertices: readonly number[],
  manifest: BrainMeshManifest
): HemisphereKey | "bilateral" {
  const hemispheres = new Set<HemisphereKey>();
  for (const vertexIndex of vertices) {
    const hemisphere = getHemisphereForVertex(vertexIndex, manifest);
    if (hemisphere) {
      hemispheres.add(hemisphere);
    }
  }

  if (hemispheres.size === 1) {
    return [...hemispheres][0];
  }

  return "bilateral";
}
