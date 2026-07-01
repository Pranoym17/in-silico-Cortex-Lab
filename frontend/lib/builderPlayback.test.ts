import { describe, expect, it } from "vitest";

import { StimulusBlock } from "./api";
import {
  getActivePlaybackBlocks,
  getActiveWordIndex,
  getHrfLagZones,
  getImageDisplayMode,
  getImageSources,
  getMediaSource,
  getPlaybackDurationMs,
  getPlaybackWords
} from "./builderPlayback";

function block(overrides: Partial<StimulusBlock> = {}): StimulusBlock {
  return {
    id: "block-1",
    experiment_id: "experiment-1",
    type: "text",
    condition: "test",
    start_ms: 1000,
    duration_ms: 2000,
    content_hash: null,
    payload: { text: "one two" },
    created_at: "",
    updated_at: "",
    ...overrides
  };
}

describe("builder playback", () => {
  it("calculates duration and active blocks across timeline gaps", () => {
    const blocks = [block(), block({ id: "later", start_ms: 5000, duration_ms: 1000 })];
    expect(getPlaybackDurationMs(blocks)).toBe(6000);
    expect(getActivePlaybackBlocks(blocks, 1500).map((item) => item.id)).toEqual(["block-1"]);
    expect(getActivePlaybackBlocks(blocks, 4000)).toEqual([]);
  });

  it("prefers local preview metadata before a public asset path", () => {
    expect(getMediaSource({ local: { preview_url: "blob:local" }, public_path: "/public.wav" })).toBe("blob:local");
    expect(getMediaSource({ public_path: "/public.wav" })).toBe("/public.wav");
  });

  it("normalizes image display modes and side-by-side sources", () => {
    const payload = {
      public_path: "/left.png",
      display: { mode: "side_by_side", secondary_public_path: "/right.png" }
    };
    expect(getImageDisplayMode(payload)).toBe("side-by-side");
    expect(getImageSources(payload)).toEqual(["/left.png", "/right.png"]);
    expect(getImageDisplayMode({ display: { mode: "full_bleed" } })).toBe("full-bleed");
  });

  it("uses explicit word timings and finds the active word", () => {
    const words = getPlaybackWords(
      block({
        payload: {
          text: "hello cortex",
          word_timings: [
            { word: "hello", start_ms: 0, end_ms: 400 },
            { word: "cortex", start_ms: 400, end_ms: 1000 }
          ]
        }
      })
    );
    expect(words).toHaveLength(2);
    expect(getActiveWordIndex(words, 600)).toBe(1);
  });

  it("spreads untimed words over the block duration", () => {
    expect(getPlaybackWords(block())).toEqual([
      { text: "one", startMs: 0, endMs: 1000 },
      { text: "two", startMs: 1000, endMs: 2000 }
    ]);
  });

  it("places HRF response zones five seconds after each stimulus", () => {
    expect(getHrfLagZones([block()])).toEqual([
      { blockId: "block-1", condition: "test", startMs: 6000, endMs: 8000 }
    ]);
  });
});
