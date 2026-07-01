"use client";

import { KeyboardEvent, PointerEvent, WheelEvent, useRef, useState } from "react";
import { StimulusBlock } from "@/lib/api";
import { getConditionColor } from "@/lib/builderConditions";
import { formatDuration } from "@/lib/builderSummary";
import { getStimulusReadinessIssues } from "@/lib/stimulusMetadata";
import {
  DEFAULT_TIMELINE_ZOOM,
  MIN_BLOCK_DURATION_MS,
  TIMELINE_NUDGE_MS,
  TIMELINE_SNAP_MS,
  clampTimelineZoom,
  getTimelineDurationMs,
  pixelsToTimelineMs,
  snapTimelineMs,
  zoomFromPinch,
  zoomFromWheel
} from "@/lib/timelineControls";

const MIN_TIMELINE_WIDTH = 720;

type TimelineInteraction = {
  blockId: string;
  kind: "move" | "resize";
  pointerId: number;
  startClientX: number;
  initialMs: number;
  previewMs: number;
};

type BuilderTimelineProps = {
  blocks: StimulusBlock[];
  selectedBlockId: string | null;
  onSelectBlock: (blockId: string) => void;
  onMoveBlock?: (blockId: string, startMs: number) => void | Promise<void>;
  onResizeBlock?: (blockId: string, durationMs: number) => void | Promise<void>;
  zoom?: number;
  onZoomChange?: (zoom: number, source: "wheel" | "pinch") => void;
  snapMs?: number;
};

function getBlockClassName(block: StimulusBlock, selectedBlockId: string | null) {
  const issues = getStimulusReadinessIssues(block);
  const classes = ["timeline-block", issues.length > 0 ? "timeline-block-blocked" : "timeline-block-ready"];
  if (block.id === selectedBlockId) {
    classes.push("timeline-block-selected");
  }
  return classes.join(" ");
}

