"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { LibraryEntry, LibraryListParams, listLibraryEntries } from "@/lib/api";
import { AppShell, EmptyState, ErrorPanel, LoadingRows, StatusBadge } from "@/components/ui/AppShell";

function formatPublishedAt(value: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric"
  }).format(new Date(value));
}

function entryTags(entry: LibraryEntry) {
  return entry.tags.length > 0 ? entry.tags.join(", ") : "No tags";
}

export function LibraryClient() {
  const [entries, setEntries] = useState<LibraryEntry[]>([]);
  const [searchDraft, setSearchDraft] = useState("");
  const [tagDraft, setTagDraft] = useState("");
  const [params, setParams] = useState<LibraryListParams>({ sort: "featured" });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let isActive = true;
    setIsLoading(true);
    setError(null);

    listLibraryEntries(params)
      .then((response) => {
        if (isActive) {
          setEntries(response.items);
        }
      })
      .catch((caught: unknown) => {
        if (isActive) {
          setError(caught instanceof Error ? caught.message : "Failed to load the public library");
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
  }, [params, reloadKey]);

  function handleFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setParams((current) => ({
      ...current,
      search: searchDraft.trim() || undefined,
      tag: tagDraft.trim().toLowerCase() || undefined
    }));
  }

  return (
    <AppShell
      title="Library"
      description="Browse published experiments and fork useful paradigms into your workspace."
      actions={
        <form className="library-filter-form" onSubmit={handleFilter}>
          <input
            aria-label="Search library"
            onChange={(event) => setSearchDraft(event.target.value)}
            placeholder="Search library"
            value={searchDraft}
          />
          <input
            aria-label="Filter by tag"
            onChange={(event) => setTagDraft(event.target.value)}
            placeholder="Tag"
            value={tagDraft}
          />
          <select
            aria-label="Sort library"
            onChange={(event) => setParams((current) => ({ ...current, sort: event.target.value as LibraryListParams["sort"] }))}
            value={params.sort ?? "featured"}
          >
            <option value="featured">Featured</option>
            <option value="newest">Newest</option>
            <option value="run_count">Most forked</option>
          </select>
          <button type="submit">Filter</button>
        </form>
      }
    >
      <section className="panel stack">
        <div className="toolbar">
          <div>
            <h2>Published paradigms</h2>
            <p>{isLoading ? "Loading entries" : `${entries.length} entr${entries.length === 1 ? "y" : "ies"}`}</p>
          </div>
          <StatusBadge tone="neutral">{params.sort ?? "featured"}</StatusBadge>
        </div>

        {error ? <ErrorPanel message={error} onRetry={() => setReloadKey((value) => value + 1)} /> : null}
        {isLoading ? <LoadingRows rows={4} /> : null}

        {!isLoading && !error && entries.length === 0 ? (
          <EmptyState title="No published experiments yet" message="Published experiments will appear here once the library has entries." />
        ) : null}

        <div className="library-grid">
          {entries.map((entry) => (
            <article className="library-card" key={entry.id}>
              <div className="library-card-main">
                <div className="library-card-header">
                  <h3>{entry.title}</h3>
                  {entry.featured ? <StatusBadge tone="good">Featured</StatusBadge> : null}
                </div>
                <p>{entry.description || "No description provided."}</p>
              </div>
              <div className="library-card-meta">
                <span>{entryTags(entry)}</span>
                <span>{entry.run_count} forks</span>
                <span>{formatPublishedAt(entry.published_at)}</span>
              </div>
              <Link href={`/library/${entry.slug}`}>Open</Link>
            </article>
          ))}
        </div>
      </section>
    </AppShell>
  );
}
