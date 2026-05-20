import { create } from "zustand";
import { StimulusBlock } from "@/lib/api";
import { getStimulusReadinessIssues } from "../lib/stimulusMetadata";

export type BuilderValidationError = {
  blockId?: string;
  message: string;
};

type ExperimentState = {
  blocks: StimulusBlock[];
  selectedBlockId: string | null;
  isDirty: boolean;
  validationErrors: BuilderValidationError[];
  setBlocks: (blocks: StimulusBlock[]) => void;
  upsertBlock: (block: StimulusBlock) => void;
  removeBlock: (blockId: string) => void;
  selectBlock: (blockId: string | null) => void;
  setDirty: (isDirty: boolean) => void;
  validate: () => BuilderValidationError[];
};

function validateBlocks(blocks: StimulusBlock[]) {
  const errors: BuilderValidationError[] = [];

  if (blocks.length > 50) {
    errors.push({ message: "Experiments cannot exceed 50 blocks." });
  }

  const sortedBlocks = [...blocks].sort((a, b) => a.start_ms - b.start_ms);
  let previousEnd = 0;
  for (const block of sortedBlocks) {
    const blockEnd = block.start_ms + block.duration_ms;
    if (block.start_ms < previousEnd) {
      errors.push({ blockId: block.id, message: "Blocks cannot overlap." });
    }
    if (blockEnd > 300000) {
      errors.push({ blockId: block.id, message: "Experiment duration cannot exceed 5 minutes." });
    }
    if (block.type === "image" && (block.duration_ms < 500 || block.duration_ms > 30000)) {
      errors.push({ blockId: block.id, message: "Image blocks must be between 0.5s and 30s." });
    }
    if (block.type === "audio" && block.duration_ms > 60000) {
      errors.push({ blockId: block.id, message: "Audio blocks cannot exceed 60s." });
    }
    if (block.type === "text" && typeof block.payload.text === "string" && block.payload.text.split(/\s+/).length > 1024) {
      errors.push({ blockId: block.id, message: "Text blocks cannot exceed 1024 words." });
    }
    for (const issue of getStimulusReadinessIssues(block)) {
      errors.push({ blockId: block.id, message: issue });
    }
    previousEnd = Math.max(previousEnd, blockEnd);
  }

  return errors;
}

function sortBlocks(blocks: StimulusBlock[]) {
  return [...blocks].sort((a, b) => a.start_ms - b.start_ms || a.id.localeCompare(b.id));
}

export const useExperimentStore = create<ExperimentState>((set, get) => ({
  blocks: [],
  selectedBlockId: null,
  isDirty: false,
  validationErrors: [],
  setBlocks: (blocks) =>
    set({
      blocks: sortBlocks(blocks),
      isDirty: false,
      selectedBlockId: blocks.some((block) => block.id === get().selectedBlockId) ? get().selectedBlockId : null,
      validationErrors: validateBlocks(blocks)
    }),
  upsertBlock: (block) =>
    set((state) => {
      const exists = state.blocks.some((item) => item.id === block.id);
      const blocks = sortBlocks(
        exists ? state.blocks.map((item) => (item.id === block.id ? block : item)) : [...state.blocks, block]
      );
      return { blocks, isDirty: true, validationErrors: validateBlocks(blocks) };
    }),
  removeBlock: (blockId) =>
    set((state) => {
      const blocks = state.blocks.filter((block) => block.id !== blockId);
      return {
        blocks,
        isDirty: true,
        selectedBlockId: state.selectedBlockId === blockId ? null : state.selectedBlockId,
        validationErrors: validateBlocks(blocks)
      };
    }),
  selectBlock: (blockId) => set({ selectedBlockId: blockId }),
  setDirty: (isDirty) => set({ isDirty }),
  validate: () => {
    const validationErrors = validateBlocks(get().blocks);
    set({ validationErrors });
    return validationErrors;
  }
}));
