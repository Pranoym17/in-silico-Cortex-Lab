import { BrainMeshManifest, HemisphereKey } from "./brainAssets";
import { activationToRgb, inferActivationDomain } from "./colormap";
import { DecodedActivationChunk } from "./sse";

export type ActivationDomain = readonly [number, number];

export function getLatestActivationChunk(chunks: readonly DecodedActivationChunk[]): DecodedActivationChunk | null {
  return chunks.length > 0 ? chunks[chunks.length - 1] : null;
}

export function getStreamedTimestepCount(chunks: readonly DecodedActivationChunk[]): number {
  return chunks.reduce(
    (maxTimestep, chunk) => Math.max(maxTimestep, chunk.timestep_start + chunk.timestep_count),
    0
  );
}

export function getChunkForTimestep(
  chunks: readonly DecodedActivationChunk[],
  timestep: number
): DecodedActivationChunk | null {
  return (
    chunks.find((chunk) => timestep >= chunk.timestep_start && timestep < chunk.timestep_start + chunk.timestep_count) ??
    getLatestActivationChunk(chunks)
  );
}

export function getFrameIndexForTimestep(chunk: DecodedActivationChunk | null, timestep: number): number {
  if (!chunk) {
    return 0;
  }
  return Math.max(0, Math.min(timestep - chunk.timestep_start, chunk.timestep_count - 1));
}

export function getActivationFrame(chunk: DecodedActivationChunk, frameIndex = 0): Float32Array {
  const safeFrameIndex = Math.max(0, Math.min(frameIndex, chunk.timestep_count - 1));
  const start = safeFrameIndex * chunk.vertex_count;
  const end = start + chunk.vertex_count;
  return chunk.activations.slice(start, end);
}

export function getActivationDomain(
  chunk: DecodedActivationChunk | null,
  frameIndex = 0,
  overrideDomain?: ActivationDomain | null
): ActivationDomain {
  if (overrideDomain && isValidDomain(overrideDomain)) {
    return overrideDomain;
  }
  return chunk ? inferActivationDomain(getActivationFrame(chunk, frameIndex)) : [-1, 1];
}

export function getHemisphereActivationFrame(
  chunk: DecodedActivationChunk | null,
  manifest: BrainMeshManifest,
  hemisphere: HemisphereKey,
  frameIndex = 0
): Float32Array {
  const metadata = manifest.hemispheres[hemisphere];
  if (!chunk || chunk.vertex_count < metadata.activation_offset + metadata.vertex_count) {
    return new Float32Array(metadata.vertex_count);
  }

  const frame = getActivationFrame(chunk, frameIndex);
  return frame.slice(metadata.activation_offset, metadata.activation_offset + metadata.vertex_count);
}

export function buildVertexColorBuffer(
  values: Float32Array,
  domain: ActivationDomain = inferActivationDomain(values)
): Float32Array {
  const colors = new Float32Array(values.length * 3);

  for (let index = 0; index < values.length; index += 1) {
    const [red, green, blue] = activationToRgb(values[index], domain);
    const colorOffset = index * 3;
    colors[colorOffset] = red;
    colors[colorOffset + 1] = green;
    colors[colorOffset + 2] = blue;
  }

  return colors;
}

export function buildHemisphereVertexColors(
  chunk: DecodedActivationChunk | null,
  manifest: BrainMeshManifest,
  hemisphere: HemisphereKey,
  frameIndex = 0,
  domain?: ActivationDomain | null
): Float32Array {
  const values = getHemisphereActivationFrame(chunk, manifest, hemisphere, frameIndex);
  return buildVertexColorBuffer(values, getActivationDomain(chunk, frameIndex, domain));
}

function isValidDomain(domain: ActivationDomain) {
  return Number.isFinite(domain[0]) && Number.isFinite(domain[1]) && domain[0] < domain[1];
}
