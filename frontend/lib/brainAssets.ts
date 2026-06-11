export type HemisphereKey = "left" | "right";

export type BrainHemisphereManifest = {
  path: string;
  file: string;
  vertex_start: number;
  vertex_count: number;
  activation_offset: number;
};

export type BrainMeshManifest = {
  source?: string;
  atlas_source?: string;
  surface: "fsaverage5";
  vertex_order: "left_then_right";
  total_vertex_count: number;
  vertex_count: number;
  left_vertex_count: number;
  right_vertex_count: number;
  ordering: "left-then-right";
  ordering_rule?: string;
  coordinate_units?: "millimeters";
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
  if (manifest.vertex_order !== "left_then_right") {
    throw new Error("Brain mesh manifest vertex order must be left_then_right");
  }
  if (manifest.atlas !== "desikan-killiany") {
    throw new Error("Brain mesh manifest atlas must be desikan-killiany");
  }
  if (manifest.ordering !== "left-then-right") {
    throw new Error("Brain mesh manifest ordering must be left-then-right");
  }
  if (manifest.ordering_rule !== undefined && manifest.ordering_rule !== "left source vertex order, then right source vertex order") {
    throw new Error("Brain mesh manifest ordering rule is invalid");
  }
  if (manifest.coordinate_units !== undefined && manifest.coordinate_units !== "millimeters") {
    throw new Error("Brain mesh manifest coordinate units must be millimeters");
  }
  if (!isPositiveInteger(manifest.left_vertex_count) || !isPositiveInteger(manifest.right_vertex_count)) {
    throw new Error("Brain mesh manifest hemisphere vertex counts must be positive integers");
  }
  if (manifest.vertex_count !== manifest.left_vertex_count + manifest.right_vertex_count) {
    throw new Error("Brain mesh manifest total vertex count must equal left plus right");
  }
  if (manifest.total_vertex_count !== manifest.vertex_count) {
    throw new Error("Brain mesh manifest total_vertex_count must match vertex_count");
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
  if (typeof value.path !== "string" || value.path !== value.file) {
    throw new Error(`Brain mesh manifest ${key} hemisphere path must match file`);
  }
  if (value.vertex_count !== expectedVertexCount) {
    throw new Error(`Brain mesh manifest ${key} vertex count does not match top-level count`);
  }
  if (value.vertex_start !== expectedActivationOffset) {
    throw new Error(`Brain mesh manifest ${key} vertex start is invalid`);
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
