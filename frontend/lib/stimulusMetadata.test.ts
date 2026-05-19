import { describe, expect, it } from "vitest";
import { StimulusBlock } from "@/lib/api";
import { getStimulusReadinessIssues, normalizeContentHash } from "./stimulusMetadata";

function makeBlock(overrides: Partial<StimulusBlock> = {}): StimulusBlock {
  return {
    id: "block_1",
    experiment_id: "exp_1",
    type: "text",
    condition: "condition_a",
    start_ms: 0,
    duration_ms: 2000,
    content_hash: null,
    payload: { text: "hello" },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides
  };
}

describe("stimulusMetadata", () => {
  it("normalizes bare hashes to the run-contract prefix", () => {
    expect(normalizeContentHash("abc123")).toBe("sha256:abc123");
    expect(normalizeContentHash("sha256:abc123")).toBe("sha256:abc123");
    expect(normalizeContentHash(" ")).toBeNull();
  });

  it("reports missing run metadata for media blocks", () => {
    const issues = getStimulusReadinessIssues(
      makeBlock({ type: "image", content_hash: "sha256:image", payload: { mime_type: "image/png" } })
    );

    expect(issues).toContain("Image blocks need an uploaded S3 object key before running.");
  });

  it("accepts ready text metadata", () => {
    expect(getStimulusReadinessIssues(makeBlock({ content_hash: "sha256:text" }))).toEqual([]);
  });
});
