export type Rgb = readonly [number, number, number];

const COOL: Rgb = [0.1, 0.34, 0.82];
const NEUTRAL: Rgb = [0.56, 0.6, 0.66];
const WARM: Rgb = [0.96, 0.32, 0.14];

export function activationToRgb(value: number, domain: readonly [number, number]): Rgb {
  const [min, max] = domain;
  if (!Number.isFinite(value) || !Number.isFinite(min) || !Number.isFinite(max) || min >= max) {
    return NEUTRAL;
  }

  const t = clamp01((value - min) / (max - min));
  if (t <= 0.5) {
    return interpolateRgb(COOL, NEUTRAL, t * 2);
  }
  return interpolateRgb(NEUTRAL, WARM, (t - 0.5) * 2);
}

export function inferActivationDomain(values: Float32Array | readonly number[]): [number, number] {
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;

  for (const value of values) {
    if (!Number.isFinite(value)) {
      continue;
    }
    min = Math.min(min, value);
    max = Math.max(max, value);
  }

  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return [-1, 1];
  }
  if (min === max) {
    const radius = Math.max(Math.abs(min), 1);
    return [min - radius, max + radius];
  }
  return [min, max];
}

function interpolateRgb(from: Rgb, to: Rgb, t: number): Rgb {
  const clamped = clamp01(t);
  return [
    from[0] + (to[0] - from[0]) * clamped,
    from[1] + (to[1] - from[1]) * clamped,
    from[2] + (to[2] - from[2]) * clamped
  ];
}

function clamp01(value: number) {
  return Math.max(0, Math.min(1, value));
}
