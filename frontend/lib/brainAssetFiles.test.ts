import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { validateBrainAtlas, validateBrainManifest } from "./brainAssets";

const brainDir = resolve(__dirname, "../public/brain");

function readJson<T>(filename: string): T {
  return JSON.parse(readFileSync(resolve(brainDir, filename), "utf-8")) as T;
}

function readGltfVertexCount(filename: string): number {
  const gltf = readJson<{ accessors: Array<{ count: number; type: string }> }>(filename);
  const positionAccessor = gltf.accessors.find((accessor) => accessor.type === "VEC3");
  if (!positionAccessor) {
    throw new Error(`${filename} does not include a POSITION accessor`);
  }
  return positionAccessor.count;
}

describe("checked-in brain fixture assets", () => {
  it("match the manifest and atlas contracts", () => {
    const manifest = validateBrainManifest(readJson("mesh-manifest.json"));
    const atlas = validateBrainAtlas(readJson("atlas-desikan-killiany.json"));

    expect(manifest.vertex_count).toBe(Object.keys(atlas).length);
    expect(readGltfVertexCount("fsaverage5_left.gltf")).toBe(manifest.left_vertex_count);
    expect(readGltfVertexCount("fsaverage5_right.gltf")).toBe(manifest.right_vertex_count);
  });
});
