import { CreateUploadIntentInput, StimulusBlock, UploadIntent } from "./api";
import { formatUploadError as formatJobUploadError } from "./jobErrors";
import { AUDIO_MIME_TYPES, IMAGE_MIME_TYPES, VIDEO_MIME_TYPES } from "./stimulusMetadata";

const MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024;
const MAX_AUDIO_SIZE_BYTES = 100 * 1024 * 1024;
const MAX_VIDEO_SIZE_BYTES = 100 * 1024 * 1024;
export const MAX_VIDEO_DURATION_MS = 10000;
const MAX_IMAGE_PIXELS = 4096 * 4096;

export type UploadableBlock = Extract<StimulusBlock["type"], "image" | "audio" | "video">;

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

  if (kind === "video") {
    if (!VIDEO_MIME_TYPES.includes(file.type as (typeof VIDEO_MIME_TYPES)[number])) {
      throw new Error("Video uploads must be MP4, WebM, or MOV.");
    }
    if (file.size > MAX_VIDEO_SIZE_BYTES) {
      throw new Error("Video uploads cannot exceed 100MB.");
    }
  }
}

export function createUploadIntentInput(
  experimentId: string,
  block: StimulusBlock,
  file: File
): CreateUploadIntentInput {
  if (block.type !== "image" && block.type !== "audio" && block.type !== "video") {
    throw new Error("Only image, audio, and video blocks support file uploads.");
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
  return readMediaDurationMs(file, "audio");
}

export async function readVideoDurationMs(file: File) {
  return readMediaDurationMs(file, "video");
}

async function readMediaDurationMs(file: File, kind: "audio" | "video") {
  const url = URL.createObjectURL(file);

  try {
    const media = document.createElement(kind);
    const loaded = new Promise<number | null>((resolve) => {
      media.onloadedmetadata = () => resolve(Number.isFinite(media.duration) ? Math.round(media.duration * 1000) : null);
      media.onerror = () => resolve(null);
    });
    media.src = url;
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

  const durationMs = block.type === "video" ? await readVideoDurationMs(file) : await readAudioDurationMs(file);
  if (durationMs === null) {
    throw new Error(`Could not read ${block.type} duration. Choose a supported, non-corrupt file.`);
  }
  if (block.type === "video" && durationMs > MAX_VIDEO_DURATION_MS) {
    throw new Error("Video blocks cannot exceed 10 seconds.");
  }
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
      ...(block.type === "audio"
        ? {
            channels: typeof block.payload.channels === "number" ? block.payload.channels : 1,
            sample_rate_hz: typeof block.payload.sample_rate_hz === "number" ? block.payload.sample_rate_hz : 16000
          }
        : {})
    }
  };
}
