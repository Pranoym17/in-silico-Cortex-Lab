"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { getSupabaseBrowserClient } from "@/lib/supabase";
import { useAuthStore } from "@/store/authStore";

type AppShellProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  width?: "normal" | "wide" | "full";
};

export function AppShell({ title, description, actions, children, width = "wide" }: AppShellProps) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const email = useAuthStore((state) => state.email);
  const setSession = useAuthStore((state) => state.setSession);

  async function handleSignOut() {
    const supabase = getSupabaseBrowserClient();
    if (supabase) {
      await supabase.auth.signOut();
    }
    setSession({ accessToken: null, email: null });
  }

  return (
    <div className="app-frame">
      <header className="app-topbar">
        <Link className="app-brand" href="/dashboard">
          Cortex Lab
        </Link>
        <nav className="app-nav" aria-label="Primary navigation">
          <Link href="/dashboard">Experiments</Link>
        </nav>
        <div className="app-account">
          {accessToken ? (
            <>
              <span title={email ?? "Authenticated session"}>{email ?? "Session connected"}</span>
              <button type="button" onClick={handleSignOut}>
                Sign out
              </button>
            </>
          ) : (
            <Link href="/dashboard">Sign in</Link>
          )}
        </div>
      </header>

      <main className={`app-main app-main-${width}`}>
        <div className="page-header">
          <div>
            <h1>{title}</h1>
            {description ? <p>{description}</p> : null}
          </div>
          {actions ? <div className="page-actions">{actions}</div> : null}
        </div>
        {children}
      </main>
    </div>
  );
}

export function EmptyState({
  title,
  message,
  action
}: {
  title: string;
  message: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{message}</p>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export function ErrorPanel({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-panel" role="alert">
      <strong>Something needs attention</strong>
      <p>{message}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function LoadingRows({ rows = 3 }: { rows?: number }) {
  return (
    <div className="loading-list" aria-label="Loading">
      {Array.from({ length: rows }, (_, index) => (
        <div className="loading-row" key={index} />
      ))}
    </div>
  );
}

export function StatusBadge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "warn" | "bad" }) {
  return <span className={`status-badge status-badge-${tone}`}>{children}</span>;
}
