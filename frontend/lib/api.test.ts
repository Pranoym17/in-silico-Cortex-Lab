import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiFetch, apiJson, createBlock, createExperiment, createUploadIntent, reorderBlocks } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("apiFetch", () => {
  it("attaches bearer token when provided", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200 }));

    await apiFetch("/api/me", "token-123");

    const headers = fetchMock.mock.calls[0][1]?.headers as Headers;
    expect(headers.get("authorization")).toBe("Bearer token-123");
  });
});

describe("apiJson", () => {
  it("throws ApiError for non-ok responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Authentication required" }), { status: 401 })
    );

    await expect(apiJson("/api/me")).rejects.toMatchObject(
      new ApiError(401, { detail: "Authentication required" })
    );
  });
});

describe("createExperiment", () => {
  it("posts experiment metadata", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "exp_1", name: "FFA pilot" }), { status: 201 })
    );

    await createExperiment({ name: "FFA pilot" }, "token-123");

    expect(fetchMock.mock.calls[0][0]).toContain("/api/experiments");
    expect(fetchMock.mock.calls[0][1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[0][1]?.body).toBe(JSON.stringify({ name: "FFA pilot" }));
  });
});

describe("block helpers", () => {
  it("posts block metadata", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "block_1", type: "text" }), { status: 201 })
    );

    await createBlock(
      "exp_1",
      {
        type: "text",
        condition: "language",
        start_ms: 0,
        duration_ms: 5000,
        payload: { text: "hello" }
      },
      "token-123"
    );

    expect(fetchMock.mock.calls[0][0]).toContain("/api/experiments/exp_1/blocks");
    expect(fetchMock.mock.calls[0][1]?.method).toBe("POST");
  });

  it("reorders blocks using the contract envelope", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]", { status: 200 }));

    await reorderBlocks("exp_1", [{ id: "block_1", start_ms: 1000, duration_ms: 2000 }], "token-123");

    expect(fetchMock.mock.calls[0][0]).toContain("/api/experiments/exp_1/blocks/reorder");
    expect(fetchMock.mock.calls[0][1]?.method).toBe("PUT");
    expect(fetchMock.mock.calls[0][1]?.body).toBe(
      JSON.stringify({ blocks: [{ id: "block_1", start_ms: 1000, duration_ms: 2000 }] })
    );
  });
});

describe("upload helpers", () => {
  it("requests a presigned upload intent", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ upload_url: "https://s3.example/upload" }), { status: 201 })
    );

    await createUploadIntent(
      {
        experiment_id: "exp_1",
        block_id: "block_1",
        kind: "image",
        filename: "face.png",
        mime_type: "image/png",
        size_bytes: 512000
      },
      "token-123"
    );

    expect(fetchMock.mock.calls[0][0]).toContain("/api/uploads/presign");
    expect(fetchMock.mock.calls[0][1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[0][1]?.body).toBe(
      JSON.stringify({
        experiment_id: "exp_1",
        block_id: "block_1",
        kind: "image",
        filename: "face.png",
        mime_type: "image/png",
        size_bytes: 512000
      })
    );
  });
});
