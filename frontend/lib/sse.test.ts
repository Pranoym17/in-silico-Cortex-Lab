import { afterEach, describe, expect, it, vi } from "vitest";
import msgpack from "msgpack-lite";
import {
  decodeActivationChunk,
  decodeBase64Msgpack,
  parseSseFrame,
  SseFrameParser,
  streamJobEvents
} from "./sse";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("decodeBase64Msgpack", () => {
  it("decodes the SSE chunk envelope payload", () => {
    const payload = Buffer.from(msgpack.encode({ vertex_count: 20000 })).toString("base64");

    expect(decodeBase64Msgpack<{ vertex_count: number }>({ encoding: "base64-msgpack", payload })).toEqual({
      vertex_count: 20000
    });
  });
});

describe("decodeActivationChunk", () => {
  it("decodes raw float32 activation bytes", () => {
    const values = new Float32Array([1.5, -2, 0.25]);
    const payload = Buffer.from(
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
    ).toString("base64");

    const decoded = decodeActivationChunk({ encoding: "base64-msgpack", payload });

    expect(decoded.job_id).toBe("job_1");
    expect(decoded.shape).toEqual([1, 3]);
    expect(Array.from(decoded.activations)).toEqual([1.5, -2, 0.25]);
  });
});

describe("parseSseFrame", () => {
  it("parses a named event with an id and JSON data", () => {
    expect(parseSseFrame('event: progress\nid: 7\ndata: {"job_id":"job_1","completed_timesteps":2}\n')).toEqual({
      id: 7,
      event: "progress",
      data: { job_id: "job_1", completed_timesteps: 2 }
    });
  });

  it("ignores comments and unknown events", () => {
    expect(parseSseFrame(': heartbeat\n\n')).toBeNull();
    expect(parseSseFrame('event: custom\ndata: {"ok":true}\n')).toBeNull();
  });
});

describe("SseFrameParser", () => {
  it("parses events split across chunks", () => {
    const parser = new SseFrameParser();

    expect(parser.push('event: queued\nid: 1\ndata: {"job_id"')).toEqual([]);
    expect(parser.push(':"job_1","status":"queued"}\n\n')).toEqual([
      { id: 1, event: "queued", data: { job_id: "job_1", status: "queued" } }
    ]);
  });
});

describe("streamJobEvents", () => {
  it("streams events with Authorization headers", async () => {
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('event: queued\nid: 1\ndata: {"job_id":"job_1","status":"queued"}\n\n'));
        controller.close();
      }
    });
    const fetchMock = vi.fn().mockResolvedValue(new Response(body, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const events: unknown[] = [];

    await streamJobEvents({
      jobId: "job_1",
      token: "token_123",
      fromEventId: 4,
      onEvent: (event) => events.push(event)
    });

    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/jobs/job_1/stream?from_event_id=4");
    expect(fetchMock.mock.calls[0][1].headers.authorization).toBe("Bearer token_123");
    expect(events).toEqual([{ id: 1, event: "queued", data: { job_id: "job_1", status: "queued" } }]);
  });
});
