"use client";

import { useViewerStore } from "@/store/viewerStore";

export function ResultsViewer({ experimentId }: { experimentId: string }) {
  const timestep = useViewerStore((state) => state.timestep);

  return (
    <main className="shell">
      <h1>Viewer</h1>
      <section className="panel">
        <p>Experiment: {experimentId}</p>
        <p>Current timestep: {timestep}</p>
      </section>
    </main>
  );
}

