"use client";

import { StimulusBlock } from "@/lib/api";
import { getConditionColor } from "@/lib/builderConditions";
import { formatDuration } from "@/lib/builderSummary";
import { getStimulusReadinessIssues } from "@/lib/stimulusMetadata";
import { getTimelineDurationMs } from "@/lib/timelineControls";

const PX_PER_MS = 0.08;
const MIN_TIMELINE_WIDTH = 720;

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
            <span>
              <i style={{ background: getConditionColor(block.condition ?? "unlabeled") }} />
              {block.type}
            </span>
            <small>
              {block.condition ?? "unlabeled"} · {formatDuration(block.duration_ms)}
            </small>
          </button>
        ))}
      </div>
    </div>
  );
}
