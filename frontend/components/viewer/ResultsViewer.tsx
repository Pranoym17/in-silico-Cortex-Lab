"use client";

import { useEffect, useMemo, useState } from "react";
import { BrainPointerPosition, BrainScene } from "./BrainScene";
import {
  BrainMeshManifest,
  DesikanKillianyAtlas,
  loadBrainAtlas,
  loadBrainManifest,
  validateAtlasForManifest
} from "@/lib/brainAssets";
import {
  getJobResult,
  getJobResultDownload,
  ResultMetadata,
  ApiError,
  cancelJob,
  getJob,
  Job
} from "@/lib/api";
import {
  ActivationDomain,
  getActivationFrame,
  getActivationDomain,
  getActivationStats,
  getChunkForTimestep,
  getFrameIndexForTimestep,
  getLatestActivationChunk,
  getStreamedTimestepCount,
  validateActivationChunkAgainstManifest
} from "@/lib/brainActivation";
import {
  BrainRegionInfo,
  BrainRegionTimecoursePoint,
  compareTopConditions,
  getRegionActivationStats,
  getRegionConditionSummaries,
  getRegionForVertex,
  getRegionMetadata,
  getRegionPeak,
  getRegionTimecourse
} from "@/lib/brainRegions";
import { streamJobEvents } from "@/lib/sse";
import { getSupabaseBrowserClient } from "@/lib/supabase";
import { getJobErrorCopy } from "@/lib/jobErrors";
import { useAuthStore } from "@/store/authStore";
import { useViewerStore } from "@/store/viewerStore";
import { AppShell, ErrorPanel, StatusBadge } from "@/components/ui/AppShell";

