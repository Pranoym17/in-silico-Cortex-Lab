"use client";

import Link from "next/link";
import { ReactNode, useState } from "react";
import { usePathname } from "next/navigation";
import { BrainCircuit, ChevronDown, CircleUserRound, FlaskConical, LibraryBig, LogOut, Menu, X } from "lucide-react";
import { getSupabaseBrowserClient } from "@/lib/supabase";
import { useAuthStore } from "@/store/authStore";

type AppShellProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  width?: "normal" | "wide" | "full";
};

const navigation = [
  { href: "/dashboard", label: "Experiments", icon: FlaskConical },
  { href: "/library", label: "Library", icon: LibraryBig }
];

export function AppShell({ title, description, actions, children, width = "wide" }: AppShellProps) {
  const pathname = usePathname();
  const accessToken = useAuthStore((state) => state.accessToken);
  const email = useAuthStore((state) => state.email);
  const setSession = useAuthStore((state) => state.setSession);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);

  async function handleSignOut() {
    const supabase = getSupabaseBrowserClient();
    if (supabase) {
      await supabase.auth.signOut();
    }
    setSession({ accessToken: null, email: null });
    setAccountOpen(false);
  }

  const isActive = (href: string) => pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`));

  return (
    <div className={`app-frame ${width === "full" ? "app-frame-workspace" : ""}`}>
      <aside className="app-rail" aria-label="Workspace navigation">
        <Link aria-label="Cortex Lab experiments" className="app-mark" href="/dashboard" title="Cortex Lab">
          <BrainCircuit aria-hidden="true" size={22} strokeWidth={1.7} />
        </Link>
        <nav className="app-rail-nav" aria-label="Primary navigation">
          {navigation.map(({ href, label, icon: Icon }) => (
            <Link
              aria-current={isActive(href) ? "page" : undefined}
              className={isActive(href) ? "app-rail-link active" : "app-rail-link"}
              href={href}
              key={href}
              title={label}
            >
              <Icon aria-hidden="true" size={18} strokeWidth={1.7} />
              <span>{label}</span>
            </Link>
          ))}
        </nav>
      </aside>

      <div className="app-canvas">
        <header className="app-topbar">
          <div className="app-heading">
            <button
              aria-controls="mobile-navigation"
              aria-expanded={mobileNavOpen}
              aria-label={mobileNavOpen ? "Close navigation" : "Open navigation"}
              className="icon-button mobile-nav-toggle"
              onClick={() => setMobileNavOpen((open) => !open)}
              type="button"
            >
              {mobileNavOpen ? <X aria-hidden="true" size={19} /> : <Menu aria-hidden="true" size={19} />}
            </button>
            <div>
              <span className="eyebrow">Cortex Lab</span>
              <h1>{title}</h1>
            </div>
          </div>
          <div className="app-topbar-actions">
            {actions ? <div className="page-actions">{actions}</div> : null}
            <div className="account-menu">
              <button
                aria-expanded={accountOpen}
                aria-haspopup="menu"
                aria-label="Account menu"
                className="account-trigger"
                onClick={() => setAccountOpen((open) => !open)}
                type="button"
              >
                <span className="account-avatar" aria-hidden="true"><CircleUserRound size={17} strokeWidth={1.6} /></span>
                <span className="account-copy">{accessToken ? email ?? "Research session" : "Guest session"}</span>
                <ChevronDown aria-hidden="true" size={15} />
              </button>
              {accountOpen ? (
                <div className="account-popover" role="menu">
                  <div className="account-popover-identity">
                    <CircleUserRound aria-hidden="true" size={20} />
                    <span>{accessToken ? email ?? "Research session" : "Not signed in"}</span>
                  </div>
                  {accessToken ? (
                    <button onClick={handleSignOut} role="menuitem" type="button">
                      <LogOut aria-hidden="true" size={15} />
                      Sign out
                    </button>
                  ) : (
                    <Link href="/dashboard" onClick={() => setAccountOpen(false)} role="menuitem">
                      Sign in
                    </Link>
                  )}
                </div>
              ) : null}
            </div>
          </div>
        </header>

        <nav className={mobileNavOpen ? "mobile-navigation open" : "mobile-navigation"} id="mobile-navigation" aria-label="Mobile navigation">
          {navigation.map(({ href, label, icon: Icon }) => (
            <Link href={href} key={href} onClick={() => setMobileNavOpen(false)}>
              <Icon aria-hidden="true" size={18} />
              {label}
            </Link>
          ))}
        </nav>

        <main className={`app-main app-main-${width}`}>
          {description ? <p className="page-description">{description}</p> : null}
          {children}
        </main>
      </div>
    </div>
  );
}

export function EmptyState({ title, message, action }: { title: string; message: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <BrainCircuit aria-hidden="true" size={26} strokeWidth={1.35} />
      <strong>{title}</strong>
      <p>{message}</p>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export function ErrorPanel({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-panel" role="alert">
      <div><strong>Something needs attention</strong><p>{message}</p></div>
      {onRetry ? <button type="button" onClick={onRetry}>Retry</button> : null}
    </div>
  );
}

export function LoadingRows({ rows = 3 }: { rows?: number }) {
  return <div className="loading-list" aria-label="Loading">{Array.from({ length: rows }, (_, index) => <div className="loading-row" key={index} />)}</div>;
}

export function StatusBadge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "warn" | "bad" }) {
  return <span className={`status-badge status-badge-${tone}`}><i aria-hidden="true" />{children}</span>;
}
