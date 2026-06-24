import { API_URL } from "./api";

export type OptimizerCandidate = {
  text: string;
  score: number;
};

export type OptimizerGenerationEvent = {
  optimizer_job_id: string;
  generation: number;
  best_score: number;
  best_stimulus: string;
  candidates: OptimizerCandidate[];
};

export type OptimizerCompleteEvent = {
  optimizer_job_id: string;
  status: "complete";
  target_region: string;
  direction: string;
  best_score: number;
  best_stimulus: string;
  generations: OptimizerGenerationEvent[];
};

export type OptimizerStreamEvent =
  | { id: number | null; event: "queued"; data: { optimizer_job_id: string; status: string; target_region: string; direction: string } }
  | { id: number | null; event: "generation"; data: OptimizerGenerationEvent }
  | { id: number | null; event: "complete"; data: OptimizerCompleteEvent }
  | { id: number | null; event: "error"; data: { optimizer_job_id: string; code: string; message: string } };

export function parseOptimizerSseFrame(frame: string): OptimizerStreamEvent | null {
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

  if (dataLines.length === 0 || !isKnownOptimizerEvent(eventName)) {
    return null;
  }

  return { id: eventId, event: eventName, data: JSON.parse(dataLines.join("\n")) } as OptimizerStreamEvent;
}

export class OptimizerSseFrameParser {
  private buffer = "";

  push(chunk: string): OptimizerStreamEvent[] {
    this.buffer += chunk.replace(/\r\n/g, "\n");
    const frames = this.buffer.split("\n\n");
    this.buffer = frames.pop() ?? "";
    return frames.map(parseOptimizerSseFrame).filter((event): event is OptimizerStreamEvent => event !== null);
  }

  flush(): OptimizerStreamEvent[] {
    if (!this.buffer.trim()) {
      this.buffer = "";
      return [];
    }
    const event = parseOptimizerSseFrame(this.buffer);
    this.buffer = "";
    return event ? [event] : [];
  }
}

export async function streamOptimizerEvents({
  optimizerJobId,
  token,
  signal,
  onEvent
}: {
  optimizerJobId: string;
  token: string;
  signal?: AbortSignal;
  onEvent: (event: OptimizerStreamEvent) => void;
}) {
  const response = await fetch(`${API_URL}/api/ml/optimize/${optimizerJobId}/stream`, {
    headers: {
      accept: "text/event-stream",
      authorization: `Bearer ${token}`
    },
    signal
  });

  if (!response.ok || !response.body) {
    throw new Error(`Optimizer stream failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new OptimizerSseFrameParser();

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

function isKnownOptimizerEvent(event: string): event is OptimizerStreamEvent["event"] {
  return event === "queued" || event === "generation" || event === "complete" || event === "error";
}
