import { describe, expect, it } from "vitest";
import { BrainMeshManifest } from "./brainAssets";
import {
  buildHemisphereVertexColors,
  buildVertexColorBuffer,
  getActivationFrame,
  getHemisphereActivationFrame,
  getLatestActivationChunk
} from "./brainActivation";
import { DecodedActivationChunk } from "./sse";

const manifest: BrainMeshManifest = {
  surface: "fsaverage5",
  vertex_count: 6,
  left_vertex_count: 2,
  right_vertex_count: 4,
  ordering: "left-then-right",
  atlas: "desikan-killiany",
  gltf: {
    left: "/brain/fsaverage5_left.gltf",
    right: "/brain/fsaverage5_right.gltf"
  },
  hemispheres: {
    left: {
      file: "/brain/fsaverage5_left.gltf",
      vertex_count: 2,
      activation_offset: 0
    },
    right: {
      file: "/brain/fsaverage5_right.gltf",
      vertex_count: 4,
      activation_offset: 2
    }
  }
};

function chunk(values: number[], timestepCount = 1): DecodedActivationChunk {
  return {
    job_id: "job_1",
    block_id: "block_1",
    chunk_index: 0,
    timestep_start: 0,
    timestep_count: timestepCount,
    sample_rate_hz: 2,
    vertex_count: 6,
    dtype: "float32",
    shape: [timestepCount, 6],
    activations: new Float32Array(values)
  };
}

describe("brainActivation", () => {
  it("selects the latest chunk and frame", () => {
    const first = chunk([0, 1, 2, 3, 4, 5]);
    const second = chunk([6, 7, 8, 9, 10, 11]);

    expect(getLatestActivationChunk([first, second])).toBe(second);
    expect(Array.from(getActivationFrame(second))).toEqual([6, 7, 8, 9, 10, 11]);
  });

  it("slices activation values by hemisphere offsets", () => {
    const current = chunk([0, 1, 2, 3, 4, 5]);

    expect(Array.from(getHemisphereActivationFrame(current, manifest, "left"))).toEqual([0, 1]);
    expect(Array.from(getHemisphereActivationFrame(current, manifest, "right"))).toEqual([2, 3, 4, 5]);
  });

  it("builds one rgb triplet per vertex", () => {
    const values = new Float32Array([-1, 0, 1]);
    const colors = buildVertexColorBuffer(values, [-1, 1]);

    expect(colors).toHaveLength(9);
    expect(colors[2]).toBeGreaterThan(colors[0]);
    expect(colors[6]).toBeGreaterThan(colors[8]);
  });

  it("returns neutral-sized colors when a chunk does not match the manifest", () => {
    const colors = buildHemisphereVertexColors(null, manifest, "right");

    expect(colors).toHaveLength(12);
  });
});
