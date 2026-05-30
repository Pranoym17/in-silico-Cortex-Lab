"use client";

import { useEffect, useMemo, useState } from "react";
import { BrainScene } from "./BrainScene";
import { BrainMeshManifest, loadBrainManifest } from "@/lib/brainAssets";
import {
  getChunkForTimestep,
  getFrameIndexForTimestep,
  getLatestActivationChunk,
  getStreamedTimestepCount
} from "@/lib/brainActivation";
import { streamJobEvents } from "@/lib/sse";
import { getSupabaseBrowserClient } from "@/lib/supabase";
import { useAuthStore } from "@/store/authStore";
import { useViewerStore } from "@/store/viewerStore";

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
  const error = useViewerStore((state) => state.error);
  const resetJob = useViewerStore((state) => state.resetJob);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("idle");
  const [streamError, setStreamError] = useState<string | null>(null);
  const [connectAttempt, setConnectAttempt] = useState(0);
  const [manifest, setManifest] = useState<BrainMeshManifest | null>(null);
  const [assetError, setAssetError] = useState<string | null>(null);
  const [selectedTimestep, setSelectedTimestep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const [showLeft, setShowLeft] = useState(true);
  const [showRight, setShowRight] = useState(true);
  const latestChunk = getLatestActivationChunk(chunks);
  const streamedTimesteps = getStreamedTimestepCount(chunks);
  const maxSelectableTimestep = Math.max(0, streamedTimesteps - 1);
  const selectedChunk = useMemo(
    () => getChunkForTimestep(chunks, selectedTimestep),
    [chunks, selectedTimestep]
  );
  const selectedFrameIndex = getFrameIndexForTimestep(selectedChunk, selectedTimestep);

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
  }, [jobId, resetJob]);

  useEffect(() => {
    if (isPlaying || selectedTimestep > maxSelectableTimestep) {
      setSelectedTimestep(maxSelectableTimestep);
    }
  }, [isPlaying, maxSelectableTimestep, selectedTimestep]);

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

  return (
    <main className="shell">
      <div className="page-header">
        <div>
          <h1>Viewer</h1>
          <p>Streamed cortical activation preview.</p>
        </div>
      </div>

      <div className="viewer-grid">
        <section className="viewer-canvas-panel">
          {manifest ? (
            <BrainScene
              chunk={selectedChunk ?? latestChunk}
              frameIndex={selectedFrameIndex}
              manifest={manifest}
              showLeft={showLeft}
              showRight={showRight}
            />
          ) : (
            <div className="brain-scene brain-loading">Loading brain mesh</div>
          )}
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
              <button type="button" onClick={() => setSelectedTimestep(maxSelectableTimestep)}>
                Live
              </button>
            </div>
            <label>
              Timestep
              <input
                max={maxSelectableTimestep}
                min={0}
                onChange={(event) => {
                  setIsPlaying(false);
                  setSelectedTimestep(Number(event.target.value));
                }}
                type="range"
                value={selectedTimestep}
              />
            </label>
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
          </div>
          {!accessToken ? <p>Open the dashboard and sign in to stream this job.</p> : null}
          {assetError ? <p className="error-text">{assetError}</p> : null}
          {error ? <p className="error-text">{error}</p> : null}
          {streamError ? <p className="error-text">{streamError}</p> : null}
          {accessToken && connectionStatus === "disconnected" && status !== "complete" ? (
            <button type="button" onClick={() => setConnectAttempt((value) => value + 1)}>
              Reconnect
            </button>
          ) : null}
        </aside>
      </div>
    </main>
  );
}
