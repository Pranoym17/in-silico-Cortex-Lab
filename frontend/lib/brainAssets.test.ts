import { describe, expect, it, vi } from "vitest";
import { loadBrainAtlas, loadBrainManifest, validateBrainAtlas, validateBrainManifest } from "./brainAssets";

const manifest = {
  surface: "fsaverage5",
  vertex_order: "left_then_right",
  total_vertex_count: 20484,
  vertex_count: 20484,
  left_vertex_count: 10242,
  right_vertex_count: 10242,
  ordering: "left-then-right",
  ordering_rule: "left source vertex order, then right source vertex order",
  coordinate_units: "millimeters",
  atlas: "desikan-killiany",
  gltf: {
    left: "/brain/fsaverage5_left.gltf",
    right: "/brain/fsaverage5_right.gltf"
  },
  hemispheres: {
    left: {
      path: "/brain/fsaverage5_left.gltf",
      file: "/brain/fsaverage5_left.gltf",
      vertex_start: 0,
      vertex_count: 10242,
      activation_offset: 0
    },
    right: {
      path: "/brain/fsaverage5_right.gltf",
      file: "/brain/fsaverage5_right.gltf",
      vertex_start: 10242,
      vertex_count: 10242,
      activation_offset: 10242
    }
  }
};

describe("brain asset validation", () => {
  it("accepts the mesh manifest contract", () => {
    expect(validateBrainManifest(manifest)).toEqual(manifest);
  });

  it("rejects mismatched vertex counts", () => {
    expect(() => validateBrainManifest({ ...manifest, vertex_count: 10 })).toThrow(
      "Brain mesh manifest total vertex count must equal left plus right"
    );
    expect(() => validateBrainManifest({ ...manifest, total_vertex_count: 10 })).toThrow(
      "Brain mesh manifest total_vertex_count must match vertex_count"
    );
  });

  it("rejects invalid vertex order and hemisphere starts", () => {
    expect(() => validateBrainManifest({ ...manifest, vertex_order: "right_then_left" })).toThrow(
      "Brain mesh manifest vertex order must be left_then_right"
    );
    expect(() =>
      validateBrainManifest({
        ...manifest,
        hemispheres: {
          ...manifest.hemispheres,
          right: { ...manifest.hemispheres.right, vertex_start: 0 }
        }
      })
    ).toThrow("Brain mesh manifest right vertex start is invalid");
  });

  it("rejects invalid coordinate metadata", () => {
    expect(() => validateBrainManifest({ ...manifest, coordinate_units: "meters" })).toThrow(
      "Brain mesh manifest coordinate units must be millimeters"
    );
    expect(() => validateBrainManifest({ ...manifest, ordering_rule: "right-first" })).toThrow(
      "Brain mesh manifest ordering rule is invalid"
    );
  });

  it("accepts numeric atlas index keys", () => {
    expect(validateBrainAtlas({ "0": "Left-Banks-STS", "10242": "Right-Banks-STS" })).toEqual({
      "0": "Left-Banks-STS",
      "10242": "Right-Banks-STS"
    });
  });

  it("rejects non-numeric atlas keys", () => {
    expect(() => validateBrainAtlas({ left: "Left-Banks-STS" })).toThrow(
      "Brain atlas must map numeric vertex indices to region names"
    );
  });
});

describe("brain asset loaders", () => {
  it("loads and validates manifest JSON", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(manifest), { status: 200 }));

    await expect(loadBrainManifest(fetcher)).resolves.toEqual(manifest);
    expect(fetcher).toHaveBeenCalledWith("/brain/mesh-manifest.json");
  });

  it("loads and validates atlas JSON", async () => {
    const atlas = { "0": "Left-Banks-STS" };
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(atlas), { status: 200 }));

    await expect(loadBrainAtlas(fetcher)).resolves.toEqual(atlas);
    expect(fetcher).toHaveBeenCalledWith("/brain/atlas-desikan-killiany.json");
  });
});
