export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ApiErrorBody = {
  detail?: string | { code?: string; message?: string };
};

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody | unknown;

  constructor(status: number, body: ApiErrorBody | unknown) {
    const message = getApiErrorMessage(status, body);
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function getApiErrorMessage(status: number, body: ApiErrorBody | unknown) {
  if (!body || typeof body !== "object" || !("detail" in body)) {
    return `Request failed with status ${status}`;
  }

  if (typeof body.detail === "string") {
    return body.detail;
  }

  if (body.detail && typeof body.detail === "object" && "message" in body.detail && typeof body.detail.message === "string") {
    return body.detail.message;
  }

  return `Request failed with status ${status}`;
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

export type UploadKind = "image" | "audio";

export type CreateUploadIntentInput = {
  experiment_id: string;
  block_id?: string | null;
  kind: UploadKind;
  filename: string;
  mime_type: string;
  size_bytes: number;
};

export type UploadIntent = {
  method: "POST";
  upload_url: string;
  object_key: string;
  headers: Record<string, string>;
  fields: Record<string, string>;
  expires_in_seconds: number;
  content_hash_algorithm: "sha256";
};

export type RunExperimentResponse = {
  job_id: string;
  experiment_id: string;
  status: "queued" | "complete";
  stream_url: string;
  user_id?: string | null;
};

export type JobStatus = "queued" | "warming" | "running" | "streaming" | "complete" | "failed" | "cancelled";

export type Job = {
  id: string;
  experiment_id: string;
  owner_id: string;
  status: JobStatus;
  run_spec: Record<string, unknown>;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ResultMetadata = {
  id: string;
  job_id: string;
  experiment_id: string;
  owner_id: string;
  s3_key: string;
  format: string;
  dtype: string;
  shape: number[];
  vertex_count: number;
  timestep_count: number;
  sample_rate_hz: number | null;
  model_name: string;
  model_version: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ResultDownload = {
  result_id: string;
  job_id: string;
  download_url: string;
  expires_in_seconds: number;
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

export function createUploadIntent(input: CreateUploadIntentInput, token?: string | null) {
  return apiJson<UploadIntent>("/api/uploads/presign", token, {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function runExperiment(experimentId: string, input: unknown, token?: string | null) {
  return apiJson<RunExperimentResponse>(`/api/experiments/${experimentId}/run`, token, {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function getJob(jobId: string, token?: string | null) {
  return apiJson<Job>(`/api/jobs/${jobId}`, token);
}

export function getJobResult(jobId: string, token?: string | null) {
  return apiJson<ResultMetadata>(`/api/jobs/${jobId}/result`, token);
}

export function getJobResultDownload(jobId: string, token?: string | null) {
  return apiJson<ResultDownload>(`/api/jobs/${jobId}/result/download`, token);
}

export function cancelJob(jobId: string, token?: string | null) {
  return apiJson<Job>(`/api/jobs/${jobId}/cancel`, token, { method: "POST" });
}
