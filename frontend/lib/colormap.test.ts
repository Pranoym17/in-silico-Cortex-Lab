import { describe, expect, it } from "vitest";
import { activationToRgb, inferActivationDomain } from "./colormap";

describe("colormap", () => {
  it("maps low, neutral, and high activations to distinct colors", () => {
    const low = activationToRgb(-1, [-1, 1]);
    const neutral = activationToRgb(0, [-1, 1]);
    const high = activationToRgb(1, [-1, 1]);

    expect(low[2]).toBeGreaterThan(low[0]);
    expect(neutral[0]).toBeCloseTo(0.56);
    expect(high[0]).toBeGreaterThan(high[2]);
  });

  it("infers stable domains for normal and flat values", () => {
    expect(inferActivationDomain(new Float32Array([-2, 0, 3]))).toEqual([-2, 3]);
    expect(inferActivationDomain(new Float32Array([2, 2]))).toEqual([0, 4]);
  });
});
