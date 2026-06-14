import { describe, expect, it } from "vitest";
import { BrainMeshManifest, DesikanKillianyAtlas } from "./brainAssets";
import {
  compareTopConditions,
  getRegionConditionSummaries,
  getHemisphereForVertex,
  getRegionActivationStats,
  getRegionForVertex,
  getRegionLabels,
  getRegionMetadata,
  getRegionPeak,
  getRegionTimecourse,
  getRegionVertices
} from "./brainRegions";
import { DecodedActivationChunk } from "./sse";

const manifest: BrainMeshManifest = {
  surface: "fsaverage5",
  vertex_order: "left_then_right",
  total_vertex_count: 6,
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
      path: "/brain/fsaverage5_left.gltf",
      file: "/brain/fsaverage5_left.gltf",
      vertex_start: 0,
      vertex_count: 2,
      activation_offset: 0
    },
    right: {
      path: "/brain/fsaverage5_right.gltf",
      file: "/brain/fsaverage5_right.gltf",
      vertex_start: 2,
      vertex_count: 4,
      activation_offset: 2
    }
  }
};

const atlas: DesikanKillianyAtlas = {
  "0": "Left-A",
  "1": "Left-B",
  "2": "Right-A",
  "3": "Right-A",
  "4": "Right-B",
  "5": "Right-A"
};

function chunk(values: number[], timestepStart = 0, timestepCount = 1): DecodedActivationChunk {
  return {
    job_id: "job_1",
    block_id: "block_1",
    chunk_index: 0,
    timestep_start: timestepStart,
    timestep_count: timestepCount,
    sample_rate_hz: 2,
    vertex_count: 6,
    dtype: "float32",
    shape: [timestepCount, 6],
    activations: new Float32Array(values)
  };
}

function blockChunk(blockId: string, values: number[], timestepStart = 0, timestepCount = 1): DecodedActivationChunk {
  return { ...chunk(values, timestepStart, timestepCount), block_id: blockId };
}

describe("brainRegions", () => {
  it("maps global vertex indices to hemispheres", () => {
    expect(getHemisphereForVertex(0, manifest)).toBe("left");
    expect(getHemisphereForVertex(1, manifest)).toBe("left");
    expect(getHemisphereForVertex(2, manifest)).toBe("right");
    expect(getHemisphereForVertex(5, manifest)).toBe("right");
    expect(getHemisphereForVertex(6, manifest)).toBeNull();
  });

  it("looks up the atlas region for one vertex", () => {
    expect(getRegionForVertex(atlas, manifest, 3)).toEqual({
      vertexIndex: 3,
      label: "Right-A",
      hemisphere: "right"
    });
    expect(getRegionForVertex(atlas, manifest, 99)).toBeNull();
  });

  it("returns sorted vertices and labels for a region", () => {
    expect(getRegionVertices(atlas, "Right-A")).toEqual([2, 3, 5]);
    expect(getRegionLabels(atlas)).toEqual(["Left-A", "Left-B", "Right-A", "Right-B"]);
  });

  it("summarizes one region activation frame", () => {
    const stats = getRegionActivationStats("Right-A", atlas, manifest, chunk([0, 1, 2, 4, 8, 6]));

    expect(stats).toEqual({
      label: "Right-A",
      hemisphere: "right",
      vertexCount: 3,
      min: 2,
      max: 6,
      mean: 4,
      absoluteMax: 6
    });
  });

  it("builds a per-timestep region mean timecourse", () => {
    const current = chunk([0, 1, 2, 4, 8, 6, 0, 1, 3, 6, 9, 12], 5, 2);

    expect(getRegionTimecourse("Right-A", atlas, manifest, [current])).toEqual([
      { timestep: 5, mean: 4, vertexCount: 3 },
      { timestep: 6, mean: 7, vertexCount: 3 }
    ]);
  });

  it("finds the peak absolute region response", () => {
    expect(
      getRegionPeak([
        { timestep: 0, mean: 0.2, vertexCount: 3 },
        { timestep: 1, mean: -0.8, vertexCount: 3 },
        { timestep: 2, mean: 0.5, vertexCount: 3 }
      ])
    ).toEqual({ timestep: 1, value: -0.8 });
  });

  it("returns atlas metadata for known and unknown labels", () => {
    expect(getRegionMetadata("Left-precentral").knownFunction).toContain("motor");
    expect(getRegionMetadata("Right-madeup").atlasDescription).toContain("Desikan-Killiany");
  });

  it("summarizes and compares region activation by streamed block", () => {
    const summaries = getRegionConditionSummaries("Right-A", atlas, manifest, [
      blockChunk("block_a", [0, 1, 2, 4, 8, 6, 0, 1, 3, 6, 9, 12], 0, 2),
      blockChunk("block_b", [0, 1, -2, -4, 8, -6], 2, 1)
    ]);

    expect(summaries).toEqual([
      { condition: "Condition 1", blockId: "block_a", mean: 5.5, peak: 7, samples: 2 },
      { condition: "Condition 2", blockId: "block_b", mean: -4, peak: -4, samples: 1 }
    ]);
    expect(compareTopConditions(summaries)).toEqual({
      conditionA: "Condition 1",
      conditionB: "Condition 2",
      meanDifference: 9.5,
      peakDifference: 11,
      dominantCondition: "Condition 1"
    });
  });
});
