"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ArrowDownToLine, ArrowLeft, Braces, Check, Clipboard, Flag, FlaskConical, GitFork, Info, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import {
  LibraryDetail,
  PublicEmbed,
  PublicExperimentReport,
  PublicLibraryBlock,
  flagLibraryEntry,
  forkLibraryEntry,
  getLibraryEntry,
  getPublicLibraryEmbed,
  getPublicLibraryReport
} from "@/lib/api";
import { AppShell, EmptyState, ErrorPanel, LoadingRows, StatusBadge } from "@/components/ui/AppShell";
import { PublicResultsViewer } from "@/components/viewer/PublicResultsViewer";
import { useAuthStore } from "@/store/authStore";

function formatDuration(ms: number) {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(ms % 1000 === 0 ? 0 : 1)} s`;
}

function summarizePayload(block: PublicLibraryBlock) {
  if (block.type === "text" && typeof block.payload.text === "string") return block.payload.text;
  if (typeof block.payload.title === "string") return block.payload.title;
  if (typeof block.payload.transcript === "string") return block.payload.transcript;
  if (typeof block.payload.alt === "string") return block.payload.alt;
  return "Configured stimulus";
}

function blockTypeLabel(type: string) {
  return type === "audio" ? "Audio" : type === "image" ? "Image" : type === "video" ? "Video" : "Text";
}

function downloadReport(report: PublicExperimentReport) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `cortexlab-${report.slug}-report.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function LibraryDetailClient({ slug }: { slug: string }) {
  const router = useRouter();
  const accessToken = useAuthStore((state) => state.accessToken);
  const [detail, setDetail] = useState<LibraryDetail | null>(null);
  const [report, setReport] = useState<PublicExperimentReport | null>(null);
  const [embed, setEmbed] = useState<PublicEmbed | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isForking, setIsForking] = useState(false);
  const [isFlagging, setIsFlagging] = useState(false);
  const [flagReason, setFlagReason] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let isActive = true;
    setIsLoading(true);
    setError(null);

    Promise.all([getLibraryEntry(slug), getPublicLibraryReport(slug), getPublicLibraryEmbed(slug)])
      .then(([entry, loadedReport, loadedEmbed]) => {
        if (!isActive) return;
        setDetail(entry);
        setReport(loadedReport);
        setEmbed(loadedEmbed);
      })
      .catch((caught: unknown) => {
        if (isActive) setError(caught instanceof Error ? caught.message : "Failed to load library entry");
      })
      .finally(() => {
        if (isActive) setIsLoading(false);
      });

    return () => { isActive = false; };
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

  async function handleCopyEmbed() {
    if (!embed) return;
    const source = `${window.location.origin}${embed.iframe_path}`;
    const code = `<iframe src="${source}" title="${embed.title}" width="100%" height="640" loading="lazy"></iframe>`;
    try {
      await navigator.clipboard.writeText(code);
      setNotice("Embed code copied to your clipboard.");
    } catch {
      setNotice("Your browser blocked clipboard access. Copy the embed URL from this page after deployment.");
    }
  }

  async function handleFlag(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!accessToken || flagReason.trim().length < 3) return;
    setIsFlagging(true);
    setError(null);
    try {
      await flagLibraryEntry(slug, flagReason.trim(), accessToken);
      setFlagReason("");
      setNotice("Report submitted for review.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to submit report");
    } finally {
      setIsFlagging(false);
    }
  }

  return (
    <AppShell
      title={detail?.entry.title ?? "Research record"}
      description={detail?.entry.description ?? "Inspect a published experiment before creating a private fork."}
      actions={
        <div className="library-detail-actions">
          <Link href="/library"><ArrowLeft aria-hidden="true" size={14} /> <span>Library</span></Link>
          <button type="button" disabled={isForking || isLoading || !detail} onClick={handleFork}>
            <GitFork aria-hidden="true" size={15} />
            <span className="library-fork-desktop">{isForking ? "Forking..." : accessToken ? "Fork privately" : "Sign in to fork"}</span>
            <span className="library-fork-mobile">{isForking ? "Working..." : "Fork"}</span>
          </button>
        </div>
      }
    >
      {error ? <ErrorPanel message={error} onRetry={() => setReloadKey((value) => value + 1)} /> : null}
      {notice ? <p className="library-notice" role="status"><Check aria-hidden="true" size={15} /> {notice}</p> : null}
      {isLoading ? <section className="panel stack"><LoadingRows rows={5} /></section> : null}
      {!isLoading && !error && !detail ? <EmptyState title="Record unavailable" message="This published experiment could not be loaded." /> : null}

      {detail ? (
        <div className="public-record-layout">
          <section className="panel public-record-main">
            <div className="public-record-origin">
              <span className="author-mark"><UserRound aria-hidden="true" size={16} /></span>
              <div>
                <span>Published by</span>
                <strong>{detail.author.display_name}</strong>
              </div>
              <StatusBadge tone="good">Public</StatusBadge>
            </div>

            <div className="library-detail-summary">
              <div><span>Stimulus blocks</span><strong>{detail.blocks.length}</strong></div>
              <div><span>Private forks</span><strong>{detail.entry.run_count}</strong></div>
              <div><span>Tags</span><strong>{detail.entry.tags.length || "-"}</strong></div>
              <div><span>Result</span><strong>{report?.result ? "Available" : "Pending"}</strong></div>
            </div>

            <div className="public-record-section-heading">
              <div><span className="section-kicker"><FlaskConical aria-hidden="true" size={13} /> Stimulus timeline</span><h2>{detail.experiment_name}</h2></div>
              <span>{detail.entry.tags.length ? detail.entry.tags.join(" / ") : "Untyped paradigm"}</span>
            </div>
            <div className="library-block-list public-block-list">
              {detail.blocks.map((block) => (
                <article className="library-block-row" key={block.id}>
                  <span className={`public-block-type type-${block.type}`}>{blockTypeLabel(block.type)}</span>
                  <div>
                    <h3>{block.condition || "Unlabeled condition"}</h3>
                    <p>{summarizePayload(block)}</p>
                  </div>
                  <span className="block-timing">{formatDuration(block.start_ms)} <i aria-hidden="true" /> {formatDuration(block.start_ms + block.duration_ms)}</span>
                </article>
              ))}
            </div>
            {report?.result ? <PublicResultsViewer slug={slug} /> : null}
          </section>

          <aside className="public-record-sidebar">
            <section className="panel public-provenance-panel">
              <span className="section-kicker"><Braces aria-hidden="true" size={13} /> Reproducibility</span>
              <h2>Result contract</h2>
              {report?.result ? (
                <dl>
                  <div><dt>Surface</dt><dd>{String(report.result.metadata.vertex_space ?? "fsaverage5")}</dd></div>
                  <div><dt>Vertices</dt><dd>{report.result.vertex_count.toLocaleString()}</dd></div>
                  <div><dt>Timepoints</dt><dd>{report.result.timestep_count}</dd></div>
                  <div><dt>Model</dt><dd>{report.result.model_version ?? report.result.model_name}</dd></div>
                </dl>
              ) : <p>No completed public result has been attached yet.</p>}
              <div className="public-record-actions">
                {report ? <button type="button" onClick={() => downloadReport(report)}><ArrowDownToLine aria-hidden="true" size={14} /> Report JSON</button> : null}
                {embed ? <button type="button" onClick={handleCopyEmbed}><Clipboard aria-hidden="true" size={14} /> Embed</button> : null}
              </div>
            </section>

            <section className="panel public-limitations-panel">
              <span className="section-kicker"><Info aria-hidden="true" size={13} /> Interpretation</span>
              <h2>Scientific limitations</h2>
              <ul>{(report?.limitations ?? ["Predictions represent simulated average-subject responses, not measured fMRI data."]).map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
            </section>

            <details className="reporting-panel">
              <summary><Flag aria-hidden="true" size={14} /> Report this record</summary>
              {accessToken ? (
                <form onSubmit={handleFlag}>
                  <label htmlFor="report-reason">What needs review?</label>
                  <textarea id="report-reason" minLength={3} onChange={(event) => setFlagReason(event.target.value)} placeholder="Describe the issue concisely" required rows={3} value={flagReason} />
                  <button disabled={isFlagging || flagReason.trim().length < 3} type="submit">{isFlagging ? "Sending..." : "Submit report"}</button>
                </form>
              ) : <p>Sign in to submit a moderation report.</p>}
            </details>
          </aside>
        </div>
      ) : null}
    </AppShell>
  );
}
