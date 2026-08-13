"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ArrowRight, Bookmark, Filter, FlaskConical, LibraryBig, Sparkles } from "lucide-react";
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
      description="Inspect public paradigms, their reproducibility record, and fork a private working copy."
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
          <button title="Apply library filters" type="submit"><Filter aria-hidden="true" size={14} /> <span>Filter</span></button>
        </form>
      }
    >
      <section className="panel stack library-index-panel">
        <div className="toolbar library-index-toolbar">
          <div>
            <span className="section-kicker"><LibraryBig aria-hidden="true" size={13} /> Public research record</span>
            <h2>Published paradigms</h2>
            <p>{isLoading ? "Loading entries" : `${entries.length} entr${entries.length === 1 ? "y" : "ies"} available to inspect`}</p>
          </div>
          <StatusBadge tone="neutral">{params.sort ?? "featured"}</StatusBadge>
        </div>

        {error ? <ErrorPanel message={error} onRetry={() => setReloadKey((value) => value + 1)} /> : null}
        {isLoading ? <LoadingRows rows={4} /> : null}

        {!isLoading && !error && entries.length === 0 ? (
          <EmptyState
            title="No published experiments yet"
            message="Start with a research template, then publish a validated result when it is ready to share."
            action={<Link className="empty-state-action" href="/dashboard">Build an experiment <ArrowRight aria-hidden="true" size={14} /></Link>}
          />
        ) : null}

        <div className="library-grid">
          {entries.map((entry) => (
            <article className="library-card" key={entry.id}>
              <div className="library-card-main">
                <div className="library-card-header">
                  <span className="library-card-glyph">{entry.featured ? <Sparkles aria-hidden="true" size={16} /> : <FlaskConical aria-hidden="true" size={16} />}</span>
                  {entry.featured ? <StatusBadge tone="good">Featured</StatusBadge> : <StatusBadge tone="neutral">Public</StatusBadge>}
                </div>
                <h3>{entry.title}</h3>
                <p>{entry.description || "No description provided."}</p>
              </div>
              <div className="library-card-meta">
                <span><Bookmark aria-hidden="true" size={12} /> {entryTags(entry)}</span>
                <span>{entry.run_count} fork{entry.run_count === 1 ? "" : "s"}</span>
                <span>Published {formatPublishedAt(entry.published_at)}</span>
              </div>
              <Link href={`/library/${entry.slug}`}>Inspect record <ArrowRight aria-hidden="true" size={14} /></Link>
            </article>
          ))}
        </div>
      </section>
    </AppShell>
  );
}
