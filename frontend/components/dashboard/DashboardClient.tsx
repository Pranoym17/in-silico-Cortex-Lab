"use client";

import Link from "next/link";
import NextImage from "next/image";
import { FormEvent, useEffect, useState } from "react";
import { Activity, ArrowRight, BookOpen, CircleCheck, FlaskConical, LockKeyhole, Plus, Sparkles } from "lucide-react";
import { ApiError, Experiment, createExperiment, listExperiments } from "@/lib/api";
import { getSupabaseBrowserClient, isSupabaseConfigured } from "@/lib/supabase";
import { useAuthStore } from "@/store/authStore";
import { AppShell, EmptyState, ErrorPanel, LoadingRows, StatusBadge } from "@/components/ui/AppShell";
import { PearlButton } from "@/components/ui/PearlButton";

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
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [name, setName] = useState("Untitled experiment");
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isRestoringSession, setIsRestoringSession] = useState(supabaseConfigured);
  const [isCreating, setIsCreating] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [error, setError] = useState<string | null>(null);

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
      setExperiments((current) => [experiment, ...current.filter((item) => item.id !== experiment.id)]);
      setName("Untitled experiment");
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Failed to create experiment";
      setError(message);
    } finally {
      setIsCreating(false);
    }
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
      title={accessToken ? "Experiments" : "Cortex Lab"}
      description={accessToken ? "Build precisely timed stimuli, validate a run, and read the cortical response." : "Sign in to access your private research workspace."}
      actions={
        accessToken ? (
          <form className="compact-create-form" onSubmit={handleCreate}>
            <input value={name} onChange={(event) => setName(event.target.value)} aria-label="Experiment name" />
            <button aria-label="New experiment" title="Create experiment" type="submit" disabled={isCreating || !name.trim()}>
              <Plus aria-hidden="true" size={15} />
              <span>{isCreating ? "Creating..." : "New experiment"}</span>
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
            <section className="panel auth-panel auth-workbench">
              <div className="auth-copy">
                <span className="auth-brand-mark" aria-hidden="true">
                  <NextImage alt="" className="auth-brand-logo" height={64} src="/brand/cortex-lab-logo.png" width={86} />
                </span>
            <span className="section-kicker"><LockKeyhole aria-hidden="true" size={13} /> Cortex Lab workspace</span>
            <h2>Sign in to your account</h2>
            <p>Access your private experiments, queued runs, and saved stimulus timelines.</p>
          </div>
          {supabaseConfigured ? (
            <div className="auth-actions auth-google-only">
              <PearlButton className="google-sign-in" type="button" onClick={handleGoogleSignIn}>
                <span aria-hidden="true" className="auth-google-mark" />
                Continue with Google
              </PearlButton>
              <p className="auth-legal">Google securely verifies your account before returning you to Cortex Lab.</p>
            </div>
          ) : (
            <div className="auth-actions">
              <p className="auth-access-copy">Use your research access token to open a private workspace session.</p>
              <form
                className="token-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  setAccessToken(tokenDraft.trim() || null);
                }}
              >
                <label className="auth-field">
                  <span>Research access token</span>
                  <input
                    aria-label="Research access token"
                    value={tokenDraft}
                    onChange={(event) => setTokenDraft(event.target.value)}
                    placeholder="Enter access token"
                  />
                </label>
                <PearlButton icon={<ArrowRight size={16} strokeWidth={1.8} />} type="submit">Continue</PearlButton>
              </form>
            </div>
          )}
          {error ? <p className="error-text">{error}</p> : null}
        </section>
      ) : (
        <>
          <section className="dashboard-instrument-strip" aria-label="Workspace overview">
            <div>
              <span>Private workspace</span>
              <strong>{experiments.length}</strong>
              <small>experiment{experiments.length === 1 ? "" : "s"}</small>
            </div>
            <div>
              <span>Ready to run</span>
              <strong>{experiments.filter((experiment) => experiment.status === "ready").length}</strong>
              <small>validated timeline{experiments.filter((experiment) => experiment.status === "ready").length === 1 ? "" : "s"}</small>
            </div>
            <div>
              <span>Research mode</span>
              <strong><CircleCheck aria-hidden="true" size={17} /> Online</strong>
              <small>session verified</small>
            </div>
          </section>

          <section className="panel stack dashboard-records">
            <div className="toolbar dashboard-toolbar">
              <div>
                <span className="section-kicker"><FlaskConical aria-hidden="true" size={13} /> Experiment records</span>
                <h2>Continue analysis</h2>
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
                message="Create a private draft, or begin from a published paradigm in the library."
                action={<Link className="empty-state-action" href="/library">Browse research templates <ArrowRight aria-hidden="true" size={14} /></Link>}
              />
            ) : null}

            {!isLoading && experiments.length > 0 && filteredExperiments.length === 0 ? (
              <EmptyState title="No matching experiments" message="Clear the search field to see every experiment." />
            ) : null}

            <div className="experiment-list">
              {filteredExperiments.map((experiment) => (
                <article className="experiment-row" key={experiment.id}>
                  <div className="experiment-row-title">
                    <span className="experiment-type-mark"><Activity aria-hidden="true" size={15} /></span>
                    <div>
                      <h3>{experiment.name}</h3>
                      <p>Updated {formatUpdatedAt(experiment.updated_at)}</p>
                    </div>
                  </div>
                  <div className="experiment-row-actions">
                    <span className={experiment.is_public ? "visibility-mark public" : "visibility-mark"}>{experiment.is_public ? "Public" : "Private"}</span>
                    <StatusBadge tone={experiment.status === "ready" ? "good" : "neutral"}>{experiment.status}</StatusBadge>
                    <Link href={`/builder/${experiment.id}`}>Open <ArrowRight aria-hidden="true" size={14} /></Link>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="dashboard-reference-row" aria-label="Research starting points">
            <div className="reference-intro">
              <span className="section-kicker"><BookOpen aria-hidden="true" size={13} /> Starting points</span>
              <h2>Use a validated paradigm as your first instrument.</h2>
              <Link href="/library">Open library <ArrowRight aria-hidden="true" size={14} /></Link>
            </div>
            <div className="reference-list">
              <span><Sparkles aria-hidden="true" size={15} /> FFA faces versus houses</span>
              <span><Activity aria-hidden="true" size={15} /> Speech versus music</span>
              <span><FlaskConical aria-hidden="true" size={15} /> Semantic N400</span>
            </div>
          </section>
        </>
      )}
    </AppShell>
  );
}
