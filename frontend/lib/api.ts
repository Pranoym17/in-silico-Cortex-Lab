export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ApiErrorBody = {
  detail?: string;
};

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody | unknown;

  constructor(status: number, body: ApiErrorBody | unknown) {
    const message =
      body && typeof body === "object" && "detail" in body && typeof body.detail === "string"
        ? body.detail
        : `Request failed with status ${status}`;
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export type ExperimentStatus = "draft" | "ready" | "archived";

export type Experiment = {
  id: string;
  owner_id: string;
  name: string;
  description: string | null;
  status: ExperimentStatus;
  is_public: boolean;
  slug: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateExperimentInput = {
  name: string;
  description?: string | null;
};

export type UpdateExperimentInput = Partial<{
  name: string;
  description: string | null;
  status: ExperimentStatus;
}>;

export type StimulusBlockType = "image" | "text" | "audio";

export type StimulusBlock = {
  id: string;
  experiment_id: string;
  type: StimulusBlockType;
  condition: string | null;
  start_ms: number;
  duration_ms: number;
  content_hash: string | null;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type CreateBlockInput = {
  type: StimulusBlockType;
  condition?: string | null;
  start_ms: number;
  duration_ms: number;
  content_hash?: string | null;
  payload?: Record<string, unknown>;
};

export type UpdateBlockInput = Partial<{
  condition: string | null;
  start_ms: number;
  duration_ms: number;
  content_hash: string | null;
  payload: Record<string, unknown>;
}>;

export type ReorderBlockInput = {
  id: string;
  start_ms: number;
  duration_ms: number;
};

export async function apiFetch(path: string, token?: string | null, init: RequestInit = {}) {
  const headers = new Headers(init.headers);

  if (init.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }

  if (token) {
    headers.set("authorization", `Bearer ${token}`);
  }

  return fetch(`${API_URL}${path}`, {
    ...init,
    headers
  });
}

export async function apiJson<T>(path: string, token?: string | null, init: RequestInit = {}): Promise<T> {
  const response = await apiFetch(path, token, init);

  if (response.status === 204) {
    return undefined as T;
  }

  const body = await response.json().catch(() => undefined);

  if (!response.ok) {
    throw new ApiError(response.status, body);
  }

  return body as T;
}

export function listExperiments(token?: string | null) {
  return apiJson<Experiment[]>("/api/experiments", token);
}

export function getExperiment(id: string, token?: string | null) {
  return apiJson<Experiment>(`/api/experiments/${id}`, token);
}

export function createExperiment(input: CreateExperimentInput, token?: string | null) {
  return apiJson<Experiment>("/api/experiments", token, {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function updateExperiment(id: string, input: UpdateExperimentInput, token?: string | null) {
  return apiJson<Experiment>(`/api/experiments/${id}`, token, {
    method: "PATCH",
    body: JSON.stringify(input)
  });
}

export function archiveExperiment(id: string, token?: string | null) {
  return apiJson<void>(`/api/experiments/${id}`, token, {
    method: "DELETE"
  });
}

export function listBlocks(experimentId: string, token?: string | null) {
  return apiJson<StimulusBlock[]>(`/api/experiments/${experimentId}/blocks`, token);
}

export function createBlock(experimentId: string, input: CreateBlockInput, token?: string | null) {
  return apiJson<StimulusBlock>(`/api/experiments/${experimentId}/blocks`, token, {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function updateBlock(
  experimentId: string,
  blockId: string,
  input: UpdateBlockInput,
  token?: string | null
) {
  return apiJson<StimulusBlock>(`/api/experiments/${experimentId}/blocks/${blockId}`, token, {
    method: "PATCH",
    body: JSON.stringify(input)
  });
}

export function deleteBlock(experimentId: string, blockId: string, token?: string | null) {
  return apiJson<void>(`/api/experiments/${experimentId}/blocks/${blockId}`, token, {
    method: "DELETE"
  });
}

export function reorderBlocks(experimentId: string, blocks: ReorderBlockInput[], token?: string | null) {
  return apiJson<StimulusBlock[]>(`/api/experiments/${experimentId}/blocks/reorder`, token, {
    method: "PUT",
    body: JSON.stringify({ blocks })
  });
}
