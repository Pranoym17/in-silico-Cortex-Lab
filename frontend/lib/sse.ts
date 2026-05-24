import msgpack from "msgpack-lite";
import { API_URL } from "./api";

export type ChunkEnvelope = {
  encoding: "base64-msgpack";
  payload: string;
};

export type QueuedEvent = {
  job_id: string;
  status: "queued";
};

export type WarmingEvent = {
  job_id: string;
  reason: string;
  estimated_seconds: number;
};

export type ProgressEvent = {
  job_id: string;
  completed_blocks: number;
  total_blocks: number;
  completed_timesteps: number;
};

export type CompleteEvent = {
  job_id: string;
  status: "complete";
  result_s3_key: string | null;
  timesteps: number;
  vertex_count: number;
};

export type ErrorEvent = {
  job_id: string;
  code: string;
  message: string;
  retryable: boolean;
  last_timestep: number | null;
};

export type JobStreamEvent =
  | { id: number | null; event: "queued"; data: QueuedEvent }
  | { id: number | null; event: "warming"; data: WarmingEvent }
  | { id: number | null; event: "progress"; data: ProgressEvent }
  | { id: number | null; event: "chunk"; data: ChunkEnvelope }
  | { id: number | null; event: "complete"; data: CompleteEvent }
  | { id: number | null; event: "error"; data: ErrorEvent };

export type ActivationChunkPayload = {
  job_id: string;
  block_id: string;
  chunk_index: number;
  timestep_start: number;
  timestep_count: number;
  sample_rate_hz: number;
  vertex_count: number;
  dtype: "float32";
  shape: [number, number];
  activations: Uint8Array | Buffer;
};

export type DecodedActivationChunk = Omit<ActivationChunkPayload, "activations"> & {
  activations: Float32Array;
};

export type StreamJobEventsOptions = {
  jobId: string;
  token: string;
  fromEventId?: number | null;
  signal?: AbortSignal;
  onEvent: (event: JobStreamEvent) => void;
};

export function decodeBase64Msgpack<T>(envelope: ChunkEnvelope): T {
  const bytes = decodeBase64(envelope.payload);
  return msgpack.decode(bytes) as T;
}

export function decodeActivationChunk(envelope: ChunkEnvelope): DecodedActivationChunk {
  if (envelope.encoding !== "base64-msgpack") {
    throw new Error(`Unsupported activation encoding: ${envelope.encoding}`);
  }

  const decoded = decodeBase64Msgpack<ActivationChunkPayload>(envelope);
  if (decoded.dtype !== "float32") {
    throw new Error(`Unsupported activation dtype: ${decoded.dtype}`);
  }

  const bytes = toUint8Array(decoded.activations);
  const expectedBytes = decoded.shape[0] * decoded.shape[1] * Float32Array.BYTES_PER_ELEMENT;
  if (bytes.byteLength !== expectedBytes) {
    throw new Error("Activation byte length does not match the declared shape");
  }

  const activations = new Float32Array(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
  return { ...decoded, activations };
}

export function parseSseFrame(frame: string): JobStreamEvent | null {
  let eventName = "message";
  let eventId: number | null = null;
  const dataLines: string[] = [];

  for (const line of frame.replace(/\r\n/g, "\n").split("\n")) {
    if (!line || line.startsWith(":")) {
      continue;
    }

    const separatorIndex = line.indexOf(":");
    const field = separatorIndex === -1 ? line : line.slice(0, separatorIndex);
    const value = separatorIndex === -1 ? "" : line.slice(separatorIndex + 1).replace(/^ /, "");

    if (field === "event") {
      eventName = value;
    } else if (field === "id") {
      const parsed = Number.parseInt(value, 10);
      eventId = Number.isFinite(parsed) ? parsed : null;
    } else if (field === "data") {
      dataLines.push(value);
    }
  }

  if (dataLines.length === 0 || !isKnownJobEvent(eventName)) {
    return null;
  }

  return {
    id: eventId,
    event: eventName,
    data: JSON.parse(dataLines.join("\n"))
  } as JobStreamEvent;
}

export class SseFrameParser {
  private buffer = "";

  push(chunk: string): JobStreamEvent[] {
    this.buffer += chunk.replace(/\r\n/g, "\n");
    const frames = this.buffer.split("\n\n");
    this.buffer = frames.pop() ?? "";
    return frames.map(parseSseFrame).filter((event): event is JobStreamEvent => event !== null);
  }

  flush(): JobStreamEvent[] {
    if (!this.buffer.trim()) {
      this.buffer = "";
      return [];
    }

    const event = parseSseFrame(this.buffer);
    this.buffer = "";
    return event ? [event] : [];
  }
}

export async function streamJobEvents({ jobId, token, fromEventId, signal, onEvent }: StreamJobEventsOptions) {
  const url = new URL(`${API_URL}/api/jobs/${jobId}/stream`);
  if (fromEventId !== undefined && fromEventId !== null) {
    url.searchParams.set("from_event_id", String(fromEventId));
  }

  const response = await fetch(url, {
    headers: {
      accept: "text/event-stream",
      authorization: `Bearer ${token}`
    },
    signal
  });

  if (!response.ok || !response.body) {
    throw new Error(`Job stream failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseFrameParser();

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      for (const event of parser.flush()) {
        onEvent(event);
      }
      return;
    }

    const text = decoder.decode(value, { stream: true });
    for (const event of parser.push(text)) {
      onEvent(event);
    }
  }
}

function decodeBase64(payload: string): Uint8Array {
  if (typeof atob === "function") {
    const binary = atob(payload);
    return Uint8Array.from(binary, (char) => char.charCodeAt(0));
  }

  return Buffer.from(payload, "base64");
}

function toUint8Array(value: Uint8Array | Buffer): Uint8Array {
  return value instanceof Uint8Array ? value : new Uint8Array(value);
}

function isKnownJobEvent(event: string): event is JobStreamEvent["event"] {
  return event === "queued" || event === "warming" || event === "progress" || event === "chunk" || event === "complete" || event === "error";
}
