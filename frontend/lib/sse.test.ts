import { describe, expect, it } from "vitest";
import msgpack from "msgpack-lite";
import { decodeBase64Msgpack } from "./sse";

describe("decodeBase64Msgpack", () => {
  it("decodes the SSE chunk envelope payload", () => {
    const payload = Buffer.from(msgpack.encode({ vertex_count: 20000 })).toString("base64");

    expect(decodeBase64Msgpack<{ vertex_count: number }>({ encoding: "base64-msgpack", payload })).toEqual({
      vertex_count: 20000
    });
  });
});

