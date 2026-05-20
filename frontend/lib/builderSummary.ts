import { StimulusBlock } from "./api";
import { getStimulusReadinessIssues } from "./stimulusMetadata";
import { getTimelineDurationMs } from "./timelineControls";

export type BuilderSummary = {
  totalBlocks: number;
  readyBlocks: number;
  blockedBlocks: number;
  durationMs: number;
  countsByType: Record<StimulusBlock["type"], number>;
};

export function getBuilderSummary(blocks: StimulusBlock[]): BuilderSummary {
  const countsByType: BuilderSummary["countsByType"] = {
    image: 0,
    text: 0,
    audio: 0
  };

  let readyBlocks = 0;

  for (const block of blocks) {
    countsByType[block.type] += 1;
    if (getStimulusReadinessIssues(block).length === 0) {
      readyBlocks += 1;
    }
  }

  return {
    totalBlocks: blocks.length,
    readyBlocks,
    blockedBlocks: blocks.length - readyBlocks,
    durationMs: getTimelineDurationMs(blocks),
    countsByType
  };
}

export function formatDuration(ms: number) {
  const totalSeconds = Math.ceil(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;

  if (minutes === 0) {
    return `${seconds}s`;
  }

  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}
