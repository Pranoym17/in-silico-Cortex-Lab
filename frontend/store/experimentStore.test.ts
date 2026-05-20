import { describe, expect, it } from "vitest";
import { StimulusBlock } from "@/lib/api";
import { useExperimentStore } from "./experimentStore";

function makeBlock(overrides: Partial<StimulusBlock> = {}): StimulusBlock {
  return {
    id: "block_1",
    experiment_id: "exp_1",
    type: "text",
    condition: "language",
    start_ms: 0,
    duration_ms: 5000,
    content_hash: null,
    payload: { text: "hello" },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides
  };
}

describe("experimentStore", () => {
  it("loads blocks without marking the builder dirty", () => {
    useExperimentStore.getState().setBlocks([makeBlock()]);

    expect(useExperimentStore.getState().blocks).toHaveLength(1);
    expect(useExperimentStore.getState().isDirty).toBe(false);
  });

  it("upserts blocks and marks the builder dirty", () => {
    useExperimentStore.getState().setBlocks([]);
    useExperimentStore.getState().upsertBlock(makeBlock({ id: "block_2" }));

    expect(useExperimentStore.getState().blocks[0].id).toBe("block_2");
    expect(useExperimentStore.getState().isDirty).toBe(true);
  });

  it("keeps blocks sorted by start time", () => {
    useExperimentStore.getState().setBlocks([
      makeBlock({ id: "block_2", start_ms: 2000 }),
      makeBlock({ id: "block_1", start_ms: 0 })
    ]);

    expect(useExperimentStore.getState().blocks.map((block) => block.id)).toEqual(["block_1", "block_2"]);
  });

  it("detects overlapping blocks", () => {
    useExperimentStore.getState().setBlocks([
      makeBlock({ id: "block_1", start_ms: 0, duration_ms: 2000, content_hash: "sha256:block-1" }),
      makeBlock({ id: "block_2", start_ms: 1000, duration_ms: 2000, content_hash: "sha256:block-2" })
    ]);

    expect(useExperimentStore.getState().validationErrors).toContainEqual({
      blockId: "block_2",
      message: "Blocks cannot overlap."
    });
  });

  it("flags blocks that are missing run-ready metadata", () => {
    useExperimentStore.getState().setBlocks([makeBlock({ content_hash: null })]);

    expect(useExperimentStore.getState().validationErrors).toContainEqual({
      blockId: "block_1",
      message: "Content hash is required before running."
    });
  });
});
