import { StimulusBlock } from "./api";

export const HRF_LAG_MS = 5000;

export type PlaybackWord = {
  text: string;
  startMs: number;
  endMs: number;
};

export type ImageDisplayMode = "center" | "full-bleed" | "side-by-side";

function stringValue(value: unknown) {
  return typeof value === "string" && value.trim() ? value : null;
}

function recordValue(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function getPlaybackDurationMs(blocks: StimulusBlock[]) {
  return blocks.reduce(
    (duration, block) => Math.max(duration, block.start_ms + block.duration_ms),
    0
  );
}

export function getActivePlaybackBlocks(blocks: StimulusBlock[], timeMs: number) {
  return blocks
    .filter((block) => timeMs >= block.start_ms && timeMs < block.start_ms + block.duration_ms)
    .sort((left, right) => left.start_ms - right.start_ms);
}

export function getBlockLocalTimeMs(block: StimulusBlock, timeMs: number) {
  return Math.max(0, Math.min(block.duration_ms, timeMs - block.start_ms));
}

export function getMediaSource(payload: Record<string, unknown>) {
  const local = recordValue(payload.local);
  return (
    stringValue(local?.url) ??
    stringValue(local?.preview_url) ??
    stringValue(payload.local_url) ??
    stringValue(payload.local_preview_url) ??
    stringValue(payload.preview_url) ??
    stringValue(payload.public_path) ??
    null
  );
}

export function getImageDisplayMode(payload: Record<string, unknown>): ImageDisplayMode {
  const display = recordValue(payload.display);
  const mode = stringValue(display?.mode) ?? stringValue(payload.display_mode);
  if (mode === "full-bleed" || mode === "full_bleed") {
    return "full-bleed";
  }
  if (mode === "side-by-side" || mode === "side_by_side") {
    return "side-by-side";
  }
  return "center";
}

export function getImageSources(payload: Record<string, unknown>) {
  const primary = getMediaSource(payload);
  const display = recordValue(payload.display);
  const secondary = recordValue(payload.secondary);
  const secondarySource =
    stringValue(display?.secondary_public_path) ??
    stringValue(display?.secondary_url) ??
    stringValue(secondary?.public_path) ??
    stringValue(secondary?.local_url) ??
    stringValue(payload.secondary_public_path) ??
    stringValue(payload.secondary_url);

  return [primary, secondarySource].filter((source): source is string => source !== null);
}

function explicitWords(payload: Record<string, unknown>, blockDurationMs: number): PlaybackWord[] {
  const candidates = payload.word_timings ?? payload.words;
  if (!Array.isArray(candidates)) {
    return [];
  }

  return candidates.flatMap((candidate) => {
    const word = recordValue(candidate);
    const text = stringValue(word?.word) ?? stringValue(word?.text);
    if (!word || !text) {
      return [];
    }
    const start = Number(word.start_ms ?? Number(word.start_seconds) * 1000);
    const end = Number(word.end_ms ?? Number(word.end_seconds) * 1000);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
      return [];
    }
    return [{ text, startMs: Math.max(0, start), endMs: Math.min(blockDurationMs, end) }];
  });
}

export function getPlaybackWords(block: StimulusBlock): PlaybackWord[] {
  if (block.type !== "text") {
    return [];
  }
  const timed = explicitWords(block.payload, block.duration_ms);
  if (timed.length > 0) {
    return timed;
  }

  const words = (stringValue(block.payload.text) ?? "").split(/\s+/).filter(Boolean);
  const wordDuration = words.length > 0 ? block.duration_ms / words.length : 0;
  return words.map((text, index) => ({
    text,
    startMs: index * wordDuration,
    endMs: (index + 1) * wordDuration
  }));
}

export function getActiveWordIndex(words: PlaybackWord[], localTimeMs: number) {
  return words.findIndex((word) => localTimeMs >= word.startMs && localTimeMs < word.endMs);
}

export function getHrfLagZones(blocks: StimulusBlock[]) {
  return blocks.map((block) => ({
    blockId: block.id,
    condition: block.condition,
    startMs: block.start_ms + HRF_LAG_MS,
    endMs: block.start_ms + block.duration_ms + HRF_LAG_MS
  }));
}
