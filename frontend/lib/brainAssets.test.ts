import { describe, expect, it, vi } from "vitest";
import {
  FSAVERAGE5_TOTAL_VERTEX_COUNT,
  loadBrainAtlas,
  loadBrainManifest,
  validateAtlasForManifest,
  validateBrainAtlas,
  validateBrainManifest
} from "./brainAssets";

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
  atlas_source: "freesurfer-fsaverage-aparc-nearest-to-nilearn-fsaverage5",
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

  it("validates a complete atlas against the mesh manifest", () => {
    const atlas = makeAtlas();

    expect(validateAtlasForManifest(atlas, validateBrainManifest(manifest))).toEqual({ valid: true, message: null });
  });

  it("rejects missing or placeholder atlas sources for region interaction", () => {
    const atlas = makeAtlas();

    expect(validateAtlasForManifest(null, validateBrainManifest(manifest))).toEqual({
      valid: false,
      message: "Atlas unavailable."
    });
    expect(
      validateAtlasForManifest(atlas, validateBrainManifest({ ...manifest, atlas_source: "unknown-placeholder" }))
    ).toEqual({
      valid: false,
      message: "Atlas unavailable: manifest atlas source is not scientifically verified."
    });
  });

  it("rejects atlas count mismatches", () => {
    const atlas = makeAtlas();
    const missingLast = { ...atlas };
    delete missingLast[String(FSAVERAGE5_TOTAL_VERTEX_COUNT - 1)];

    expect(validateAtlasForManifest({ "0": "Left-A" }, validateBrainManifest(manifest))).toEqual({
      valid: false,
      message: "Atlas unavailable: atlas has 1 vertices, expected 20484."
    });
    expect(validateAtlasForManifest(missingLast, validateBrainManifest(manifest))).toEqual({
      valid: false,
      message: "Atlas unavailable: atlas has 20483 vertices, expected 20484."
    });
  });

  it("rejects missing atlas endpoint vertices", () => {
    const missingFirst = { ...makeAtlas(), [String(FSAVERAGE5_TOTAL_VERTEX_COUNT)]: "Out-of-range" };
    delete missingFirst["0"];
    const missingLast = { ...makeAtlas(), [String(FSAVERAGE5_TOTAL_VERTEX_COUNT)]: "Out-of-range" };
    delete missingLast[String(FSAVERAGE5_TOTAL_VERTEX_COUNT - 1)];

    expect(validateAtlasForManifest(missingFirst, validateBrainManifest(manifest))).toEqual({
      valid: false,
      message: "Atlas unavailable: vertex 0 is missing."
    });
    expect(validateAtlasForManifest(missingLast, validateBrainManifest(manifest))).toEqual({
      valid: false,
      message: "Atlas unavailable: vertex 20483 is missing."
    });
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

function makeAtlas() {
  return Object.fromEntries(
    Array.from({ length: FSAVERAGE5_TOTAL_VERTEX_COUNT }, (_value, index) => [
      String(index),
      index < 10242 ? "Left-A" : "Right-A"
    ])
  );
}
