import { describe, expect, it } from "vitest";
import msgpack from "msgpack-lite";
import { useViewerStore } from "./viewerStore";

function resetStore() {
  useViewerStore.getState().resetJob("job_1");
}

function chunkEnvelope() {
  const values = new Float32Array([0, 1, 2]);
  return {
    encoding: "base64-msgpack" as const,
    payload: Buffer.from(
      msgpack.encode({
        job_id: "job_1",
        block_id: "block_1",
        chunk_index: 0,
        timestep_start: 0,
        timestep_count: 1,
        sample_rate_hz: 2,
        vertex_count: 3,
        dtype: "float32",
        shape: [1, 3],
        activations: Buffer.from(values.buffer)
      })
    ).toString("base64")
  };
}

describe("viewerStore", () => {
  it("tracks progress and decoded chunks from stream events", () => {
    resetStore();

    useViewerStore.getState().handleStreamEvent({
      id: 1,
      event: "queued",
      data: { job_id: "job_1", status: "queued" }
    });
    useViewerStore.getState().handleStreamEvent({
      id: 2,
      event: "progress",
      data: { job_id: "job_1", completed_blocks: 0, total_blocks: 1, completed_timesteps: 0 }
    });
    useViewerStore.getState().handleStreamEvent({ id: 3, event: "chunk", data: chunkEnvelope() });

    const state = useViewerStore.getState();
    expect(state.status).toBe("running");
    expect(state.completedBlocks).toBe(0);
    expect(state.totalBlocks).toBe(1);
    expect(state.timestep).toBe(1);
    expect(state.lastEventId).toBe(3);
    expect(state.chunks).toHaveLength(1);
    expect(Array.from(state.chunks[0].activations)).toEqual([0, 1, 2]);
  });

  it("marks complete and failed states", () => {
    resetStore();

    useViewerStore.getState().handleStreamEvent({
      id: 9,
      event: "complete",
      data: { job_id: "job_1", status: "complete", result_s3_key: null, timesteps: 4, vertex_count: 16 }
    });

    expect(useViewerStore.getState().status).toBe("complete");
    expect(useViewerStore.getState().timestep).toBe(4);

    useViewerStore.getState().handleStreamEvent({
      id: 10,
      event: "error",
      data: {
        job_id: "job_1",
        code: "validation_failed",
        message: "Run specification failed validation.",
        retryable: false,
        last_timestep: null
      }
    });

    expect(useViewerStore.getState().status).toBe("failed");
    expect(useViewerStore.getState().error).toBe("Run specification failed validation.");
  });
});
