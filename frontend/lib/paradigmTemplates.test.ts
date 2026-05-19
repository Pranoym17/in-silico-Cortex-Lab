import { describe, expect, it } from "vitest";
import { PARADIGM_TEMPLATES } from "./paradigmTemplates";

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
});

