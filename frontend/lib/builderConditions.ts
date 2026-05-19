import { StimulusBlock } from "@/lib/api";

export type ConditionSummary = {
  name: string;
  count: number;
};

export function getConditionSummaries(blocks: StimulusBlock[]): ConditionSummary[] {
  const counts = new Map<string, number>();

  for (const block of blocks) {
    const name = block.condition?.trim() || "unlabeled";
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }

  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

export function getConditionColor(name: string) {
  const palette = ["#4fb3ff", "#ff7a90", "#7bd88f", "#ffd166", "#b794f4", "#4dd4c6"];
  const index = [...name].reduce((sum, char) => sum + char.charCodeAt(0), 0) % palette.length;
  return palette[index];
}

