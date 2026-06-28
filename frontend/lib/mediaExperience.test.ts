import { describe, expect, it } from "vitest";
import { estimateTextDurationMs, preferredRecordingMimeType } from "./mediaExperience";

describe("media experience", () => {
  it("estimates text duration at 200 words per minute", () => {
    expect(estimateTextDurationMs(Array.from({ length: 100 }, () => "word").join(" "))).toBe(30_000);
    expect(estimateTextDurationMs("")).toBe(500);
  });

  it("selects a supported MediaRecorder format", () => {
    expect(preferredRecordingMimeType((type) => type === "audio/webm")).toBe("audio/webm");
    expect(preferredRecordingMimeType(() => false)).toBe("");
  });
});
