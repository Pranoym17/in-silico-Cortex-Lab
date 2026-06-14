"use client";

import { useEffect, useMemo, useState } from "react";
import { BrainPointerPosition, BrainScene } from "./BrainScene";
import { BrainMeshManifest, DesikanKillianyAtlas, loadBrainAtlas, loadBrainManifest } from "@/lib/brainAssets";
import {
  getJobResult,
  getJobResultDownload,
  ResultMetadata,
  ApiError
} from "@/lib/api";
import {
  ActivationDomain,
  getActivationDomain,
  getActivationStats,
  getChunkForTimestep,
  getFrameIndexForTimestep,
  getLatestActivationChunk,
  getStreamedTimestepCount,
  validateActivationChunkAgainstManifest
} from "@/lib/brainActivation";
import { BrainRegionInfo, getRegionForVertex } from "@/lib/brainRegions";
import { streamJobEvents } from "@/lib/sse";
import { getSupabaseBrowserClient } from "@/lib/supabase";
import { useAuthStore } from "@/store/authStore";
import { useViewerStore } from "@/store/viewerStore";
import { AppShell, ErrorPanel, StatusBadge } from "@/components/ui/AppShell";

type ConnectionStatus = "idle" | "connecting" | "connected" | "disconnected";

export function ResultsViewer({ jobId }: { jobId: string }) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const setSession = useAuthStore((state) => state.setSession);
  const status = useViewerStore((state) => state.status);
  const timestep = useViewerStore((state) => state.timestep);
  const completedBlocks = useViewerStore((state) => state.completedBlocks);
  const totalBlocks = useViewerStore((state) => state.totalBlocks);
  const chunks = useViewerStore((state) => state.chunks);
  const lastEventId = useViewerStore((state) => state.lastEventId);
  const resultS3Key = useViewerStore((state) => state.resultS3Key);
  const error = useViewerStore((state) => state.error);
  const resetJob = useViewerStore((state) => state.resetJob);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("idle");
  const [streamError, setStreamError] = useState<string | null>(null);
  const [connectAttempt, setConnectAttempt] = useState(0);
  const [manifest, setManifest] = useState<BrainMeshManifest | null>(null);
  const [atlas, setAtlas] = useState<DesikanKillianyAtlas | null>(null);
  const [assetError, setAssetError] = useState<string | null>(null);
  const [result, setResult] = useState<ResultMetadata | null>(null);
  const [resultError, setResultError] = useState<string | null>(null);
  const [isDownloadingResult, setIsDownloadingResult] = useState(false);
  const [selectedTimestep, setSelectedTimestep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const [showLeft, setShowLeft] = useState(true);
  const [showRight, setShowRight] = useState(true);
  const [useManualDomain, setUseManualDomain] = useState(false);
  const [manualMin, setManualMin] = useState("-1");
  const [manualMax, setManualMax] = useState("1");
  const [hoveredVertex, setHoveredVertex] = useState<number | null>(null);
  const [hoverPosition, setHoverPosition] = useState<BrainPointerPosition | null>(null);
  const [selectedVertex, setSelectedVertex] = useState<number | null>(null);
  const latestChunk = getLatestActivationChunk(chunks);
  const streamedTimesteps = getStreamedTimestepCount(chunks);
  const maxSelectableTimestep = Math.max(0, streamedTimesteps - 1);
  const selectedChunk = useMemo(
    () => getChunkForTimestep(chunks, selectedTimestep),
    [chunks, selectedTimestep]
  );
  const selectedFrameIndex = getFrameIndexForTimestep(selectedChunk, selectedTimestep);
  const manualDomain = parseManualDomain(manualMin, manualMax);
  const activeDomain = useMemo(
    () => getActivationDomain(selectedChunk ?? latestChunk, selectedFrameIndex, useManualDomain ? manualDomain : null),
    [latestChunk, manualDomain, selectedChunk, selectedFrameIndex, useManualDomain]
  );
  const selectedStats = useMemo(
    () => getActivationStats(selectedChunk ?? latestChunk, selectedFrameIndex),
    [latestChunk, selectedChunk, selectedFrameIndex]
  );
  const selectedValidation = useMemo(
    () => validateActivationChunkAgainstManifest(selectedChunk ?? latestChunk, manifest),
    [latestChunk, manifest, selectedChunk]
  );
  const renderableChunk = selectedValidation.valid ? selectedChunk ?? latestChunk : null;
  const selectedFrame = useMemo(
    () => (renderableChunk ? renderableChunk.activations.slice(
      selectedFrameIndex * renderableChunk.vertex_count,
      selectedFrameIndex * renderableChunk.vertex_count + renderableChunk.vertex_count
    ) : null),
    [renderableChunk, selectedFrameIndex]
  );
  const hoveredRegion = useMemo(
    () => getVertexRegionSnapshot(hoveredVertex, atlas, manifest, selectedFrame),
    [atlas, hoveredVertex, manifest, selectedFrame]
  );
  const selectedRegion = useMemo(
    () => getVertexRegionSnapshot(selectedVertex, atlas, manifest, selectedFrame),
    [atlas, manifest, selectedFrame, selectedVertex]
  );
  const manualDomainInvalid = useManualDomain && manualDomain === null;
  const shouldReconnect =
    Boolean(accessToken) && connectionStatus === "disconnected" && status !== "complete" && status !== "failed";
  const reconnectDelaySeconds = Math.min(30, 2 ** Math.min(connectAttempt, 5));

  useEffect(() => {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) {
      return;
    }

    supabase.auth.getSession().then(({ data }) => {
      setSession({
        accessToken: data.session?.access_token ?? null,
        email: data.session?.user.email ?? null
      });
    });

    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession({
        accessToken: session?.access_token ?? null,
        email: session?.user.email ?? null
      });
    });

    return () => {
      data.subscription.unsubscribe();
    };
  }, [setSession]);

  useEffect(() => {
    let cancelled = false;

    Promise.all([loadBrainManifest(), loadBrainAtlas()])
      .then(([loadedManifest, loadedAtlas]) => {
        if (!cancelled) {
          setManifest(loadedManifest);
          setAtlas(loadedAtlas);
          setAssetError(null);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setAssetError(caught instanceof Error ? caught.message : "Brain mesh assets failed to load");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    resetJob(jobId);
    setStreamError(null);
    setConnectionStatus("idle");
    setSelectedTimestep(0);
    setIsPlaying(true);
    setResult(null);
    setResultError(null);
    setHoveredVertex(null);
    setHoverPosition(null);
    setSelectedVertex(null);
  }, [jobId, resetJob]);

  useEffect(() => {
    if (!accessToken || status !== "complete") {
      return;
    }

    let cancelled = false;
    getJobResult(jobId, accessToken)
      .then((metadata) => {
        if (!cancelled) {
          setResult(metadata);
          setResultError(null);
        }
      })
      .catch((caught) => {
        if (cancelled) {
          return;
        }
        if (caught instanceof ApiError && caught.status === 404) {
          setResultError("Result metadata is not available yet.");
          return;
        }
        setResultError(caught instanceof Error ? caught.message : "Result metadata failed to load");
      });

    return () => {
      cancelled = true;
    };
  }, [accessToken, jobId, status]);

  useEffect(() => {
    if (isPlaying || selectedTimestep > maxSelectableTimestep) {
      setSelectedTimestep(maxSelectableTimestep);
    }
  }, [isPlaying, maxSelectableTimestep, selectedTimestep]);

  useEffect(() => {
    if (!shouldReconnect) {
      return;
    }

    const timeout = window.setTimeout(() => {
      setConnectAttempt((value) => value + 1);
    }, reconnectDelaySeconds * 1000);

    return () => window.clearTimeout(timeout);
  }, [reconnectDelaySeconds, shouldReconnect]);

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    const controller = new AbortController();
    const fromEventId = useViewerStore.getState().lastEventId;

    setConnectionStatus("connecting");
    setStreamError(null);

    streamJobEvents({
      jobId,
      token: accessToken,
      fromEventId,
      signal: controller.signal,
      onEvent: (event) => {
        useViewerStore.getState().handleStreamEvent(event);
        setConnectionStatus("connected");
      }
    })
      .then(() => {
        if (!controller.signal.aborted) {
          setConnectionStatus("disconnected");
        }
      })
      .catch((caught) => {
        if (controller.signal.aborted) {
          return;
        }
        setConnectionStatus("disconnected");
        setStreamError(caught instanceof Error ? caught.message : "Job stream disconnected");
      });

    return () => {
      controller.abort();
    };
  }, [accessToken, connectAttempt, jobId]);

  async function downloadResult() {
    if (!accessToken) {
      setResultError("Sign in again to download this result.");
      return;
    }

    setIsDownloadingResult(true);
    setResultError(null);
    try {
      const download = await getJobResultDownload(jobId, accessToken);
      window.location.assign(download.download_url);
    } catch (caught) {
      setResultError(caught instanceof Error ? caught.message : "Result download failed");
    } finally {
      setIsDownloadingResult(false);
    }
  }

  return (
    <AppShell
      title="Viewer"
      description="Inspect streamed cortical activation across the fsaverage5 surface."
      width="full"
      actions={
        <div className="viewer-header-actions">
          <StatusBadge tone={status === "complete" ? "good" : status === "failed" ? "bad" : status === "warming" ? "warn" : "neutral"}>
            {status}
          </StatusBadge>
          <StatusBadge tone={connectionStatus === "connected" ? "good" : connectionStatus === "disconnected" ? "warn" : "neutral"}>
            {connectionStatus}
          </StatusBadge>
        </div>
      }
    >
      <div className="viewer-grid">
        <section className="viewer-canvas-panel">
          {manifest ? (
            <BrainScene
              colorDomain={activeDomain}
              chunk={renderableChunk}
              frameIndex={selectedFrameIndex}
              manifest={manifest}
              onVertexClick={(vertexIndex) => setSelectedVertex(vertexIndex)}
              onVertexHover={(vertexIndex, position) => {
                setHoveredVertex(vertexIndex);
                setHoverPosition(position);
              }}
              showLeft={showLeft}
              showRight={showRight}
            />
          ) : (
            <div className="brain-scene brain-loading">Loading brain mesh</div>
          )}
          {hoveredRegion && hoverPosition ? (
            <div
              className="brain-hover-tooltip"
              style={{ left: hoverPosition.x + 14, top: hoverPosition.y + 14 }}
            >
              <strong>{hoveredRegion.label}</strong>
              <span>{formatHemisphere(hoveredRegion.hemisphere)}</span>
              <span>Vertex {hoveredRegion.vertexIndex}</span>
              <span>{formatActivationValue(hoveredRegion.activationValue)}</span>
            </div>
          ) : null}
          <div className="viewer-bottom-timeline">
            <div>
              <strong>Timestep</strong>
              <span>
                {selectedTimestep}/{maxSelectableTimestep}
              </span>
            </div>
            <input
              aria-label="Timestep scrubber"
              max={maxSelectableTimestep}
              min={0}
              onChange={(event) => {
                setIsPlaying(false);
                setSelectedTimestep(Number(event.target.value));
              }}
              type="range"
              value={selectedTimestep}
            />
            <div>
              <strong>Streamed</strong>
              <span>{timestep} frames</span>
            </div>
          </div>
        </section>

        <aside className="panel stack viewer-sidebar">
          <div>
            <h2>Run</h2>
            <p>Job: {jobId}</p>
          </div>
          <div className="viewer-controls">
            <div className="viewer-control-row">
              <button type="button" onClick={() => setIsPlaying((value) => !value)}>
                {isPlaying ? "Pause" : "Play"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsPlaying(true);
                  setSelectedTimestep(maxSelectableTimestep);
                }}
              >
                Live
              </button>
            </div>
            <div className="viewer-control-row">
              <label>
                <input
                  checked={showLeft}
                  onChange={(event) => setShowLeft(event.target.checked || !showRight)}
                  type="checkbox"
                />
                Left
              </label>
              <label>
                <input
                  checked={showRight}
                  onChange={(event) => setShowRight(event.target.checked || !showLeft)}
                  type="checkbox"
                />
                Right
              </label>
            </div>
            <label>
              <input
                checked={useManualDomain}
                onChange={(event) => setUseManualDomain(event.target.checked)}
                type="checkbox"
              />
              Manual color scale
            </label>
            <div className="viewer-domain-controls">
              <label>
                Min
                <input
                  disabled={!useManualDomain}
                  inputMode="decimal"
                  onChange={(event) => setManualMin(event.target.value)}
                  value={manualMin}
                />
              </label>
              <label>
                Max
                <input
                  disabled={!useManualDomain}
                  inputMode="decimal"
                  onChange={(event) => setManualMax(event.target.value)}
                  value={manualMax}
                />
              </label>
            </div>
            <div className="viewer-legend" aria-label={`Activation scale from ${activeDomain[0]} to ${activeDomain[1]}`}>
              <span>{formatDomainValue(activeDomain[0])}</span>
              <div />
              <span>{formatDomainValue(activeDomain[1])}</span>
            </div>
            {manualDomainInvalid ? <p className="error-text">Manual scale must have a numeric min below max.</p> : null}
          </div>
          <div className="viewer-section">
            <h3>Frame</h3>
            <div className="viewer-stat-grid">
              <div>
                <span>Min</span>
                <strong>{formatStatValue(selectedStats.min)}</strong>
              </div>
              <div>
                <span>Max</span>
                <strong>{formatStatValue(selectedStats.max)}</strong>
              </div>
              <div>
                <span>Mean</span>
                <strong>{formatStatValue(selectedStats.mean)}</strong>
              </div>
              <div>
                <span>Abs max</span>
                <strong>{formatStatValue(selectedStats.absoluteMax)}</strong>
              </div>
              <div>
                <span>Vertices</span>
                <strong>{selectedStats.vertexCount}</strong>
              </div>
              <div>
                <span>Sample Hz</span>
                <strong>{selectedChunk?.sample_rate_hz ?? latestChunk?.sample_rate_hz ?? "none"}</strong>
              </div>
            </div>
          </div>
          {!selectedValidation.valid ? <ErrorPanel message={selectedValidation.message ?? "Activation mesh validation failed."} /> : null}
          <div className="viewer-section">
            <div className="viewer-section-header">
              <h3>Selected Region</h3>
              <button disabled={!selectedRegion} onClick={() => setSelectedVertex(null)} type="button">
                Clear
              </button>
            </div>
            {selectedRegion ? (
              <div className="viewer-stat-grid">
                <div>
                  <span>Region</span>
                  <strong>{selectedRegion.label}</strong>
                </div>
                <div>
                  <span>Hemisphere</span>
                  <strong>{formatHemisphere(selectedRegion.hemisphere)}</strong>
                </div>
                <div>
                  <span>Vertex</span>
                  <strong>{selectedRegion.vertexIndex}</strong>
                </div>
                <div>
                  <span>Activation</span>
                  <strong>{formatActivationValue(selectedRegion.activationValue)}</strong>
                </div>
              </div>
            ) : (
              <p>Click a cortical region to pin it.</p>
            )}
          </div>
          <div className="viewer-section">
            <h3>Result</h3>
            <div className="viewer-stat-grid">
              <div>
                <span>Saved</span>
                <strong>{resultS3Key || result?.s3_key ? "yes" : "no"}</strong>
              </div>
              <div>
                <span>Format</span>
                <strong>{result?.format ?? "none"}</strong>
              </div>
              <div>
                <span>Shape</span>
                <strong>{result ? result.shape.join(" x ") : "none"}</strong>
              </div>
              <div>
                <span>Model</span>
                <strong>{result?.model_name ?? "none"}</strong>
              </div>
            </div>
            <button disabled={!result || isDownloadingResult} onClick={downloadResult} type="button">
              {isDownloadingResult ? "Preparing" : "Download NPZ"}
            </button>
          </div>
          <div className="viewer-stat-grid">
            <div>
              <span>Status</span>
              <strong>{status}</strong>
            </div>
            <div>
              <span>Connection</span>
              <strong>{connectionStatus}</strong>
            </div>
            <div>
              <span>Timestep</span>
              <strong>
                {selectedTimestep}/{maxSelectableTimestep}
              </strong>
            </div>
            <div>
              <span>Blocks</span>
              <strong>
                {completedBlocks}/{totalBlocks}
              </strong>
            </div>
            <div>
              <span>Chunks</span>
              <strong>{chunks.length}</strong>
            </div>
            <div>
              <span>Streamed</span>
              <strong>{timestep}</strong>
            </div>
            <div>
              <span>Last event</span>
              <strong>{lastEventId ?? "none"}</strong>
            </div>
            <div>
              <span>Chunk</span>
              <strong>{selectedChunk?.chunk_index ?? "none"}</strong>
            </div>
            <div>
              <span>Block</span>
              <strong>{selectedChunk?.block_id ?? "none"}</strong>
            </div>
          </div>
          {!accessToken ? <p>Open the dashboard and sign in to stream this job.</p> : null}
          {status === "failed" && chunks.length > 0 ? (
            <div className="partial-result-banner">
              Partial result is still available. The stream failed after receiving {chunks.length} chunk
              {chunks.length === 1 ? "" : "s"}.
            </div>
          ) : null}
          {assetError ? <ErrorPanel message={assetError} /> : null}
          {error ? <ErrorPanel message={error} /> : null}
          {streamError ? <ErrorPanel message={streamError} /> : null}
          {resultError ? <ErrorPanel message={resultError} /> : null}
          {shouldReconnect ? <p>Reconnecting in {reconnectDelaySeconds}s.</p> : null}
          {accessToken && connectionStatus === "disconnected" && status !== "complete" && status !== "failed" ? (
            <button type="button" onClick={() => setConnectAttempt((value) => value + 1)}>
              Reconnect
            </button>
          ) : null}
        </aside>
      </div>
    </AppShell>
  );
}

