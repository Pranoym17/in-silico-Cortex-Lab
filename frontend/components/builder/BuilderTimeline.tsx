"use client";

import { StimulusBlock } from "@/lib/api";
import { getTimelineDurationMs } from "@/lib/timelineControls";

const PX_PER_MS = 0.08;
const MIN_TIMELINE_WIDTH = 720;

function getBlockClassName(block: StimulusBlock, selectedBlockId: string | null) {
  return block.id === selectedBlockId ? "timeline-block timeline-block-selected" : "timeline-block";
}

export function BuilderTimeline({
  blocks,
  selectedBlockId,
  onSelectBlock
}: {
  blocks: StimulusBlock[];
  selectedBlockId: string | null;
  onSelectBlock: (blockId: string) => void;
}) {
  const durationMs = getTimelineDurationMs(blocks);
  const width = Math.max(MIN_TIMELINE_WIDTH, durationMs * PX_PER_MS + 120);

  return (
    <div className="timeline-shell" aria-label="Experiment timeline">
      <div className="timeline-ruler" style={{ width }}>
        <span>0s</span>
        <span>{Math.ceil(durationMs / 1000)}s</span>
      </div>
      <div className="timeline-track" style={{ width }}>
        {blocks.map((block) => (
          <button
            aria-pressed={block.id === selectedBlockId}
            className={getBlockClassName(block, selectedBlockId)}
            key={block.id}
            onClick={() => onSelectBlock(block.id)}
            style={{
              left: block.start_ms * PX_PER_MS,
              width: Math.max(48, block.duration_ms * PX_PER_MS)
            }}
            title={`${block.type}: ${block.start_ms}ms-${block.start_ms + block.duration_ms}ms`}
            type="button"
          >
            <span>{block.type}</span>
            <small>{block.condition ?? "none"}</small>
          </button>
        ))}
      </div>
    </div>
  );
}
