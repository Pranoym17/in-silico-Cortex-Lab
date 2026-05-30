"use client";

import { useEffect, useState } from "react";
import { BrainScene } from "./BrainScene";
import { BrainMeshManifest, loadBrainManifest } from "@/lib/brainAssets";
import { getLatestActivationChunk } from "@/lib/brainActivation";
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
  const latestChunk = getLatestActivationChunk(chunks);

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
  }, [jobId, resetJob]);

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
            <BrainScene manifest={manifest} chunk={latestChunk} />
          ) : (
            <div className="brain-scene brain-loading">Loading brain mesh</div>
          )}
        </section>

        <aside className="panel stack viewer-sidebar">
          <div>
            <h2>Run</h2>
            <p>Job: {jobId}</p>
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
              <strong>{timestep}</strong>
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