function parseManualDomain(minValue: string, maxValue: string): ActivationDomain | null {
  const min = Number(minValue);
  const max = Number(maxValue);
  return Number.isFinite(min) && Number.isFinite(max) && min < max ? [min, max] : null;
}

function formatDomainValue(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

function formatStatValue(value: number) {
  if (!Number.isFinite(value)) {
    return "0";
  }
  if (Math.abs(value) >= 100) {
    return value.toFixed(1);
  }
  return value.toFixed(3);
}

type VertexRegionSnapshot = BrainRegionInfo & {
  activationValue: number | null;
};

function getVertexRegionSnapshot(
  vertexIndex: number | null,
  atlas: DesikanKillianyAtlas | null,
  manifest: BrainMeshManifest | null,
  frame: Float32Array | null
): VertexRegionSnapshot | null {
  if (vertexIndex === null || !atlas || !manifest) {
    return null;
  }

  const region = getRegionForVertex(atlas, manifest, vertexIndex);
  if (!region) {
    return null;
  }

  return {
    ...region,
    activationValue: frame?.[vertexIndex] ?? null
  };
}

function formatHemisphere(hemisphere: string) {
  return hemisphere === "left" ? "Left hemisphere" : "Right hemisphere";
}

function formatActivationValue(value: number | null) {
  if (value === null || !Number.isFinite(value)) {
    return "Activation none";
  }
  return `Activation ${formatStatValue(value)}`;
}
