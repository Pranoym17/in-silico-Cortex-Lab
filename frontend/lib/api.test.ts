import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiFetch, apiJson, createExperiment } from "./api";

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

