import { CreateBlockInput } from "@/lib/api";

export type ParadigmTemplate = {
  slug: string;
  name: string;
  description: string;
  blocks: CreateBlockInput[];
};

function imageBlock(startMs: number, condition: string, libraryId: string): CreateBlockInput {
  return {
    type: "image",
    condition,
    start_ms: startMs,
    duration_ms: 2000,
    payload: {
      source: "library",
      library_id: libraryId,
      display: { mode: "center" }
    }
  };
}

function textBlock(startMs: number, condition: string, text: string): CreateBlockInput {
  return {
    type: "text",
    condition,
    start_ms: startMs,
    duration_ms: 5000,
    payload: {
      text,
      voice: "kokoro_default"
    }
  };
}

function audioBlock(startMs: number, condition: string, filename: string): CreateBlockInput {
  return {
    type: "audio",
    condition,
    start_ms: startMs,
    duration_ms: 10000,
    payload: {
      source: "placeholder",
      filename,
      mime_type: "audio/wav"
    }
  };
}

export const PARADIGM_TEMPLATES: ParadigmTemplate[] = [
  {
    slug: "ffa-face-house",
    name: "FFA Face vs House",
    description: "Alternating face and house image blocks for a fusiform face area pilot.",
    blocks: [
      imageBlock(0, "faces", "face_001"),
      imageBlock(2000, "houses", "house_001"),
      imageBlock(4000, "faces", "face_002"),
      imageBlock(6000, "houses", "house_002"),
      imageBlock(8000, "faces", "face_003"),
      imageBlock(10000, "houses", "house_003")
    ]
  },
  {
    slug: "n400",
    name: "N400 Congruency",
    description: "Short congruent and incongruent sentence blocks for language comprehension.",
    blocks: [
      textBlock(0, "congruent", "She spread the warm bread with butter."),
      textBlock(5000, "incongruent", "She spread the warm bread with socks."),
      textBlock(10000, "congruent", "The gardener watered the flowers before noon."),
      textBlock(15000, "incongruent", "The gardener watered the keyboard before noon.")
    ]
  },
  {
    slug: "speech-music",
    name: "Speech vs Music",
    description: "Placeholder audio blocks comparing spoken language and instrumental music.",
    blocks: [
      audioBlock(0, "speech", "spoken-passage-placeholder.wav"),
      audioBlock(10000, "music", "instrumental-music-placeholder.wav"),
      audioBlock(20000, "speech", "spoken-passage-2-placeholder.wav"),
      audioBlock(30000, "music", "instrumental-music-2-placeholder.wav")
    ]
  }
];

