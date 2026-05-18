"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ApiError, Experiment, createExperiment, listExperiments } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";

function formatUpdatedAt(value: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(new Date(value));
}

export function DashboardClient() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const setAccessToken = useAuthStore((state) => state.setAccessToken);
  const [tokenDraft, setTokenDraft] = useState("");
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [name, setName] = useState("Untitled experiment");
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) {
      setExperiments([]);
      return;
    }

    let isActive = true;
    setIsLoading(true);
    setError(null);

    listExperiments(accessToken)
      .then((items) => {
        if (isActive) {
          setExperiments(items);
        }
      })
      .catch((caught: unknown) => {
        if (isActive) {
          setError(caught instanceof Error ? caught.message : "Failed to load experiments");
        }
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [accessToken]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!accessToken || !name.trim()) {
      return;
    }

    setIsCreating(true);
    setError(null);

    try {
      const experiment = await createExperiment({ name: name.trim() }, accessToken);
      setExperiments((current) => [experiment, ...current]);
      setName("Untitled experiment");
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Failed to create experiment";
      setError(message);
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <main className="shell">
      <div className="page-header">
        <div>
          <h1>Experiments</h1>
          <p>Checkpoint 1 dashboard for authenticated experiment metadata.</p>
        </div>
      </div>

      {!accessToken ? (
        <section className="panel stack">
          <h2>Connect a session</h2>
          <p>Paste a Supabase JWT when your project exists. For now, backend tests cover the same token contract.</p>
          <form
            className="token-form"
            onSubmit={(event) => {
              event.preventDefault();
              setAccessToken(tokenDraft.trim() || null);
            }}
          >
            <input
              aria-label="Access token"
              value={tokenDraft}
              onChange={(event) => setTokenDraft(event.target.value)}
              placeholder="Bearer token value"
            />
            <button type="submit">Use token</button>
          </form>
        </section>
      ) : (
        <section className="panel stack">
          <div className="toolbar">
            <h2>Your experiments</h2>
            <button type="button" onClick={() => setAccessToken(null)}>
              Clear token
            </button>
          </div>

          <form className="create-form" onSubmit={handleCreate}>
            <input value={name} onChange={(event) => setName(event.target.value)} aria-label="Experiment name" />
            <button type="submit" disabled={isCreating || !name.trim()}>
              {isCreating ? "Creating..." : "Create"}
            </button>
          </form>

          {error ? <p className="error-text">{error}</p> : null}
          {isLoading ? <p>Loading experiments...</p> : null}

          {!isLoading && experiments.length === 0 ? (
            <p>No experiments yet. Create one to open the builder metadata view.</p>
          ) : null}

          <div className="experiment-list">
            {experiments.map((experiment) => (
              <article className="experiment-row" key={experiment.id}>
                <div>
                  <h3>{experiment.name}</h3>
                  <p>
                    {experiment.status} · Updated {formatUpdatedAt(experiment.updated_at)}
                  </p>
                </div>
                <Link href={`/builder/${experiment.id}`}>Open</Link>
              </article>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}

