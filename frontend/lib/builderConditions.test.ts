import { describe, expect, it } from "vitest";
import { StimulusBlock } from "@/lib/api";
import { getConditionColor, getConditionSummaries } from "./builderConditions";

function makeBlock(id: string, condition: string | null): StimulusBlock {
  return {
    id,
    experiment_id: "exp_1",
    type: "text",
    condition,
    start_ms: 0,
    duration_ms: 1000,
    content_hash: null,
    payload: {},
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z"
  };
}

describe("getConditionSummaries", () => {
  it("counts and sorts conditions", () => {
    expect(
      getConditionSummaries([makeBlock("1", "faces"), makeBlock("2", "houses"), makeBlock("3", "faces")])
    ).toEqual([
      { name: "faces", count: 2 },
      { name: "houses", count: 1 }
    ]);
  });

  it("uses unlabeled for missing conditions", () => {
    expect(getConditionSummaries([makeBlock("1", null)])).toEqual([{ name: "unlabeled", count: 1 }]);
  });
});

describe("getConditionColor", () => {
  it("returns a stable color for the same condition", () => {
    expect(getConditionColor("faces")).toBe(getConditionColor("faces"));
  });
});

