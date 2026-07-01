import { describe, expect, it } from "vitest";
import { StimulusBlock } from "@/lib/api";
import {
  DEFAULT_TIMELINE_ZOOM,
  MAX_TIMELINE_ZOOM,
  MIN_TIMELINE_ZOOM,
  MIN_BLOCK_DURATION_MS,
  clampTimelineZoom,
  getTimelineDurationMs,
  pixelsToTimelineMs,
  resizeBlockDuration,
  shiftBlockTiming,
  snapTimelineMs,
  zoomFromPinch,
  zoomFromWheel,
  toReorderInput
} from "./timelineControls";

function makeBlock(overrides: Partial<StimulusBlock> = {}): StimulusBlock {
  return {
    id: "block_1",
    experiment_id: "exp_1",
    type: "text",
    condition: "condition_a",
    start_ms: 1000,
    duration_ms: 2000,
    content_hash: null,
    payload: { text: "hello" },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides
  };
}

describe("timelineControls", () => {
  it("calculates the full timeline duration", () => {
    const duration = getTimelineDurationMs([
      makeBlock({ start_ms: 0, duration_ms: 1000 }),
      makeBlock({ id: "block_2", start_ms: 3000, duration_ms: 1500 })
    ]);

    expect(duration).toBe(4500);
  });

  it("shifts a block without moving it before time zero", () => {
    const [block] = shiftBlockTiming([makeBlock()], "block_1", -2000);

    expect(block.start_ms).toBe(0);
  });

  it("snaps pointer timing to subsecond intervals", () => {
    expect(snapTimelineMs(1049)).toBe(1000);
    expect(snapTimelineMs(1051)).toBe(1100);
    expect(pixelsToTimelineMs(84, DEFAULT_TIMELINE_ZOOM, 50)).toBe(1050);
  });

  it("supports a custom snap interval for movement and resizing", () => {
    const [moved] = shiftBlockTiming([makeBlock()], "block_1", 137, 50);
    const [resized] = resizeBlockDuration([makeBlock()], "block_1", 137, 50);

    expect(moved.start_ms).toBe(1150);
    expect(resized.duration_ms).toBe(2150);
  });

  it("clamps wheel and pinch zoom to supported bounds", () => {
    expect(clampTimelineZoom(0)).toBe(MIN_TIMELINE_ZOOM);
    expect(clampTimelineZoom(1)).toBe(MAX_TIMELINE_ZOOM);
    expect(zoomFromWheel(DEFAULT_TIMELINE_ZOOM, -100)).toBeGreaterThan(DEFAULT_TIMELINE_ZOOM);
    expect(zoomFromPinch(DEFAULT_TIMELINE_ZOOM, 100, 50)).toBe(DEFAULT_TIMELINE_ZOOM / 2);
  });

  it("resizes a block without going below the minimum duration", () => {
    const [block] = resizeBlockDuration([makeBlock({ duration_ms: 750 })], "block_1", -500);

    expect(block.duration_ms).toBe(MIN_BLOCK_DURATION_MS);
  });

  it("creates the backend reorder envelope from timeline blocks", () => {
    expect(toReorderInput([makeBlock()])).toEqual([{ id: "block_1", start_ms: 1000, duration_ms: 2000 }]);
  });
});
