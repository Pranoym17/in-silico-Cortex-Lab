import { StimulusBlock } from "@/lib/api";

export const IMAGE_MIME_TYPES = ["image/png", "image/jpeg", "image/webp"] as const;
export const AUDIO_MIME_TYPES = ["audio/mpeg", "audio/wav", "audio/mp4", "audio/x-m4a", "audio/webm"] as const;

export function normalizeContentHash(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  return trimmed.startsWith("sha256:") ? trimmed : `sha256:${trimmed}`;
}

export function getStimulusReadinessIssues(block: StimulusBlock) {
  const issues: string[] = [];

  if (!block.content_hash) {
    issues.push("Content hash is required before running.");
  }

  if (block.type === "text") {
    const text = typeof block.payload.text === "string" ? block.payload.text : "";
    if (!text.trim()) {
      issues.push("Text blocks need stimulus text.");
    }
  }

  if (block.type === "image") {
    if (typeof block.payload.s3_key !== "string" || !block.payload.s3_key.trim()) {
      issues.push("Image blocks need an uploaded S3 object key before running.");
    }
  }

  if (block.type === "audio") {
    if (typeof block.payload.s3_key !== "string" || !block.payload.s3_key.trim()) {
      issues.push("Audio blocks need an uploaded S3 object key before running.");
    }
  }

  return issues;
}
