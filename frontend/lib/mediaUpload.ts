import { CreateUploadIntentInput, StimulusBlock, UploadIntent } from "./api";
import { formatUploadError as formatJobUploadError } from "./jobErrors";
import { AUDIO_MIME_TYPES, IMAGE_MIME_TYPES } from "./stimulusMetadata";

const MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024;
const MAX_AUDIO_SIZE_BYTES = 100 * 1024 * 1024;
const MAX_IMAGE_PIXELS = 4096 * 4096;

export type UploadableBlock = Extract<StimulusBlock["type"], "image" | "audio">;

export type UploadedStimulusMetadata = {
  contentHash: string;
  payload: Record<string, unknown>;
};

export function bytesToHex(buffer: ArrayBuffer) {
  return [...new Uint8Array(buffer)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function computeSha256ContentHash(file: Blob) {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return `sha256:${bytesToHex(digest)}`;
}

export function validateUploadFile(kind: UploadableBlock, file: File) {
  if (kind === "image") {
    if (!IMAGE_MIME_TYPES.includes(file.type as (typeof IMAGE_MIME_TYPES)[number])) {
      throw new Error("Image uploads must be PNG, JPEG, or WebP.");
    }
    if (file.size > MAX_IMAGE_SIZE_BYTES) {
      throw new Error("Image uploads cannot exceed 10MB.");
    }
  }

  if (kind === "audio") {
    if (!AUDIO_MIME_TYPES.includes(file.type as (typeof AUDIO_MIME_TYPES)[number])) {
      throw new Error("Audio uploads must be MP3, WAV, MP4, or M4A.");
    }
    if (file.size > MAX_AUDIO_SIZE_BYTES) {
      throw new Error("Audio uploads cannot exceed 100MB.");
    }
  }
}

export function createUploadIntentInput(
  experimentId: string,
  block: StimulusBlock,
  file: File
): CreateUploadIntentInput {
  if (block.type !== "image" && block.type !== "audio") {
    throw new Error("Only image and audio blocks support file uploads.");
  }

  return {
    experiment_id: experimentId,
    block_id: block.id,
    kind: block.type,
    filename: file.name,
    mime_type: file.type,
    size_bytes: file.size
  };
}

export async function uploadFileToIntent(file: File, intent: UploadIntent) {
  const formData = new FormData();
  for (const [key, value] of Object.entries(intent.fields)) {
    formData.append(key, value);
  }
  formData.append("file", file);

  const response = await fetch(intent.upload_url, {
    method: intent.method,
    headers: intent.headers,
    body: formData
  });

  if (!response.ok) {
    throw new Error(`Upload failed with status ${response.status}`);
  }
}

export function formatUploadError(caught: unknown): string {
  return formatJobUploadError(caught);
}

export async function readImageDimensions(file: File) {
  const url = URL.createObjectURL(file);

  try {
    const image = new Image();
    const loaded = new Promise<{ width: number; height: number }>((resolve, reject) => {
      image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight });
      image.onerror = () => reject(new Error("Could not read image dimensions."));
    });
    image.src = url;
    const dimensions = await loaded;

    if (dimensions.width * dimensions.height > MAX_IMAGE_PIXELS) {
      throw new Error("Image dimensions cannot exceed 4096 x 4096 pixels.");
    }

    return dimensions;
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function readAudioDurationMs(file: File) {
  const url = URL.createObjectURL(file);

  try {
    const audio = new Audio();
    const loaded = new Promise<number | null>((resolve) => {
      audio.onloadedmetadata = () => resolve(Number.isFinite(audio.duration) ? Math.round(audio.duration * 1000) : null);
      audio.onerror = () => resolve(null);
    });
    audio.src = url;
    return await loaded;
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function buildUploadedStimulusMetadata(
  block: StimulusBlock,
  file: File,
  intent: UploadIntent
): Promise<UploadedStimulusMetadata> {
  const contentHash = await computeSha256ContentHash(file);

  if (block.type === "image") {
    const dimensions = await readImageDimensions(file);
    return {
      contentHash,
      payload: {
        ...block.payload,
        source: "upload",
        filename: file.name,
        s3_key: intent.object_key,
        mime_type: file.type,
        size_bytes: file.size,
        width: dimensions.width,
        height: dimensions.height
      }
    };
  }

  const durationMs = await readAudioDurationMs(file);
  return {
    contentHash,
    payload: {
      ...block.payload,
      source: "upload",
      filename: file.name,
      s3_key: intent.object_key,
      mime_type: file.type,
      size_bytes: file.size,
      duration_ms: durationMs,
      channels: typeof block.payload.channels === "number" ? block.payload.channels : 1,
      sample_rate_hz: typeof block.payload.sample_rate_hz === "number" ? block.payload.sample_rate_hz : 16000
    }
  };
}
