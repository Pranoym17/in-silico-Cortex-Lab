"use client";

import { useEffect, useState } from "react";
import { Experiment, getExperiment } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import { useExperimentStore } from "@/store/experimentStore";

export function ExperimentBuilder({ experimentId }: { experimentId: string }) {
  const blocks = useExperimentStore((state) => state.blocks);
  const accessToken = useAuthStore((state) => state.accessToken);
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) {
      setExperiment(null);
      return;
    }

    let isActive = true;
    setError(null);

    getExperiment(experimentId, accessToken)
      .then((item) => {
        if (isActive) {
          setExperiment(item);
        }
      })
      .catch((caught: unknown) => {
        if (isActive) {
          setError(caught instanceof Error ? caught.message : "Failed to load experiment");
        }
      });

    return () => {
      isActive = false;
    };
  }, [accessToken, experimentId]);

  return (
    <main className="shell">
      <h1>{experiment?.name ?? "Builder"}</h1>
      <section className="panel stack">
        <p>Experiment: {experimentId}</p>
        {experiment ? <p>Status: {experiment.status}</p> : null}
        {!accessToken ? <p>Return to the dashboard and connect a session token to load saved metadata.</p> : null}
        {error ? <p className="error-text">{error}</p> : null}
        <p>Blocks: {blocks.length}</p>
        <button type="button">Run</button>
      </section>
    </main>
  );
}
