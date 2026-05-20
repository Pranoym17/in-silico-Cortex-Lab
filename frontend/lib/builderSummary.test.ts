import { describe, expect, it } from "vitest";
import { StimulusBlock } from "./api";
import { formatDuration, getBuilderSummary } from "./builderSummary";

function makeBlock(overrides: Partial<StimulusBlock> = {}): StimulusBlock {
  return {
    id: "block_1",
    experiment_id: "exp_1",
    type: "text",
    condition: "condition_a",
    start_ms: 0,
    duration_ms: 2000,
    content_hash: "sha256:abc123",
    payload: { text: "hello" },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides
  };
}

describe("builderSummary", () => {
  it("counts blocks, readiness, type mix, and duration", () => {
    const summary = getBuilderSummary([
      makeBlock(),
      makeBlock({
        id: "block_2",
        type: "image",
        start_ms: 2000,
        duration_ms: 3000,
        content_hash: null,
        payload: {}
      })
    ]);

    expect(summary).toEqual({
      totalBlocks: 2,
      readyBlocks: 1,
      blockedBlocks: 1,
      durationMs: 5000,
      countsByType: {
        image: 1,
        text: 1,
        audio: 0
      }
    });
  });

  it("formats durations for compact UI labels", () => {
    expect(formatDuration(5000)).toBe("5s");
    expect(formatDuration(65000)).toBe("1m 05s");
  });
});
