import { describe, expect, it } from "vitest";
import { StimulusBlock } from "@/lib/api";
import { bytesToHex, createUploadIntentInput, formatUploadError, validateUploadFile } from "./mediaUpload";

function makeBlock(overrides: Partial<StimulusBlock> = {}): StimulusBlock {
  return {
    id: "block_1",
    experiment_id: "exp_1",
    type: "image",
    condition: "condition_a",
    start_ms: 0,
    duration_ms: 2000,
    content_hash: null,
    payload: {},
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides
  };
}

describe("mediaUpload", () => {
  it("formats digest bytes as hex", () => {
    expect(bytesToHex(new Uint8Array([0, 15, 255]).buffer)).toBe("000fff");
  });

  it("builds a presign request from a block and file", () => {
    const input = createUploadIntentInput("exp_1", makeBlock(), new File(["x"], "face.png", { type: "image/png" }));

    expect(input).toEqual({
      experiment_id: "exp_1",
      block_id: "block_1",
      kind: "image",
      filename: "face.png",
      mime_type: "image/png",
      size_bytes: 1
    });
  });

  it("rejects unsupported image MIME types", () => {
    expect(() => validateUploadFile("image", new File(["x"], "face.gif", { type: "image/gif" }))).toThrow(
      "Image uploads must be PNG, JPEG, or WebP."
    );
  });

  it("formats upload failures with retry guidance", () => {
    expect(formatUploadError(new Error("Upload failed with status 403"))).toContain("Retry the upload");
  });
});
