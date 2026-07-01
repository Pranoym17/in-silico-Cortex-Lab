import { describe, expect, it } from "vitest";
import { PARADIGM_TEMPLATES } from "./paradigmTemplates";
import { STIMULUS_ASSETS, searchStimulusAssets } from "./stimulusCatalog";

describe("PARADIGM_TEMPLATES", () => {
  it("keeps templates within the checkpoint two duration cap", () => {
    for (const template of PARADIGM_TEMPLATES) {
      const duration = template.blocks.reduce((max, block) => Math.max(max, block.start_ms + block.duration_ms), 0);
      expect(duration).toBeLessThanOrEqual(300000);
    }
  });

  it("contains all launch block types across templates", () => {
    const types = new Set(PARADIGM_TEMPLATES.flatMap((template) => template.blocks.map((block) => block.type)));

    expect(types).toEqual(new Set(["image", "text", "audio"]));
  });

  it("contains all six launch paradigms with run-ready content", () => {
    expect(PARADIGM_TEMPLATES.map((template) => template.slug)).toEqual([
      "ffa-face-house",
      "n400",
      "visual-eccentricity",
      "emotion-processing",
      "speech-music",
      "reading-listening"
    ]);

    for (const template of PARADIGM_TEMPLATES) {
      for (const block of template.blocks) {
        expect(block.content_hash).toMatch(/^sha256:[a-f0-9]{64}$/);
        if (block.type === "image" || block.type === "audio") {
          expect(block.payload?.s3_key).toMatch(/^stimulus-library\/v1\//);
          expect(block.payload?.source).toBe("library");
        }
        expect(JSON.stringify(block)).not.toContain("placeholder");
      }
    }
  });

  it("ships a searchable CC0 catalog of approximately 200 stimuli", () => {
    expect(STIMULUS_ASSETS).toHaveLength(204);
    expect(STIMULUS_ASSETS.every((asset) => asset.license === "CC0-1.0")).toBe(true);
    expect(STIMULUS_ASSETS.every((asset) => asset.redistribution_permitted)).toBe(true);
    expect(searchStimulusAssets("face", "faces").length).toBeGreaterThanOrEqual(40);
    expect(new Set(STIMULUS_ASSETS.map((asset) => asset.category))).toEqual(
      new Set(["faces", "scenes", "objects", "words", "patterns", "audio"])
    );
  });
});

