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

export type BrainRegionMetadata = {
  knownFunction: string;
  atlasDescription: string;
  notes: string;
};

export type BrainRegionPeak = {
  timestep: number | null;
  value: number;
};

export type BrainRegionConditionSummary = {
  condition: string;
  blockId: string;
  mean: number;
  peak: number;
  samples: number;
};

export type BrainRegionConditionComparison = {
  conditionA: string;
  conditionB: string;
  meanDifference: number;
  peakDifference: number;
  dominantCondition: string;
} | null;

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

export function getRegionPeak(points: readonly BrainRegionTimecoursePoint[]): BrainRegionPeak {
  if (points.length === 0) {
    return { timestep: null, value: 0 };
  }

  return points.reduce(
    (peak, point) => (Math.abs(point.mean) > Math.abs(peak.value) ? { timestep: point.timestep, value: point.mean } : peak),
    { timestep: points[0].timestep, value: points[0].mean }
  );
}

export function getRegionMetadata(regionLabel: string): BrainRegionMetadata {
  const normalized = stripHemispherePrefix(regionLabel).toLowerCase();
  const knownFunction = REGION_FUNCTIONS[normalized] ?? "General cortical processing; interpret with the active task context.";
  return {
    knownFunction,
    atlasDescription: "Desikan-Killiany aparc cortical label projected from FreeSurfer fsaverage to Nilearn fsaverage5.",
    notes: "Region activation is averaged over all vertices with this atlas label in the selected hemisphere."
  };
}

export function getRegionConditionSummaries(
  regionLabel: string,
  atlas: DesikanKillianyAtlas,
  manifest: BrainMeshManifest,
  chunks: readonly DecodedActivationChunk[],
  blockLabels: ReadonlyMap<string, string> = new Map()
): BrainRegionConditionSummary[] {
  const byBlock = new Map<string, { sum: number; peak: number; samples: number }>();

  for (const chunk of chunks) {
    if (!validateActivationChunkAgainstManifest(chunk, manifest).valid) {
      continue;
    }

    const current = byBlock.get(chunk.block_id) ?? { sum: 0, peak: 0, samples: 0 };
    for (let frameIndex = 0; frameIndex < chunk.timestep_count; frameIndex += 1) {
      const mean = getRegionActivationStats(regionLabel, atlas, manifest, chunk, frameIndex).mean;
      current.sum += mean;
      current.peak = Math.abs(mean) > Math.abs(current.peak) ? mean : current.peak;
      current.samples += 1;
    }
    byBlock.set(chunk.block_id, current);
  }

  return [...byBlock.entries()]
    .map(([blockId, summary], index) => ({
      condition: blockLabels.get(blockId) ?? `Block ${index + 1}`,
      blockId,
      mean: summary.samples > 0 ? summary.sum / summary.samples : 0,
      peak: summary.peak,
      samples: summary.samples
    }))
    .sort((left, right) => left.condition.localeCompare(right.condition));
}

export function compareTopConditions(
  summaries: readonly BrainRegionConditionSummary[]
): BrainRegionConditionComparison {
  if (summaries.length < 2) {
    return null;
  }

  const [first, second] = summaries;
  const meanDifference = first.mean - second.mean;
  const peakDifference = first.peak - second.peak;
  return {
    conditionA: first.condition,
    conditionB: second.condition,
    meanDifference,
    peakDifference,
    dominantCondition: first.mean === second.mean ? "tie" : first.mean > second.mean ? first.condition : second.condition
  };
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

function stripHemispherePrefix(regionLabel: string) {
  return regionLabel.replace(/^(Left|Right)-/, "");
}

const REGION_FUNCTIONS: Record<string, string> = {
  bankssts: "Social perception, language-adjacent temporal processing, and audiovisual integration.",
  caudalanteriorcingulate: "Cognitive control, conflict monitoring, and affective regulation.",
  caudalmiddlefrontal: "Executive control, working memory, and action planning.",
  cuneus: "Early visual processing.",
  entorhinal: "Memory encoding, navigation, and medial temporal lobe input/output.",
  frontalpole: "High-level planning, abstract reasoning, and prospective cognition.",
  fusiform: "Object, word, and face-form processing.",
  inferiorparietal: "Attention, semantic integration, and multisensory association.",
  inferiortemporal: "Higher-order visual object recognition.",
  insula: "Interoception, salience, affective processing, and task switching.",
  isthmuscingulate: "Default-mode and memory-related integration.",
  lateraloccipital: "Visual object and scene processing.",
  lateralorbitofrontal: "Reward, decision-making, and affective evaluation.",
  lingual: "Visual processing, shape, and letter/word-related visual features.",
  medialorbitofrontal: "Reward valuation, emotion, and decision context.",
  middletemporal: "Language, motion, and semantic processing.",
  parahippocampal: "Scene processing, contextual memory, and navigation.",
  paracentral: "Sensorimotor control for lower body representations.",
  parsopercularis: "Language production and phonological processing.",
  parsorbitalis: "Language, semantic selection, and orbitofrontal association.",
  parstriangularis: "Language production and controlled semantic retrieval.",
  pericalcarine: "Primary visual cortex.",
  postcentral: "Primary somatosensory processing.",
  posteriorcingulate: "Default-mode processing, memory, and self-referential cognition.",
  precentral: "Primary motor control.",
  precuneus: "Visuospatial imagery, self-referential cognition, and default-mode processing.",
  rostralanteriorcingulate: "Affective evaluation and emotion regulation.",
  rostralmiddlefrontal: "Executive function and working memory.",
  superiorfrontal: "Executive control, working memory, and self-generated thought.",
  superiorparietal: "Spatial attention and sensorimotor integration.",
  superiortemporal: "Auditory, language, and social perception processing.",
  supramarginal: "Phonological processing, attention, and sensorimotor integration.",
  temporalpole: "Semantic and socio-emotional memory.",
  transversetemporal: "Primary auditory cortex.",
  unknown: "Unlabeled or non-cortical atlas region."
};
