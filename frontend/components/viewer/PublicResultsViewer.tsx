"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { Expand, Pause, Play, ScanEye, Waves } from "lucide-react";
import { BrainScene } from "./BrainScene";
import { getPublicLibraryResult, publicLibraryResultArtifactUrl, PublicResult } from "@/lib/api";
import { BrainMeshManifest, loadBrainManifest } from "@/lib/brainAssets";
import { getActivationDomain, getActivationStats } from "@/lib/brainActivation";
import { parseActivationNpz } from "@/lib/npz";
import { DecodedActivationChunk } from "@/lib/sse";
import { ErrorPanel, LoadingRows, StatusBadge } from "@/components/ui/AppShell";

function formatValue(value: number) {
  return Number.isFinite(value) ? value.toFixed(Math.abs(value) >= 10 ? 1 : 3) : "-";
}

export function PublicResultsViewer({ slug }: { slug: string }) {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const [manifest, setManifest] = useState<BrainMeshManifest | null>(null);
  const [result, setResult] = useState<PublicResult | null>(null);
  const [chunk, setChunk] = useState<DecodedActivationChunk | null>(null);
  const [timestep, setTimestep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [surface, setSurface] = useState<"pial" | "inflated">("pial");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([loadBrainManifest(), getPublicLibraryResult(slug)])
      .then(async ([loadedManifest, loadedResult]) => {
        const response = await fetch(publicLibraryResultArtifactUrl(slug));
        if (!response.ok) throw new Error("The public activation artifact could not be downloaded.");
        const matrix = parseActivationNpz(await response.arrayBuffer());
        if (matrix.shape[1] !== loadedManifest.vertex_count || matrix.shape[1] !== loadedResult.vertex_count) {
          throw new Error("The public activation artifact does not match the cortical surface.");
        }
        if (!active) return;
        setManifest(loadedManifest);
        setResult(loadedResult);
        setChunk({
          job_id: `public:${slug}`,
          block_id: "public-result",
          chunk_index: 0,
          timestep_start: 0,
          timestep_count: matrix.shape[0],
          sample_rate_hz: loadedResult.sample_rate_hz ?? 1,
          vertex_count: matrix.shape[1],
          dtype: "float32",
          shape: matrix.shape,
          activations: matrix.activations
        });
      })
      .catch((caught: unknown) => {
        if (active) setError(caught instanceof Error ? caught.message : "Failed to load the public activation result.");
      });
    return () => { active = false; };
  }, [slug]);

  useEffect(() => {
    if (!isPlaying || !chunk || chunk.timestep_count < 2) return;
    const interval = window.setInterval(() => setTimestep((current) => (current + 1) % chunk.timestep_count), 750);
    return () => window.clearInterval(interval);
  }, [chunk, isPlaying]);

  const domain = useMemo(() => getActivationDomain(chunk, timestep), [chunk, timestep]);
  const stats = useMemo(() => getActivationStats(chunk, timestep), [chunk, timestep]);

  function toggleFullscreen() {
    if (!canvasRef.current) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void canvasRef.current.requestFullscreen();
  }

  if (error) return <ErrorPanel message={error} />;
  if (!manifest || !result || !chunk) return <section className="public-viewer-loading"><LoadingRows rows={4} /></section>;

  return (
    <section className="public-viewer-shell" aria-label="Public cortical result viewer">
      <div className="public-viewer-toolbar">
        <div>
          <span className="section-kicker"><ScanEye aria-hidden="true" size={13} /> Read-only cortical surface</span>
          <strong>{result.vertex_count.toLocaleString()} vertices · {result.timestep_count} timepoints</strong>
        </div>
        <StatusBadge tone="good">Complete</StatusBadge>
      </div>
      <div className="public-viewer-canvas" ref={canvasRef}>
        <BrainScene chunk={chunk} colorDomain={domain} frameIndex={timestep} manifest={manifest} surface={surface} />
      </div>
      <div className="public-viewer-controls">
        <div className="public-viewer-playback">
          <button aria-label={isPlaying ? "Pause activation playback" : "Play activation playback"} className="icon-button" onClick={() => setIsPlaying((playing) => !playing)} title={isPlaying ? "Pause playback" : "Play playback"} type="button">
            {isPlaying ? <Pause aria-hidden="true" size={15} /> : <Play aria-hidden="true" size={15} />}
          </button>
          <input aria-label="Activation timestep" max={Math.max(0, chunk.timestep_count - 1)} min={0} onChange={(event) => { setIsPlaying(false); setTimestep(Number(event.target.value)); }} type="range" value={timestep} />
          <output>TR {timestep + 1} / {chunk.timestep_count}</output>
        </div>
        <div className="public-viewer-control-group">
          <label>Surface<select onChange={(event) => setSurface(event.target.value as "pial" | "inflated")} value={surface}><option value="pial">Pial</option><option value="inflated">Inflated</option></select></label>
          <button className="icon-button" onClick={toggleFullscreen} title="Fullscreen viewer" type="button"><Expand aria-hidden="true" size={15} /></button>
        </div>
      </div>
      <div className="public-viewer-readout">
        <span><Waves aria-hidden="true" size={13} /> mean {formatValue(stats.mean)}</span>
        <span>range {formatValue(domain[0])} to {formatValue(domain[1])}</span>
        <span>{result.sample_rate_hz ?? "-"} Hz</span>
        <Link href={`/library/${slug}`}>Fork this experiment</Link>
      </div>
    </section>
  );
}
