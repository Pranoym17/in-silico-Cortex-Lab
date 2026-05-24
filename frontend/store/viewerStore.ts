import { create } from "zustand";
import { decodeActivationChunk, DecodedActivationChunk, JobStreamEvent } from "../lib/sse";

type ViewerState = {
  jobId: string | null;
  status: "idle" | "queued" | "warming" | "running" | "complete" | "failed";
  timestep: number;
  completedBlocks: number;
  totalBlocks: number;
  chunks: DecodedActivationChunk[];
  lastEventId: number | null;
  error: string | null;
  resetJob: (jobId: string) => void;
  setTimestep: (timestep: number) => void;
  handleStreamEvent: (event: JobStreamEvent) => void;
};

export const useViewerStore = create<ViewerState>((set) => ({
  jobId: null,
  status: "idle",
  timestep: 0,
  completedBlocks: 0,
  totalBlocks: 0,
  chunks: [],
  lastEventId: null,
  error: null,
  resetJob: (jobId) =>
    set({
      jobId,
      status: "idle",
      timestep: 0,
      completedBlocks: 0,
      totalBlocks: 0,
      chunks: [],
      lastEventId: null,
      error: null
    }),
  setTimestep: (timestep) => set({ timestep }),
  handleStreamEvent: (event) =>
    set((state) => {
      const base = { lastEventId: event.id ?? state.lastEventId };

      if (event.event === "queued") {
        return { ...base, jobId: event.data.job_id, status: "queued", error: null };
      }

      if (event.event === "warming") {
        return { ...base, jobId: event.data.job_id, status: "warming", error: null };
      }

      if (event.event === "progress") {
        return {
          ...base,
          jobId: event.data.job_id,
          status: state.status === "complete" ? "complete" : "running",
          completedBlocks: event.data.completed_blocks,
          totalBlocks: event.data.total_blocks,
          timestep: event.data.completed_timesteps,
          error: null
        };
      }

      if (event.event === "chunk") {
        const chunk = decodeActivationChunk(event.data);
        return {
          ...base,
          jobId: chunk.job_id,
          status: state.status === "complete" ? "complete" : "running",
          chunks: [...state.chunks, chunk],
          timestep: Math.max(state.timestep, chunk.timestep_start + chunk.timestep_count),
          error: null
        };
      }

      if (event.event === "complete") {
        return {
          ...base,
          jobId: event.data.job_id,
          status: "complete",
          timestep: event.data.timesteps,
          error: null
        };
      }

      return {
        ...base,
        jobId: event.data.job_id,
        status: "failed",
        error: event.data.message
      };
    })
}));
