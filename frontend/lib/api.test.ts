import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  apiFetch,
  apiJson,
  cancelJob,
  createBlock,
  createExperiment,
  createUploadIntent,
  getJobResult,
  getJobResultDownload,
  listExperimentJobs,
  reorderBlocks,
  runRsa,
  runExperiment
} from "./api";

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

  it("uses structured detail messages from API errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: { code: "upload_failed", message: "Upload setup failed." } }), { status: 503 })
    );

    await expect(apiJson("/api/uploads/presign")).rejects.toMatchObject(
      new ApiError(503, { detail: { code: "upload_failed", message: "Upload setup failed." } })
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

describe("runExperiment", () => {
  it("posts the run spec to the experiment run endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ job_id: "job_1", status: "queued" }), { status: 202 })
    );

    await runExperiment("exp_1", { blocks: [], settings: {} }, "token-123");

    expect(fetchMock.mock.calls[0][0]).toContain("/api/experiments/exp_1/run");
    expect(fetchMock.mock.calls[0][1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[0][1]?.body).toBe(JSON.stringify({ blocks: [], settings: {} }));
  });
});

describe("result helpers", () => {
  it("fetches job result metadata", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "result_1", s3_key: "results/job_1/activations.npz" }), { status: 200 })
    );

    await getJobResult("job_1", "token-123");

    expect(fetchMock.mock.calls[0][0]).toContain("/api/jobs/job_1/result");
    expect(fetchMock.mock.calls[0][1]?.method).toBeUndefined();
  });

  it("fetches a presigned result download URL", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ download_url: "https://s3.example/download" }), { status: 200 })
    );

    await getJobResultDownload("job_1", "token-123");

    expect(fetchMock.mock.calls[0][0]).toContain("/api/jobs/job_1/result/download");
    expect(fetchMock.mock.calls[0][1]?.method).toBeUndefined();
  });
});

describe("cancelJob", () => {
  it("posts to the job cancel endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "job_1", status: "cancelled" }), { status: 200 })
    );

    await cancelJob("job_1", "token-123");

    expect(fetchMock.mock.calls[0][0]).toContain("/api/jobs/job_1/cancel");
    expect(fetchMock.mock.calls[0][1]?.method).toBe("POST");
  });
});

describe("job helpers", () => {
  it("lists jobs for an experiment", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]", { status: 200 }));

    await listExperimentJobs("exp_1", "token-123");

    expect(fetchMock.mock.calls[0][0]).toContain("/api/experiments/exp_1/jobs");
    expect(fetchMock.mock.calls[0][1]?.method).toBeUndefined();
  });
});

describe("ML helpers", () => {
  it("posts RSA comparison job ids", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ rsa_score: 1 }), { status: 200 })
    );

    await runRsa("job_a", "job_b", "token-123");

    expect(fetchMock.mock.calls[0][0]).toContain("/api/ml/rsa");
    expect(fetchMock.mock.calls[0][1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[0][1]?.body).toBe(JSON.stringify({ job_id_a: "job_a", job_id_b: "job_b" }));
  });
});
