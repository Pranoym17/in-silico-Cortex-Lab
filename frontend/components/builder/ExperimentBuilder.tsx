"use client";

import { useExperimentStore } from "@/store/experimentStore";

export function ExperimentBuilder({ experimentId }: { experimentId: string }) {
  const blocks = useExperimentStore((state) => state.blocks);

  return (
    <main className="shell">
      <h1>Builder</h1>
      <section className="panel">
        <p>Experiment: {experimentId}</p>
        <p>Blocks: {blocks.length}</p>
        <button type="button">Run</button>
      </section>
    </main>
  );
}

