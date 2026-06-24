import { describe, expect, it } from "vitest";
import { OptimizerSseFrameParser, parseOptimizerSseFrame } from "./optimizerStream";

describe("parseOptimizerSseFrame", () => {
  it("parses generation events", () => {
    const event = parseOptimizerSseFrame(
      'event: generation\nid: 2\ndata: {"optimizer_job_id":"opt_1","generation":1,"best_score":0.2,"best_stimulus":"hello","candidates":[]}\n\n'
    );

    expect(event?.event).toBe("generation");
    expect(event?.id).toBe(2);
    expect(event?.data.best_stimulus).toBe("hello");
  });
});

describe("OptimizerSseFrameParser", () => {
  it("buffers split SSE frames", () => {
    const parser = new OptimizerSseFrameParser();

    expect(parser.push('event: complete\ndata: {"optimizer_job_id":"opt')).toEqual([]);
    const events = parser.push(
      '_1","status":"complete","target_region":"x","direction":"maximize","best_score":1,"best_stimulus":"text","generations":[]}\n\n'
    );

    expect(events).toHaveLength(1);
    expect(events[0].event).toBe("complete");
  });
});
