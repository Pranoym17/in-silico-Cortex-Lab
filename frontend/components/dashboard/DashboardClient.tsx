"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ApiError, Experiment, createExperiment, listExperiments } from "@/lib/api";
import { getSupabaseBrowserClient, isSupabaseConfigured } from "@/lib/supabase";
import { useAuthStore } from "@/store/authStore";
import { AppShell, EmptyState, ErrorPanel, LoadingRows, StatusBadge } from "@/components/ui/AppShell";

function formatUpdatedAt(value: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(new Date(value));
}

export function DashboardClient() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const email = useAuthStore((state) => state.email);
  const setAccessToken = useAuthStore((state) => state.setAccessToken);
  const setSession = useAuthStore((state) => state.setSession);
  const supabaseConfigured = isSupabaseConfigured();
  const [tokenDraft, setTokenDraft] = useState("");
  const [emailDraft, setEmailDraft] = useState("");
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [name, setName] = useState("Untitled experiment");
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isRestoringSession, setIsRestoringSession] = useState(supabaseConfigured);
  const [isCreating, setIsCreating] = useState(false);
  const [isSendingLink, setIsSendingLink] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) {
      setIsRestoringSession(false);
      return;
    }

    supabase.auth
      .getSession()
      .then(({ data }) => {
        setSession({
          accessToken: data.session?.access_token ?? null,
          email: data.session?.user.email ?? null
        });
      })
      .finally(() => setIsRestoringSession(false));

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
    if (!accessToken) {
      setExperiments([]);
      return;
    }

    let isActive = true;
    setIsLoading(true);
    setError(null);

    listExperiments(accessToken)
      .then((items) => {
        if (isActive) {
          setExperiments(items);
        }
      })
      .catch((caught: unknown) => {
        if (isActive) {
          setError(caught instanceof Error ? caught.message : "Failed to load experiments");
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
  }, [accessToken, reloadKey]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!accessToken || !name.trim()) {
      return;
    }

    setIsCreating(true);
    setError(null);

    try {
      const experiment = await createExperiment({ name: name.trim() }, accessToken);
      setExperiments((current) => [experiment, ...current]);
      setName("Untitled experiment");
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Failed to create experiment";
      setError(message);
    } finally {
      setIsCreating(false);
    }
  }

  async function handleMagicLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const supabase = getSupabaseBrowserClient();
    if (!supabase || !emailDraft.trim()) {
      return;
    }

    setIsSendingLink(true);
    setError(null);
    setNotice(null);

    const { error: signInError } = await supabase.auth.signInWithOtp({
      email: emailDraft.trim(),
      options: {
        emailRedirectTo: window.location.origin + "/dashboard"
      }
    });

    if (signInError) {
      setError(signInError.message);
    } else {
      setNotice("Check your email for a sign-in link.");
    }

    setIsSendingLink(false);
  }

  async function handleGoogleSignIn() {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) {
      return;
    }

    const { error: signInError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: window.location.origin + "/dashboard"
      }
    });

    if (signInError) {
      setError(signInError.message);
    }
  }

  const filteredExperiments = experiments
    .filter((experiment) => experiment.name.toLowerCase().includes(search.trim().toLowerCase()))
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());

  return (
    <AppShell
      title="Experiments"
      description="Create experiments, open drafts, and continue into the builder."
      actions={
        accessToken ? (
          <form className="compact-create-form" onSubmit={handleCreate}>
            <input value={name} onChange={(event) => setName(event.target.value)} aria-label="Experiment name" />
            <button type="submit" disabled={isCreating || !name.trim()}>
              {isCreating ? "Creating..." : "Create"}
            </button>
          </form>
        ) : null
      }
    >
      {isRestoringSession ? (
        <section className="panel stack">
          <h2>Restoring session</h2>
          <LoadingRows rows={2} />
        </section>
      ) : !accessToken ? (
        <section className="panel auth-panel">
          <div className="auth-copy">
            <h2>Sign in</h2>
            <p>Use your Supabase session to load saved experiments and create new timelines.</p>
          </div>
          {supabaseConfigured ? (
            <>
              <form className="token-form" onSubmit={handleMagicLink}>
                <input
                  aria-label="Email"
                  value={emailDraft}
                  onChange={(event) => setEmailDraft(event.target.value)}
                  placeholder="you@example.com"
                  type="email"
                />
                <button type="submit" disabled={isSendingLink || !emailDraft.trim()}>
                  {isSendingLink ? "Sending..." : "Email link"}
                </button>
              </form>
              <button type="button" onClick={handleGoogleSignIn}>
                Continue with Google
              </button>
            </>
          ) : (
            <>
              <p>Supabase env vars are not set yet. Paste a development JWT to exercise the API contract.</p>
              <form
                className="token-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  setAccessToken(tokenDraft.trim() || null);
                }}
              >
                <input
                  aria-label="Access token"
                  value={tokenDraft}
                  onChange={(event) => setTokenDraft(event.target.value)}
                  placeholder="Bearer token value"
                />
                <button type="submit">Use token</button>
              </form>
            </>
          )}
          {notice ? <p>{notice}</p> : null}
          {error ? <p className="error-text">{error}</p> : null}
        </section>
      ) : (
        <section className="panel stack">
          <div className="toolbar dashboard-toolbar">
            <div>
              <h2>Experiment library</h2>
              <p>{email ? `Signed in as ${email}` : "Authenticated session"}</p>
            </div>
            <input
              aria-label="Search experiments"
              className="search-input"
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search experiments"
              value={search}
            />
          </div>

          {error ? <ErrorPanel message={error} onRetry={() => setReloadKey((value) => value + 1)} /> : null}
          {isLoading ? <LoadingRows rows={4} /> : null}

          {!isLoading && experiments.length === 0 ? (
            <EmptyState
              title="No experiments yet"
              message="Create a draft experiment to start building a stimulus timeline."
            />
          ) : null}

          {!isLoading && experiments.length > 0 && filteredExperiments.length === 0 ? (
            <EmptyState title="No matching experiments" message="Clear the search field to see every experiment." />
          ) : null}

          <div className="experiment-list">
            {filteredExperiments.map((experiment) => (
              <article className="experiment-row" key={experiment.id}>
                <div>
                  <h3>{experiment.name}</h3>
                  <p>
                    Updated {formatUpdatedAt(experiment.updated_at)}
                  </p>
                </div>
                <StatusBadge tone={experiment.status === "ready" ? "good" : "neutral"}>{experiment.status}</StatusBadge>
                <Link href={`/builder/${experiment.id}`}>Open</Link>
              </article>
            ))}
          </div>
        </section>
      )}
    </AppShell>
  );
}
