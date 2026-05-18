"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ApiError, Experiment, createExperiment, listExperiments } from "@/lib/api";
import { getSupabaseBrowserClient, isSupabaseConfigured } from "@/lib/supabase";
import { useAuthStore } from "@/store/authStore";

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
  const [tokenDraft, setTokenDraft] = useState("");
  const [emailDraft, setEmailDraft] = useState("");
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [name, setName] = useState("Untitled experiment");
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isSendingLink, setIsSendingLink] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const supabaseConfigured = isSupabaseConfigured();

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
  }, [accessToken]);

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

  async function handleSignOut() {
    const supabase = getSupabaseBrowserClient();
    if (supabase) {
      await supabase.auth.signOut();
    }
    setAccessToken(null);
  }

  return (
    <main className="shell">
      <div className="page-header">
        <div>
          <h1>Experiments</h1>
          <p>Checkpoint 1 dashboard for authenticated experiment metadata.</p>
        </div>
      </div>

      {!accessToken ? (
        <section className="panel stack">
          <h2>Connect a session</h2>
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
          <div className="toolbar">
            <div>
              <h2>Your experiments</h2>
              {email ? <p>{email}</p> : null}
            </div>
            <button type="button" onClick={handleSignOut}>
              Sign out
            </button>
          </div>

          <form className="create-form" onSubmit={handleCreate}>
            <input value={name} onChange={(event) => setName(event.target.value)} aria-label="Experiment name" />
            <button type="submit" disabled={isCreating || !name.trim()}>
              {isCreating ? "Creating..." : "Create"}
            </button>
          </form>

          {error ? <p className="error-text">{error}</p> : null}
          {isLoading ? <p>Loading experiments...</p> : null}

          {!isLoading && experiments.length === 0 ? (
            <p>No experiments yet. Create one to open the builder metadata view.</p>
          ) : null}

          <div className="experiment-list">
            {experiments.map((experiment) => (
              <article className="experiment-row" key={experiment.id}>
                <div>
                  <h3>{experiment.name}</h3>
                  <p>
                    {experiment.status} - Updated {formatUpdatedAt(experiment.updated_at)}
                  </p>
                </div>
                <Link href={`/builder/${experiment.id}`}>Open</Link>
              </article>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}

