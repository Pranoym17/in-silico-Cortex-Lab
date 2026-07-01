import catalog from "../public/stimuli/v1/catalog.json";
import { CreateBlockInput } from "./api";

export type StimulusAsset = {
  id: string;
  title: string;
  category: "faces" | "scenes" | "objects" | "words" | "patterns" | "audio";
  modality: "image" | "audio";
  tags: string[];
  public_path: string;
  object_key: string;
  mime_type: string;
  sha256: string;
  license: "CC0-1.0";
  license_url: string;
  creator: string;
  source_url: string;
  attribution: string;
  redistribution_permitted: boolean;
  generated: boolean;
  duration_ms?: number;
  sample_rate_hz?: number;
};

export const STIMULUS_ASSETS = catalog.assets as StimulusAsset[];
export const STIMULUS_CATEGORIES = ["faces", "scenes", "objects", "words", "patterns", "audio"] as const;

export function getStimulusAsset(id: string) {
  const asset = STIMULUS_ASSETS.find((item) => item.id === id);
  if (!asset) {
    throw new Error(`Unknown stimulus asset: ${id}`);
  }
  return asset;
}

export function searchStimulusAssets(query: string, category = "all") {
  const normalized = query.trim().toLowerCase();
  return STIMULUS_ASSETS.filter(
    (asset) =>
      (category === "all" || asset.category === category) &&
      (!normalized ||
        asset.title.toLowerCase().includes(normalized) ||
        asset.tags.some((tag) => tag.includes(normalized)))
  );
}

export function assetBlock(asset: StimulusAsset, startMs: number, condition: string): CreateBlockInput {
  const durationMs = asset.duration_ms ?? 2000;
  if (asset.modality === "audio") {
    return {
      type: "audio",
      condition,
      start_ms: startMs,
      duration_ms: durationMs,
      content_hash: `sha256:${asset.sha256}`,
      payload: {
        source: "library",
        library_id: asset.id,
        filename: asset.public_path.split("/").at(-1),
        public_path: asset.public_path,
        s3_key: asset.object_key,
        mime_type: asset.mime_type,
        duration_ms: durationMs,
        channels: 1,
        sample_rate_hz: asset.sample_rate_hz ?? 16000,
        attribution: asset.attribution,
        license: asset.license
      }
    };
  }
  return {
    type: "image",
    condition,
    start_ms: startMs,
    duration_ms: durationMs,
    content_hash: `sha256:${asset.sha256}`,
    payload: {
      source: "library",
      library_id: asset.id,
      public_path: asset.public_path,
      s3_key: asset.object_key,
      mime_type: asset.mime_type,
      width: 512,
      height: 384,
      display: { mode: "center" },
      attribution: asset.attribution,
      license: asset.license
    }
  };
}
