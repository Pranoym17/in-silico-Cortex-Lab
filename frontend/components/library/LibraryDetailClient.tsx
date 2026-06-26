"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LibraryDetail, PublicLibraryBlock, forkLibraryEntry, getLibraryEntry } from "@/lib/api";
import { AppShell, EmptyState, ErrorPanel, LoadingRows, StatusBadge } from "@/components/ui/AppShell";
import { useAuthStore } from "@/store/authStore";

function formatDuration(ms: number) {
  if (ms < 1000) {
    return `${ms}ms`;
  }
  return `${(ms / 1000).toFixed(ms % 1000 === 0 ? 0 : 1)}s`;
}

function summarizePayload(block: PublicLibraryBlock) {
  if (block.type === "text" && typeof block.payload.text === "string") {
    return block.payload.text;
  }
  if (typeof block.payload.filename === "string") {
    return block.payload.filename;
  }
  if (typeof block.payload.library_id === "string") {
    return block.payload.library_id;
  }
  if (typeof block.payload.source === "string") {
    return block.payload.source;
  }
  return "Configured stimulus";
}

export function LibraryDetailClient({ slug }: { slug: string }) {
  const router = useRouter();
  const accessToken = useAuthStore((state) => state.accessToken);
  const [detail, setDetail] = useState<LibraryDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isForking, setIsForking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let isActive = true;
    setIsLoading(true);
    setError(null);

    getLibraryEntry(slug)
      .then((response) => {
        if (isActive) {
          setDetail(response);
        }
      })
      .catch((caught: unknown) => {
        if (isActive) {
          setError(caught instanceof Error ? caught.message : "Failed to load library entry");
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
  }, [slug, reloadKey]);

  async function handleFork() {
    if (!accessToken) {
      router.push("/dashboard");
      return;
    }

    setIsForking(true);
    setError(null);

    try {
      const response = await forkLibraryEntry(slug, accessToken);
      router.push(`/builder/${response.experiment_id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to fork library entry");
      setIsForking(false);
    }
  }

  return (
    <AppShell
      title={detail?.entry.title ?? "Library entry"}
      description={detail?.entry.description ?? "Inspect a published experiment before forking it."}
      actions={
        <div className="library-detail-actions">
          <Link href="/library">Back to library</Link>
          <button type="button" disabled={isForking || isLoading || !detail} onClick={handleFork}>
            {isForking ? "Forking..." : accessToken ? "Fork" : "Sign in to fork"}
          </button>
        </div>
      }
    >
      <section className="panel stack">
        {error ? <ErrorPanel message={error} onRetry={() => setReloadKey((value) => value + 1)} /> : null}
        {isLoading ? <LoadingRows rows={4} /> : null}

        {!isLoading && !error && !detail ? (
          <EmptyState title="Entry unavailable" message="This published experiment could not be loaded." />
        ) : null}

        {detail ? (
          <>
            <div className="library-detail-summary">
              <div>
                <span>Experiment</span>
                <strong>{detail.experiment_name}</strong>
              </div>
              <div>
                <span>Blocks</span>
                <strong>{detail.blocks.length}</strong>
              </div>
              <div>
                <span>Forks</span>
                <strong>{detail.entry.run_count}</strong>
              </div>
              <div>
                <span>Tags</span>
                <strong>{detail.entry.tags.length > 0 ? detail.entry.tags.join(", ") : "None"}</strong>
              </div>
            </div>

            <div className="library-block-list">
              {detail.blocks.map((block) => (
                <article className="library-block-row" key={block.id}>
                  <div>
                    <h3>{block.condition || "Unlabeled condition"}</h3>
                    <p>{summarizePayload(block)}</p>
                  </div>
                  <StatusBadge tone="neutral">{block.type}</StatusBadge>
                  <span>
                    {formatDuration(block.start_ms)} - {formatDuration(block.start_ms + block.duration_ms)}
                  </span>
                </article>
              ))}
            </div>
          </>
        ) : null}
      </section>
    </AppShell>
  );
}
