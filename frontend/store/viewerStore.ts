import { create } from "zustand";

type ViewerState = {
  timestep: number;
  setTimestep: (timestep: number) => void;
};

export const useViewerStore = create<ViewerState>((set) => ({
  timestep: 0,
  setTimestep: (timestep) => set({ timestep })
}));