type ConnectionStatus = "idle" | "connecting" | "connected" | "disconnected";
const MAX_SELECTED_REGIONS = 4;
const REGION_COLORS = ["#8fb8ff", "#ff9f7c", "#93d8a3", "#d7a3ff"];

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
  const errorCode = useViewerStore((state) => state.errorCode);
  const errorRetryable = useViewerStore((state) => state.errorRetryable);
  const errorLastTimestep = useViewerStore((state) => state.errorLastTimestep);
  const resetJob = useViewerStore((state) => state.resetJob);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("idle");
  const [streamError, setStreamError] = useState<string | null>(null);
  const [connectAttempt, setConnectAttempt] = useState(0);
  const [manifest, setManifest] = useState<BrainMeshManifest | null>(null);
  const [atlas, setAtlas] = useState<DesikanKillianyAtlas | null>(null);
  const [assetError, setAssetError] = useState<string | null>(null);
  const [result, setResult] = useState<ResultMetadata | null>(null);
  const [jobMetadata, setJobMetadata] = useState<Job | null>(null);
  const [resultError, setResultError] = useState<string | null>(null);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);
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
  const [selectedRegionLabels, setSelectedRegionLabels] = useState<string[]>([]);
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
  const atlasValidation = useMemo(() => validateAtlasForManifest(atlas, manifest), [atlas, manifest]);
  const regionAtlas = atlasValidation.valid ? atlas : null;
  const regionModeEnabled = Boolean(regionAtlas && manifest);
  const showAtlasUnavailable = Boolean(manifest) && !regionModeEnabled;
  const selectedValidation = useMemo(
    () => validateActivationChunkAgainstManifest(selectedChunk ?? latestChunk, manifest),
    [latestChunk, manifest, selectedChunk]
  );
  const renderableChunk = selectedValidation.valid ? selectedChunk ?? latestChunk : null;
  const selectedFrame = useMemo(
    () => (renderableChunk ? getActivationFrame(renderableChunk, selectedFrameIndex) : null),
    [renderableChunk, selectedFrameIndex]
  );
  const hoveredRegion = useMemo(
    () => getVertexRegionSnapshot(hoveredVertex, regionAtlas, manifest, selectedFrame),
    [hoveredVertex, manifest, regionAtlas, selectedFrame]
  );
  const selectedRegion = useMemo(
    () => getVertexRegionSnapshot(selectedVertex, regionAtlas, manifest, selectedFrame),
    [manifest, regionAtlas, selectedFrame, selectedVertex]
  );
  const primaryRegionLabel = selectedRegion?.label ?? selectedRegionLabels[0] ?? null;
  const primaryRegionStats = useMemo(
    () =>
      primaryRegionLabel && regionAtlas && manifest
        ? getRegionActivationStats(primaryRegionLabel, regionAtlas, manifest, selectedChunk ?? latestChunk, selectedFrameIndex)
        : null,
    [latestChunk, manifest, primaryRegionLabel, regionAtlas, selectedChunk, selectedFrameIndex]
  );
  const primaryRegionTimecourse = useMemo(
    () => (primaryRegionLabel && regionAtlas && manifest ? getRegionTimecourse(primaryRegionLabel, regionAtlas, manifest, chunks) : []),
    [chunks, manifest, primaryRegionLabel, regionAtlas]
  );
  const primaryRegionPeak = useMemo(() => getRegionPeak(primaryRegionTimecourse), [primaryRegionTimecourse]);
  const primaryRegionMetadata = useMemo(
    () => (primaryRegionLabel ? getRegionMetadata(primaryRegionLabel) : null),
    [primaryRegionLabel]
  );
  const selectedRegionTimecourses = useMemo(
    () =>
      regionAtlas && manifest
        ? selectedRegionLabels.map((label, index) => ({
            label,
            color: REGION_COLORS[index % REGION_COLORS.length],
            points: getRegionTimecourse(label, regionAtlas, manifest, chunks)
          }))
        : [],
    [chunks, manifest, regionAtlas, selectedRegionLabels]
  );
  const blockConditionLabels = useMemo(() => getBlockConditionLabels(jobMetadata), [jobMetadata]);
  const conditionSummaries = useMemo(
    () =>
      primaryRegionLabel && regionAtlas && manifest
        ? getRegionConditionSummaries(primaryRegionLabel, regionAtlas, manifest, chunks, blockConditionLabels)
        : [],
    [blockConditionLabels, chunks, manifest, primaryRegionLabel, regionAtlas]
  );
  const conditionComparison = useMemo(() => compareTopConditions(conditionSummaries), [conditionSummaries]);
  const jobErrorCopy = useMemo(() => getJobErrorCopy(errorCode, error, errorRetryable), [error, errorCode, errorRetryable]);
  const resultSaveFailed = errorCode === "result_storage_failed";
  const manualDomainInvalid = useManualDomain && manualDomain === null;
  const shouldReconnect =
    Boolean(accessToken) && connectionStatus === "disconnected" && !isTerminalViewerStatus(status);
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

    loadBrainManifest()
      .then((loadedManifest) => {
        if (!cancelled) {
          setManifest(loadedManifest);
          setAssetError(null);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setAssetError(caught instanceof Error ? caught.message : "Brain mesh assets failed to load");
        }
      });

    loadBrainAtlas()
      .then((loadedAtlas) => {
        if (!cancelled) {
          setAtlas(loadedAtlas);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAtlas(null);
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
    setJobMetadata(null);
    setResultError(null);
    setCancelError(null);
    setIsCancelling(false);
    setHoveredVertex(null);
    setHoverPosition(null);
    setSelectedVertex(null);
    setSelectedRegionLabels([]);
  }, [jobId, resetJob]);

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    let cancelled = false;
    getJob(jobId, accessToken)
      .then((metadata) => {
        if (!cancelled) {
          setJobMetadata(metadata);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setJobMetadata(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [accessToken, jobId]);

  useEffect(() => {
    if (regionModeEnabled) {
      return;
    }
    setHoveredVertex(null);
    setHoverPosition(null);
    setSelectedVertex(null);
    setSelectedRegionLabels([]);
  }, [regionModeEnabled]);

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

  async function cancelRunningJob() {
    if (!accessToken) {
      setCancelError("Sign in again to cancel this job.");
      return;
    }

    setIsCancelling(true);
    setCancelError(null);
    try {
      await cancelJob(jobId, accessToken);
    } catch (caught) {
      setCancelError(caught instanceof Error ? caught.message : "Job cancellation failed");
    } finally {
      setIsCancelling(false);
    }
  }

  function selectVertex(vertexIndex: number) {
    if (!regionModeEnabled) {
      return;
    }
    setSelectedVertex(vertexIndex);
    if (!regionAtlas || !manifest) {
      return;
    }

    const region = getRegionForVertex(regionAtlas, manifest, vertexIndex);
    if (!region) {
      return;
    }

    setSelectedRegionLabels((labels) => {
      const withoutDuplicate = labels.filter((label) => label !== region.label);
      return [region.label, ...withoutDuplicate].slice(0, MAX_SELECTED_REGIONS);
    });
  }

  function removeSelectedRegion(label: string) {
    setSelectedRegionLabels((labels) => labels.filter((current) => current !== label));
    if (selectedRegion?.label === label) {
      setSelectedVertex(null);
    }
  }

  function retryViewerStream() {
    setStreamError(null);
    setConnectAttempt((value) => value + 1);
    setConnectionStatus("disconnected");
  }

  return (
    <AppShell
      title="Viewer"
      description="Inspect streamed cortical activation across the fsaverage5 surface."
      width="full"
      actions={
        <div className="viewer-header-actions">
          <StatusBadge tone={status === "complete" ? "good" : status === "failed" ? "bad" : status === "cancelled" || status === "warming" ? "warn" : "neutral"}>
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
              onVertexClick={selectVertex}
              onVertexHover={(vertexIndex, position) => {
                if (!regionModeEnabled) {
                  setHoveredVertex(null);
                  setHoverPosition(null);
                  return;
                }
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
              <button
                disabled={isCancelling || isTerminalViewerStatus(status)}
                onClick={cancelRunningJob}
                type="button"
              >
                {isCancelling ? "Cancelling" : "Cancel"}
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
          {showAtlasUnavailable ? (
            <ErrorPanel message={atlasValidation.message ?? "Atlas unavailable. Region hover, selection, charts, and condition comparison are disabled."} />
          ) : null}
          <div className="viewer-section">
            <div className="viewer-section-header">
              <h3>Region</h3>
              <button
                disabled={!regionModeEnabled || selectedRegionLabels.length === 0}
                onClick={() => {
                  setSelectedRegionLabels([]);
                  setSelectedVertex(null);
                }}
                type="button"
              >
                Clear all
              </button>
            </div>
            {showAtlasUnavailable ? (
              <p>Atlas unavailable. Activation rendering remains available, but region interaction is disabled.</p>
            ) : selectedRegionLabels.length > 0 ? (
              <div className="region-chip-row">
                {selectedRegionLabels.map((label, index) => (
                  <button
                    className={label === primaryRegionLabel ? "region-chip active" : "region-chip"}
                    key={label}
                    onClick={() => setSelectedRegionLabels((labels) => [label, ...labels.filter((item) => item !== label)])}
                    style={{ borderColor: REGION_COLORS[index % REGION_COLORS.length] }}
                    type="button"
                  >
                    <span>{label}</span>
                    <span aria-label={`Remove ${label}`} onClick={(event) => {
                      event.stopPropagation();
                      removeSelectedRegion(label);
                    }}>
                      x
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <p>Click a cortical region to pin it. Up to {MAX_SELECTED_REGIONS} regions can be compared.</p>
            )}
            {primaryRegionLabel && primaryRegionStats && primaryRegionMetadata ? (
              <>
                <div className="viewer-stat-grid">
                  <div>
                    <span>Region</span>
                    <strong>{primaryRegionLabel}</strong>
                  </div>
                  <div>
                    <span>Hemisphere</span>
                    <strong>{formatHemisphere(primaryRegionStats.hemisphere)}</strong>
                  </div>
                  <div>
                    <span>Current</span>
                    <strong>{selectedRegion ? formatActivationValue(selectedRegion.activationValue) : formatStatValue(primaryRegionStats.mean)}</strong>
                  </div>
                  <div>
                    <span>Mean</span>
                    <strong>{formatStatValue(primaryRegionStats.mean)}</strong>
                  </div>
                  <div>
                    <span>Min / Max</span>
                    <strong>
                      {formatStatValue(primaryRegionStats.min)} / {formatStatValue(primaryRegionStats.max)}
                    </strong>
                  </div>
                  <div>
                    <span>Peak timestep</span>
                    <strong>
                      {primaryRegionPeak.timestep === null
                        ? "none"
                        : `${primaryRegionPeak.timestep} (${formatStatValue(primaryRegionPeak.value)})`}
                    </strong>
                  </div>
                  <div>
                    <span>Vertices</span>
                    <strong>{primaryRegionStats.vertexCount}</strong>
                  </div>
                  <div>
                    <span>Atlas</span>
                    <strong>Desikan-Killiany</strong>
                  </div>
                </div>
                <div className="region-metadata">
                  <strong>Known function</strong>
                  <p>{primaryRegionMetadata.knownFunction}</p>
                  <strong>Atlas description</strong>
                  <p>{primaryRegionMetadata.atlasDescription}</p>
                  <strong>Notes</strong>
                  <p>{primaryRegionMetadata.notes}</p>
                </div>
              </>
            ) : null}
          </div>
          <div className="viewer-section">
            <h3>Timecourse</h3>
            {showAtlasUnavailable ? (
              <p>Atlas unavailable. Region timecourses are disabled.</p>
            ) : selectedRegionTimecourses.length > 0 ? (
              <>
                <RegionTimecourseChart
                  currentTimestep={selectedTimestep}
                  series={selectedRegionTimecourses}
                />
                <div className="region-chart-legend">
                  {selectedRegionTimecourses.map((series) => (
                    <span key={series.label}>
                      <i style={{ background: series.color }} />
                      {series.label}
                    </span>
                  ))}
                </div>
              </>
            ) : (
              <p>Select a region to plot its mean activation over time.</p>
            )}
          </div>
          <div className="viewer-section">
            <h3>Condition Comparison</h3>
            {showAtlasUnavailable ? (
              <p>Atlas unavailable. Condition comparison by region is disabled.</p>
            ) : conditionSummaries.length > 0 ? (
              <>
                <div className="viewer-stat-grid">
                  {conditionSummaries.slice(0, 4).map((summary) => (
                    <div key={summary.blockId}>
                      <span>{summary.condition}</span>
                      <strong>{formatStatValue(summary.mean)}</strong>
                      <span>peak {formatStatValue(summary.peak)}</span>
                    </div>
                  ))}
                </div>
                {conditionComparison ? (
                  <div className="viewer-stat-grid">
                    <div>
                      <span>Mean difference</span>
                      <strong>{formatStatValue(conditionComparison.meanDifference)}</strong>
                    </div>
                    <div>
                      <span>Peak difference</span>
                      <strong>{formatStatValue(conditionComparison.peakDifference)}</strong>
                    </div>
                    <div>
                      <span>Dominant</span>
                      <strong>{conditionComparison.dominantCondition}</strong>
                    </div>
                    <div>
                      <span>Compared</span>
                      <strong>
                        {conditionComparison.conditionA} vs {conditionComparison.conditionB}
                      </strong>
                    </div>
                  </div>
                ) : (
                  <p>Run at least two blocks to compare conditions.</p>
                )}
              </>
            ) : (
              <p>Select a region after streamed data arrives to aggregate block responses.</p>
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
            {resultSaveFailed ? (
              <div className="partial-result-banner">
                Streamed frames are still visible, but saving the NPZ artifact failed. Rerun the job to create a downloadable result.
              </div>
            ) : null}
            <button disabled={!result || isDownloadingResult || resultSaveFailed} onClick={downloadResult} type="button">
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
              {chunks.length === 1 ? "" : "s"}
              {errorLastTimestep !== null ? ` through timestep ${errorLastTimestep}` : ""}.
            </div>
          ) : null}
          {assetError ? <ErrorPanel message={assetError} /> : null}
          {error ? <ErrorPanel message={jobErrorCopy.message} onRetry={jobErrorCopy.retryLabel ? retryViewerStream : undefined} /> : null}
          {streamError ? <ErrorPanel message={streamError} onRetry={retryViewerStream} /> : null}
          {resultError ? <ErrorPanel message={resultError} /> : null}
          {cancelError ? <ErrorPanel message={cancelError} /> : null}
          {shouldReconnect ? <p>Reconnecting in {reconnectDelaySeconds}s.</p> : null}
          {accessToken && connectionStatus === "disconnected" && !isTerminalViewerStatus(status) ? (
            <button type="button" onClick={() => setConnectAttempt((value) => value + 1)}>
              Reconnect
            </button>
          ) : null}
        </aside>
      </div>
    </AppShell>
  );
}

function RegionTimecourseChart({
  currentTimestep,
  series
}: {
  currentTimestep: number;
  series: readonly { label: string; color: string; points: readonly BrainRegionTimecoursePoint[] }[];
}) {
  const allPoints = series.flatMap((item) => item.points);
  if (allPoints.length === 0) {
    return <div className="region-chart empty">Waiting for region timecourse data.</div>;
  }

  const minTimestep = Math.min(...allPoints.map((point) => point.timestep));
  const maxTimestep = Math.max(...allPoints.map((point) => point.timestep));
  const minValue = Math.min(...allPoints.map((point) => point.mean), 0);
  const maxValue = Math.max(...allPoints.map((point) => point.mean), 0);
  const valuePadding = Math.max(0.05, (maxValue - minValue) * 0.08);
  const yMin = minValue - valuePadding;
  const yMax = maxValue + valuePadding;
  const x = (timestep: number) => scaleValue(timestep, minTimestep, maxTimestep, 24, 376);
  const y = (value: number) => scaleValue(value, yMin, yMax, 136, 16);
  const markerX = x(currentTimestep);

  return (
    <svg className="region-chart" role="img" viewBox="0 0 400 152">
      <line className="region-chart-axis" x1="24" x2="376" y1={y(0)} y2={y(0)} />
      <line className="region-chart-marker" x1={markerX} x2={markerX} y1="12" y2="140" />
      {series.map((item) => (
        <polyline
          fill="none"
          key={item.label}
          points={item.points.map((point) => `${x(point.timestep)},${y(point.mean)}`).join(" ")}
          stroke={item.color}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2.5"
        />
      ))}
      <text x="24" y="148">
        {minTimestep}
      </text>
      <text textAnchor="end" x="376" y="148">
        {maxTimestep}
      </text>
      <text x="28" y="14">
        {formatStatValue(yMax)}
      </text>
      <text x="28" y="134">
        {formatStatValue(yMin)}
      </text>
    </svg>
  );
}

function parseManualDomain(minValue: string, maxValue: string): ActivationDomain | null {
  const min = Number(minValue);
  const max = Number(maxValue);
  return Number.isFinite(min) && Number.isFinite(max) && min < max ? [min, max] : null;
}

function isTerminalViewerStatus(status: string) {
  return status === "complete" || status === "failed" || status === "cancelled";
}

function getBlockConditionLabels(job: Job | null): Map<string, string> {
  const labels = new Map<string, string>();
  const blocks = job?.run_spec.blocks;
  if (!Array.isArray(blocks)) {
    return labels;
  }

  for (const block of blocks) {
    if (!block || typeof block !== "object") {
      continue;
    }
    const id = "id" in block && typeof block.id === "string" ? block.id : null;
    if (!id) {
      continue;
    }
    const condition = "condition" in block && typeof block.condition === "string" && block.condition.trim()
      ? block.condition.trim()
      : null;
    labels.set(id, condition ?? `Block ${id.slice(0, 8)}`);
  }

  return labels;
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

function scaleValue(value: number, inputMin: number, inputMax: number, outputMin: number, outputMax: number) {
  if (inputMin === inputMax) {
    return (outputMin + outputMax) / 2;
  }
  return outputMin + ((value - inputMin) / (inputMax - inputMin)) * (outputMax - outputMin);
}

function formatHemisphere(hemisphere: string) {
  if (hemisphere === "left") {
    return "Left hemisphere";
  }
  if (hemisphere === "right") {
    return "Right hemisphere";
  }
  return "Bilateral";
}

function formatActivationValue(value: number | null) {
  if (value === null || !Number.isFinite(value)) {
    return "Activation none";
  }
  return `Activation ${formatStatValue(value)}`;
}
