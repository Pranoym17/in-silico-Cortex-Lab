import { ReorderBlockInput, StimulusBlock } from "@/lib/api";

export const TIMELINE_NUDGE_MS = 500;
export const TIMELINE_DURATION_STEP_MS = 500;
export const MIN_BLOCK_DURATION_MS = 500;
export const TIMELINE_SNAP_MS = 100;
export const MIN_TIMELINE_ZOOM = 0.02;
export const MAX_TIMELINE_ZOOM = 0.4;
export const DEFAULT_TIMELINE_ZOOM = 0.08;

export function clampTimelineZoom(zoom: number) {
  return Math.min(MAX_TIMELINE_ZOOM, Math.max(MIN_TIMELINE_ZOOM, zoom));
}

export function snapTimelineMs(valueMs: number, snapMs = TIMELINE_SNAP_MS) {
  return snapMs <= 0 ? Math.round(valueMs) : Math.round(valueMs / snapMs) * snapMs;
}

export function pixelsToTimelineMs(pixels: number, zoom: number, snapMs = TIMELINE_SNAP_MS) {
  return snapTimelineMs(pixels / clampTimelineZoom(zoom), snapMs);
}

export function zoomFromWheel(currentZoom: number, deltaY: number) {
  return clampTimelineZoom(currentZoom * Math.exp(-deltaY * 0.002));
}

export function zoomFromPinch(currentZoom: number, startDistance: number, distance: number) {
  return startDistance <= 0
    ? clampTimelineZoom(currentZoom)
    : clampTimelineZoom(currentZoom * (distance / startDistance));
}

export function getTimelineDurationMs(blocks: Pick<StimulusBlock, "start_ms" | "duration_ms">[]) {
  return blocks.reduce((max, block) => Math.max(max, block.start_ms + block.duration_ms), 0);
}

export function shiftBlockTiming(
  blocks: StimulusBlock[],
  blockId: string,
  deltaMs: number,
  snapMs = TIMELINE_SNAP_MS
) {
  return blocks.map((block) =>
    block.id === blockId
      ? { ...block, start_ms: Math.max(0, snapTimelineMs(block.start_ms + deltaMs, snapMs)) }
      : block
  );
}

export function resizeBlockDuration(
  blocks: StimulusBlock[],
  blockId: string,
  deltaMs: number,
  snapMs = TIMELINE_SNAP_MS
) {
  return blocks.map((block) =>
    block.id === blockId
      ? {
          ...block,
          duration_ms: Math.max(
            MIN_BLOCK_DURATION_MS,
            snapTimelineMs(block.duration_ms + deltaMs, snapMs)
          )
        }
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
