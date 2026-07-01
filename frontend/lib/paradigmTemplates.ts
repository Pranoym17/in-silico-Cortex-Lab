import { CreateBlockInput } from "./api";
import { assetBlock, getStimulusAsset } from "./stimulusCatalog";

export type ParadigmTemplate = {
  slug: string;
  name: string;
  description: string;
  blocks: CreateBlockInput[];
};

const TEXT_HASHES: Record<string, string> = {
  "She spread the warm bread with butter.": "6b0eb847ccd2a189f2659568a2b0ad8fb44a915c29e15869401c3d2a3efc852e",
  "She spread the warm bread with socks.": "dfd641c9517c9a41f16fd9702e97a4b1356a7d908c5003dee2971f072a080e27",
  "The gardener watered the flowers before noon.": "48629a24d99ec29f893de92364b85e7fc5b1bb5d201232ed1c4f0cef52c7cbdf",
  "The gardener watered the keyboard before noon.": "4f096092c690950ebb12a82c0972c5d031a51d673f5d7d88f5ef9d607d8f910d",
  "The child drank the cold glass of milk.": "673b7b2b7b5e80782bd6bbd12277de2183e9529951519701de9ca24c2ae80fd3",
  "The child drank the cold glass of clouds.": "761ac72934e7acbd839045019db0631e5ec30e2aa5bc045f5ae27b28eb39a5c9",
  "They mailed the letter at the post office.": "1b57e687410e0ada81f47a3b05b4698c9f4f572706789c547b8be8ec411ee124",
  "They mailed the letter at the swimming pool.": "ef4d05f392eb1970f61c0c15b9b0fe977f8e83eec9216f8e11cf22730985b4bd",
  "The mechanic repaired the damaged engine.": "5c09187ea14ae371dfeaab7392639ce3927f19e1ad123daa7c755ac23e2fd19f",
  "The mechanic repaired the damaged sandwich.": "54150ffdba76d45e23851096148f8edc13720c78851ce557ca583c95e40f1618",
  "The musician tuned the guitar before playing.": "3077a0489a92d65996deccee50d3dcf214f6344ccf592ec70f2acad8b0f2efd2",
  "The musician tuned the mountain before playing.": "ff8930c28f10233a30e1cd35de61dbb68590abdc63b8fc0124232f49c942fc29",
  "The chef sliced the vegetables with a knife.": "5aad2d25996463c9abe4e1b1f75344894d09adba8b759058fc06657f28646fe3",
  "The chef sliced the vegetables with a pillow.": "79844115e201de4204a2cc860544826e87e1706f82b0fad6fae5729e6b7e9538",
  "The student opened the book to read.": "6e92da890f4bb95410503b41879b504a2c802d417e8cb99c0aefccc8e2899143",
  "The student opened the thunder to read.": "d49e3922f73dee3723e8066b3cde2ef8d6d74bb59b9cfa391166e842a301c186",
  "The researcher described a calm walk through a quiet forest.": "d245c35690f8e76b7e0099a3fb253644a753bef95de292ca420d9189571c8ebc",
  "A calm walk through a quiet forest can focus attention.": "06cb5ed090a275b3080815bd79224f411c3de226c9bc9989a5d4ffe091041d51"
};

function textBlock(startMs: number, condition: string, text: string): CreateBlockInput {
  const hash = TEXT_HASHES[text];
  if (!hash) {
    throw new Error(`Missing curated text hash: ${text}`);
  }
  return {
    type: "text",
    condition,
    start_ms: startMs,
    duration_ms: 5000,
    content_hash: `sha256:${hash}`,
    payload: { text, voice: "tribe_official_gtts" }
  };
}

function imageBlock(id: string, startMs: number, condition: string, position?: string) {
  const block = assetBlock(getStimulusAsset(id), startMs, condition);
  if (position && block.payload) {
    block.payload.display = { mode: "center", position };
  }
  return block;
}

function alternatingAssets(prefixA: string, prefixB: string, conditionA: string, conditionB: string, count: number) {
  const blocks: CreateBlockInput[] = [];
  for (let index = 1; index <= count; index += 1) {
    blocks.push(imageBlock(`${prefixA}-${String(index).padStart(3, "0")}`, (index - 1) * 4000, conditionA));
    blocks.push(imageBlock(`${prefixB}-${String(index).padStart(3, "0")}`, (index - 1) * 4000 + 2000, conditionB));
  }
  return blocks;
}

const n400Pairs = [
  ["She spread the warm bread with butter.", "She spread the warm bread with socks."],
  ["The gardener watered the flowers before noon.", "The gardener watered the keyboard before noon."],
  ["The child drank the cold glass of milk.", "The child drank the cold glass of clouds."],
  ["They mailed the letter at the post office.", "They mailed the letter at the swimming pool."],
  ["The mechanic repaired the damaged engine.", "The mechanic repaired the damaged sandwich."],
  ["The musician tuned the guitar before playing.", "The musician tuned the mountain before playing."],
  ["The chef sliced the vegetables with a knife.", "The chef sliced the vegetables with a pillow."],
  ["The student opened the book to read.", "The student opened the thunder to read."]
];

export const PARADIGM_TEMPLATES: ParadigmTemplate[] = [
  {
    slug: "ffa-face-house",
    name: "FFA Face vs House",
    description: "Ten schematic faces alternating with ten house scenes.",
    blocks: alternatingAssets("face", "house", "faces", "houses", 10)
  },
  {
    slug: "n400",
    name: "N400 Congruency",
    description: "Eight congruent and eight incongruent sentence blocks.",
    blocks: n400Pairs.flatMap(([congruent, incongruent], index) => [
      textBlock(index * 10_000, "congruent", congruent),
      textBlock(index * 10_000 + 5000, "incongruent", incongruent)
    ])
  },
  {
    slug: "visual-eccentricity",
    name: "Visual Eccentricity Map",
    description: "Pattern stimuli positioned across the visual field.",
    blocks: ["center", "left", "right", "upper", "lower", "upper-left", "upper-right", "center"].map(
      (position, index) => imageBlock(`pattern-${String(index + 1).padStart(3, "0")}`, index * 2000, position, position)
    )
  },
  {
    slug: "emotion-processing",
    name: "Emotion Processing",
    description: "Neutral and happy schematic expressions with no identity or personality-right restrictions.",
    blocks: alternatingAssets("face", "face", "neutral", "happy", 6).map((block, index) => {
      if (index % 2 === 1) {
        return imageBlock(`face-${String(21 + Math.floor(index / 2)).padStart(3, "0")}`, block.start_ms, "happy");
      }
      return block;
    })
  },
  {
    slug: "speech-music",
    name: "Speech vs Music",
    description: "Official TRIBE text-to-speech blocks alternating with first-party instrumental tones.",
    blocks: [
      textBlock(0, "speech", "The researcher described a calm walk through a quiet forest."),
      assetBlock(getStimulusAsset("music-major-01"), 5000, "music"),
      textBlock(11_000, "speech", "A calm walk through a quiet forest can focus attention."),
      assetBlock(getStimulusAsset("music-minor-01"), 16_000, "music")
    ]
  },
  {
    slug: "reading-listening",
    name: "Reading vs Listening",
    description: "Rendered words contrasted with matched language delivered through the official speech path.",
    blocks: [
      imageBlock("word-001", 0, "reading"),
      textBlock(2000, "listening", "The researcher described a calm walk through a quiet forest."),
      imageBlock("word-002", 7000, "reading"),
      textBlock(9000, "listening", "A calm walk through a quiet forest can focus attention.")
    ]
  }
];
