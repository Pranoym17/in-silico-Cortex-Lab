import { ReorderBlockInput, StimulusBlock } from "@/lib/api";

export const TIMELINE_NUDGE_MS = 500;
export const TIMELINE_DURATION_STEP_MS = 500;
export const MIN_BLOCK_DURATION_MS = 500;

export function getTimelineDurationMs(blocks: Pick<StimulusBlock, "start_ms" | "duration_ms">[]) {
  return blocks.reduce((max, block) => Math.max(max, block.start_ms + block.duration_ms), 0);
}

export function shiftBlockTiming(blocks: StimulusBlock[], blockId: string, deltaMs: number) {
  return blocks.map((block) =>
    block.id === blockId ? { ...block, start_ms: Math.max(0, block.start_ms + deltaMs) } : block
  );
}

export function resizeBlockDuration(blocks: StimulusBlock[], blockId: string, deltaMs: number) {
  return blocks.map((block) =>
    block.id === blockId
      ? { ...block, duration_ms: Math.max(MIN_BLOCK_DURATION_MS, block.duration_ms + deltaMs) }
      : block
  );
}

export function toReorderInput(blocks: StimulusBlock[]): ReorderBlockInput[] {
  return blocks.map((block) => ({
    id: block.id,
    start_ms: block.start_ms,
    duration_ms: block.duration_ms
  }));
}
