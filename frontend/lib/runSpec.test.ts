import { describe, expect, it } from "vitest";
import { StimulusBlock } from "./api";
import { buildRunExperimentInput } from "./runSpec";

function makeBlock(overrides: Partial<StimulusBlock> = {}): StimulusBlock {
  return {
    id: "block_1",
    experiment_id: "exp_1",
    type: "text",
    condition: "condition_a",
    start_ms: 1000,
    duration_ms: 2000,
    content_hash: "sha256:abc123",
    payload: { text: "hello", voice: "kokoro_default" },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides
  };
}

describe("runSpec", () => {
  it("sorts and flattens builder blocks for the run API", () => {
    const input = buildRunExperimentInput([
      makeBlock({ id: "block_2", start_ms: 2000 }),
      makeBlock({ id: "block_1", start_ms: 0 })
    ]);

    expect(input.blocks.map((block) => block.id)).toEqual(["block_1", "block_2"]);
    expect(input.settings.surface).toBe("fsaverage5");
  });

  it("maps image payload metadata into the run block", () => {
    const input = buildRunExperimentInput([
      makeBlock({
        type: "image",
        payload: {
          s3_key: "uploads/face.png",
          mime_type: "image/png",
          display: { mode: "center" }
        }
      })
    ]);

    expect(input.blocks[0]).toMatchObject({
      type: "image",
      s3_key: "uploads/face.png",
      mime_type: "image/png",
      display: { mode: "center" }
    });
  });

  it("throws when a block is missing required run metadata", () => {
    expect(() => buildRunExperimentInput([makeBlock({ content_hash: null })])).toThrow(
      "Every block needs a content hash before running."
    );
  });
});
