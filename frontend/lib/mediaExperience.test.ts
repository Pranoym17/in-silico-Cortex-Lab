import { describe, expect, it } from "vitest";
import {
  estimateTextDurationMs,
  formatRecordingElapsed,
  microphoneErrorMessage,
  preferredRecordingMimeType
} from "./mediaExperience";

describe("media experience", () => {
  it("estimates text duration at 200 words per minute", () => {
    expect(estimateTextDurationMs(Array.from({ length: 100 }, () => "word").join(" "))).toBe(30_000);
    expect(estimateTextDurationMs("")).toBe(500);
  });

  it("selects a supported MediaRecorder format", () => {
    expect(preferredRecordingMimeType((type) => type === "audio/webm")).toBe("audio/webm");
    expect(preferredRecordingMimeType(() => false)).toBe("");
  });

  it("formats recording elapsed time", () => {
    expect(formatRecordingElapsed(0)).toBe("0:00");
    expect(formatRecordingElapsed(65_999)).toBe("1:05");
    expect(formatRecordingElapsed(-1)).toBe("0:00");
  });

  it("provides actionable microphone errors", () => {
    expect(microphoneErrorMessage(new DOMException("denied", "NotAllowedError"))).toContain("browser settings");
    expect(microphoneErrorMessage(new DOMException("missing", "NotFoundError"))).toContain("No microphone");
    expect(microphoneErrorMessage(new Error("device details"))).not.toContain("device details");
  });
});
