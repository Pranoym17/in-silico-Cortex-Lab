import { create } from "zustand";

export type StimulusBlock = {
  id: string;
  type: "image" | "text" | "audio";
  startMs: number;
  durationMs: number;
};

type ExperimentState = {
  blocks: StimulusBlock[];
  setBlocks: (blocks: StimulusBlock[]) => void;
};

export const useExperimentStore = create<ExperimentState>((set) => ({
  blocks: [],
  setBlocks: (blocks) => set({ blocks })
}));