export function BuilderTimeline({
  blocks,
  selectedBlockId,
  onSelectBlock,
  onMoveBlock,
  onResizeBlock,
  zoom = DEFAULT_TIMELINE_ZOOM,
  onZoomChange,
  snapMs = TIMELINE_SNAP_MS
}: BuilderTimelineProps) {
  const safeZoom = clampTimelineZoom(zoom);
  const [interaction, setInteraction] = useState<TimelineInteraction | null>(null);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const pinch = useRef<{ startDistance: number; startZoom: number } | null>(null);
  const durationMs = getTimelineDurationMs(blocks);
  const width = Math.max(MIN_TIMELINE_WIDTH, durationMs * safeZoom + 120);

  function beginInteraction(
    event: PointerEvent<HTMLElement>,
    block: StimulusBlock,
    kind: TimelineInteraction["kind"]
  ) {
    const enabled = kind === "move" ? Boolean(onMoveBlock) : Boolean(onResizeBlock);
    if (event.button !== 0 || !enabled) return;
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    onSelectBlock(block.id);
    const initialMs = kind === "move" ? block.start_ms : block.duration_ms;
    setInteraction({
      blockId: block.id,
      kind,
      pointerId: event.pointerId,
      startClientX: event.clientX,
      initialMs,
      previewMs: initialMs
    });
  }

  function updateInteraction(event: PointerEvent<HTMLElement>) {
    if (!interaction || interaction.pointerId !== event.pointerId) return;
    const deltaMs = pixelsToTimelineMs(event.clientX - interaction.startClientX, safeZoom, snapMs);
    const minimum = interaction.kind === "move" ? 0 : MIN_BLOCK_DURATION_MS;
    setInteraction({
      ...interaction,
      previewMs: Math.max(minimum, snapTimelineMs(interaction.initialMs + deltaMs, snapMs))
    });
  }

  function finishInteraction(event: PointerEvent<HTMLElement>) {
    if (!interaction || interaction.pointerId !== event.pointerId) return;
    event.preventDefault();
    const finished = interaction;
    setInteraction(null);
    if (finished.previewMs === finished.initialMs) return;
    if (finished.kind === "move") {
      void onMoveBlock?.(finished.blockId, finished.previewMs);
    } else {
      void onResizeBlock?.(finished.blockId, finished.previewMs);
    }
  }

  function cancelInteraction(event: PointerEvent<HTMLElement>) {
    if (interaction?.pointerId === event.pointerId) {
      setInteraction(null);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, block: StimulusBlock) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    const direction = event.key === "ArrowLeft" ? -1 : 1;
    const step = event.altKey ? snapMs : TIMELINE_NUDGE_MS;
    event.preventDefault();
    onSelectBlock(block.id);
    if (event.shiftKey && onResizeBlock) {
      void onResizeBlock(
        block.id,
        Math.max(MIN_BLOCK_DURATION_MS, snapTimelineMs(block.duration_ms + direction * step, snapMs))
      );
    } else if (onMoveBlock) {
      void onMoveBlock(block.id, Math.max(0, snapTimelineMs(block.start_ms + direction * step, snapMs)));
    }
  }

  function handleWheel(event: WheelEvent<HTMLDivElement>) {
    if (!onZoomChange) return;
    event.preventDefault();
    onZoomChange(zoomFromWheel(safeZoom, event.deltaY), "wheel");
  }

  function updatePinchPointer(event: PointerEvent<HTMLDivElement>) {
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.current.size !== 2 || !onZoomChange) return;
    const [first, second] = [...pointers.current.values()];
    const distance = Math.hypot(first.x - second.x, first.y - second.y);
    if (!pinch.current) {
      pinch.current = { startDistance: distance, startZoom: safeZoom };
      return;
    }
    event.preventDefault();
    onZoomChange(zoomFromPinch(pinch.current.startZoom, pinch.current.startDistance, distance), "pinch");
  }

  function removePinchPointer(event: PointerEvent<HTMLDivElement>) {
    pointers.current.delete(event.pointerId);
    if (pointers.current.size < 2) pinch.current = null;
  }

  return (
    <div
      className="timeline-shell timeline-shell-interactive"
      aria-label="Experiment timeline"
      onPointerDown={updatePinchPointer}
      onPointerMove={updatePinchPointer}
      onPointerCancel={removePinchPointer}
      onPointerUp={removePinchPointer}
      onWheel={handleWheel}
    >
      <div className="timeline-ruler" style={{ width }}>
        <span>0s</span>
        <span>{Math.ceil(durationMs / 1000)}s</span>
      </div>
      <div className="timeline-track" style={{ width }}>
        {blocks.map((block) => {
          const active = interaction?.blockId === block.id ? interaction : null;
          const startMs = active?.kind === "move" ? active.previewMs : block.start_ms;
          const blockDurationMs = active?.kind === "resize" ? active.previewMs : block.duration_ms;
          return (
            <button
              aria-label={`${block.type} block, starts at ${startMs} milliseconds, duration ${blockDurationMs} milliseconds. Use arrow keys to move and Shift plus arrow keys to resize.`}
              aria-pressed={block.id === selectedBlockId}
              className={getBlockClassName(block, selectedBlockId)}
              key={block.id}
              onClick={() => onSelectBlock(block.id)}
              onKeyDown={(event) => handleKeyDown(event, block)}
              onPointerDown={(event) => beginInteraction(event, block, "move")}
              onPointerMove={updateInteraction}
              onPointerCancel={cancelInteraction}
              onPointerUp={finishInteraction}
              style={{
                left: startMs * safeZoom,
                width: Math.max(48, blockDurationMs * safeZoom)
              }}
              title={`${block.type}: ${startMs}ms-${startMs + blockDurationMs}ms`}
              type="button"
            >
              <span>
                <i style={{ background: getConditionColor(block.condition ?? "unlabeled") }} />
                {block.type}
              </span>
              <small>
                {block.condition ?? "unlabeled"} | {formatDuration(blockDurationMs)}
              </small>
              <span
                aria-hidden="true"
                className="timeline-block-resize-handle"
                onPointerDown={(event) => beginInteraction(event, block, "resize")}
                onPointerMove={updateInteraction}
                onPointerCancel={cancelInteraction}
                onPointerUp={finishInteraction}
              />
            </button>
          );
        })}
      </div>
    </div>
  );
}
