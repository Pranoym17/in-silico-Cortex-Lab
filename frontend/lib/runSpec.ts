import { StimulusBlock } from "./api";

export type RunBlock = {
  id: string;
  type: StimulusBlock["type"];
  condition: string | null;
  start_ms: number;
  duration_ms: number;
  content_hash: string;
};

export type ImageRunBlock = RunBlock & {
  type: "image";
  s3_key: string;
  mime_type: string;
  display: { mode: string };
};

export type TextRunBlock = RunBlock & {
  type: "text";
  text: string;
  voice: string;
};

export type AudioRunBlock = RunBlock & {
  type: "audio";
  s3_key: string;
  mime_type: string;
  channels: number;
  sample_rate_hz: number;
};

export type RunExperimentInput = {
  blocks: Array<ImageRunBlock | TextRunBlock | AudioRunBlock>;
  settings: {
    hrf_offset_ms: number;
    target_sample_rate_hz: number;
    surface: "fsaverage5";
    atlas: "desikan-killiany";
  };
};

function requireString(value: unknown, message: string) {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(message);
  }

  return value;
}

function requireContentHash(block: StimulusBlock) {
  if (!block.content_hash) {
    throw new Error("Every block needs a content hash before running.");
  }

  return block.content_hash;
}

function getDisplayMode(payload: Record<string, unknown>) {
  const display = typeof payload.display === "object" && payload.display ? payload.display : {};
  return "mode" in display && typeof display.mode === "string" ? display.mode : "center";
}

export function toRunBlock(block: StimulusBlock): ImageRunBlock | TextRunBlock | AudioRunBlock {
  const base = {
    id: block.id,
    type: block.type,
    condition: block.condition,
    start_ms: block.start_ms,
    duration_ms: block.duration_ms,
    content_hash: requireContentHash(block)
  };

  if (block.type === "image") {
    return {
      ...base,
      type: "image",
      s3_key: requireString(block.payload.s3_key, "Image blocks need an S3 object key before running."),
      mime_type: requireString(block.payload.mime_type, "Image blocks need a MIME type before running."),
      display: { mode: getDisplayMode(block.payload) }
    };
  }

  if (block.type === "audio") {
    return {
      ...base,
      type: "audio",
      s3_key: requireString(block.payload.s3_key, "Audio blocks need an S3 object key before running."),
      mime_type: requireString(block.payload.mime_type, "Audio blocks need a MIME type before running."),
      channels: typeof block.payload.channels === "number" ? block.payload.channels : 1,
      sample_rate_hz: typeof block.payload.sample_rate_hz === "number" ? block.payload.sample_rate_hz : 16000
    };
  }

  return {
    ...base,
    type: "text",
    text: requireString(block.payload.text, "Text blocks need stimulus text before running."),
    voice: typeof block.payload.voice === "string" && block.payload.voice.trim() ? block.payload.voice : "kokoro_default"
  };
}

export function buildRunExperimentInput(blocks: StimulusBlock[]): RunExperimentInput {
  return {
    blocks: [...blocks].sort((a, b) => a.start_ms - b.start_ms).map(toRunBlock),
    settings: {
      hrf_offset_ms: 5000,
      target_sample_rate_hz: 2,
      surface: "fsaverage5",
      atlas: "desikan-killiany"
    }
  };
}
