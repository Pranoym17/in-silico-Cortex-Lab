"use client";

import { useEffect, useState } from "react";
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
      <h1>Viewer</h1>
      <section className="panel stack">
        <p>Job: {jobId}</p>
        <p>Status: {status}</p>
        <p>Connection: {connectionStatus}</p>
        <p>Current timestep: {timestep}</p>
        <p>
          Blocks: {completedBlocks}/{totalBlocks}
        </p>
        <p>Chunks received: {chunks.length}</p>
        {lastEventId ? <p>Last event: {lastEventId}</p> : null}
        {!accessToken ? <p>Open the dashboard and sign in to stream this job.</p> : null}
        {error ? <p className="error-text">{error}</p> : null}
        {streamError ? <p className="error-text">{streamError}</p> : null}
        {accessToken && connectionStatus === "disconnected" && status !== "complete" ? (
          <button type="button" onClick={() => setConnectAttempt((value) => value + 1)}>
            Reconnect
          </button>
        ) : null}
      </section>
    </main>
  );
}
