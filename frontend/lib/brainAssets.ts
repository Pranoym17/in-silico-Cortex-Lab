export type HemisphereKey = "left" | "right";

export type BrainHemisphereManifest = {
  file: string;
  vertex_count: number;
  activation_offset: number;
};

export type BrainMeshManifest = {
  surface: "fsaverage5";
  vertex_count: number;
  left_vertex_count: number;
  right_vertex_count: number;
  ordering: "left-then-right";
  atlas: "desikan-killiany";
  gltf: Record<HemisphereKey, string>;
  hemispheres: Record<HemisphereKey, BrainHemisphereManifest>;
};

export type DesikanKillianyAtlas = Record<string, string>;

export async function loadBrainManifest(fetcher: typeof fetch = fetch): Promise<BrainMeshManifest> {
  const response = await fetcher("/brain/mesh-manifest.json");
  if (!response.ok) {
    throw new Error(`Failed to load brain mesh manifest: ${response.status}`);
  }
  return validateBrainManifest(await response.json());
}

export async function loadBrainAtlas(fetcher: typeof fetch = fetch): Promise<DesikanKillianyAtlas> {
  const response = await fetcher("/brain/atlas-desikan-killiany.json");
  if (!response.ok) {
    throw new Error(`Failed to load Desikan-Killiany atlas: ${response.status}`);
  }
  return validateBrainAtlas(await response.json());
}

export function validateBrainManifest(value: unknown): BrainMeshManifest {
  if (!isRecord(value)) {
    throw new Error("Brain mesh manifest must be an object");
  }

  const manifest = value as Partial<BrainMeshManifest>;
  if (manifest.surface !== "fsaverage5") {
    throw new Error("Brain mesh manifest surface must be fsaverage5");
  }
  if (manifest.atlas !== "desikan-killiany") {
    throw new Error("Brain mesh manifest atlas must be desikan-killiany");
  }
  if (manifest.ordering !== "left-then-right") {
    throw new Error("Brain mesh manifest ordering must be left-then-right");
  }
  if (!isPositiveInteger(manifest.left_vertex_count) || !isPositiveInteger(manifest.right_vertex_count)) {
    throw new Error("Brain mesh manifest hemisphere vertex counts must be positive integers");
  }
  if (manifest.vertex_count !== manifest.left_vertex_count + manifest.right_vertex_count) {
    throw new Error("Brain mesh manifest total vertex count must equal left plus right");
  }
  if (!isRecord(manifest.gltf) || typeof manifest.gltf.left !== "string" || typeof manifest.gltf.right !== "string") {
    throw new Error("Brain mesh manifest must include left and right GLTF paths");
  }
  if (!isRecord(manifest.hemispheres)) {
    throw new Error("Brain mesh manifest must include hemisphere metadata");
  }

  validateHemisphere("left", manifest.hemispheres.left, manifest.left_vertex_count, 0);
  validateHemisphere("right", manifest.hemispheres.right, manifest.right_vertex_count, manifest.left_vertex_count);
  return manifest as BrainMeshManifest;
}

export function validateBrainAtlas(value: unknown): DesikanKillianyAtlas {
  if (!isRecord(value)) {
    throw new Error("Brain atlas must be an object");
  }

  for (const [vertexIndex, label] of Object.entries(value)) {
    if (!/^\d+$/.test(vertexIndex) || typeof label !== "string" || !label.trim()) {
      throw new Error("Brain atlas must map numeric vertex indices to region names");
    }
  }

  return value as DesikanKillianyAtlas;
}

function validateHemisphere(
  key: HemisphereKey,
  value: unknown,
  expectedVertexCount: number,
  expectedActivationOffset: number
) {
  if (!isRecord(value)) {
    throw new Error(`Brain mesh manifest missing ${key} hemisphere metadata`);
  }
  if (typeof value.file !== "string" || !value.file.endsWith(`fsaverage5_${key}.gltf`)) {
    throw new Error(`Brain mesh manifest ${key} hemisphere file path is invalid`);
  }
  if (value.vertex_count !== expectedVertexCount) {
    throw new Error(`Brain mesh manifest ${key} vertex count does not match top-level count`);
  }
  if (value.activation_offset !== expectedActivationOffset) {
    throw new Error(`Brain mesh manifest ${key} activation offset is invalid`);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isPositiveInteger(value: unknown): value is number {
  return Number.isInteger(value) && Number(value) > 0;
}
