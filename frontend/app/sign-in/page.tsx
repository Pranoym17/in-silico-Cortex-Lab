"use client";

import Link from "next/link";
import NextImage from "next/image";
import { FormEvent, Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowRight, Building2, CheckCircle2, Mail } from "lucide-react";
import { HeroBrain } from "@/components/landing/HeroBrain";
import { getSupabaseBrowserClient, isSupabaseConfigured } from "@/lib/supabase";

function safeNextPath(value: string | null) {
  return value?.startsWith("/") && !value.startsWith("//") ? value : "/dashboard";
}

function SignInContent() {
  const searchParams = useSearchParams();
  const nextPath = useMemo(() => safeNextPath(searchParams.get("next")), [searchParams]);
  const [email, setEmail] = useState("");
  const [showEmail, setShowEmail] = useState(false);
  const [showInstitutional, setShowInstitutional] = useState(false);
  const [isConnecting, setIsConnecting] = useState<"google" | "email" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [emailSent, setEmailSent] = useState(false);

  const configured = isSupabaseConfigured();

  async function continueWithGoogle() {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) {
      setError("Sign-in is not configured for this environment.");
      return;
    }
    setError(null);
    setIsConnecting("google");
    const { error: signInError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}${nextPath}` }
    });
    if (signInError) {
      setError(signInError.message);
      setIsConnecting(null);
    }
  }

  async function sendMagicLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const supabase = getSupabaseBrowserClient();
    if (!supabase || !email.trim()) return;
    setError(null);
    setIsConnecting("email");
    const { error: signInError } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { emailRedirectTo: `${window.location.origin}${nextPath}` }
    });
    setIsConnecting(null);
    if (signInError) {
      setError(signInError.message);
      return;
    }
    setEmailSent(true);
  }

  return (
    <main className="sign-in-page">
      <section className="sign-in-card" aria-labelledby="sign-in-title">
        <Link className="sign-in-brand" href="/">
          <NextImage alt="Cortex Lab" height={52} src="/brand/cortex-lab-logo.png" width={92} />
          <span>Cortex Lab</span>
        </Link>
        {emailSent ? (
          <div className="sign-in-confirmation" role="status">
            <CheckCircle2 aria-hidden="true" size={28} />
            <h1 id="sign-in-title">Check your email</h1>
            <p>We sent a secure sign-in link to <strong>{email}</strong>. It can be used once and expires shortly.</p>
            <button className="auth-secondary-button" onClick={() => setEmailSent(false)} type="button">Use a different email</button>
          </div>
        ) : (
          <>
            <div className="sign-in-intro">
              <span className="eyebrow">Cortex Lab workspace</span>
              <h1 id="sign-in-title">Sign in to your workspace</h1>
              <p>Private by default. Your experiments stay yours until you publish them.</p>
            </div>
            {configured ? (
              <div className="sign-in-options">
                <button className="google-auth-button" disabled={isConnecting !== null} onClick={continueWithGoogle} type="button">
                  <span aria-hidden="true" className="google-glyph">G</span>
                  {isConnecting === "google" ? "Connecting..." : "Continue with Google"}
                  <ArrowRight aria-hidden="true" size={16} />
                </button>
                <div className="auth-divider"><span>or</span></div>
                {!showEmail ? (
                  <button className="auth-secondary-button" disabled={isConnecting !== null} onClick={() => setShowEmail(true)} type="button">
                    <Mail aria-hidden="true" size={16} /> Continue with email
                  </button>
                ) : (
                  <form className="sign-in-email-form" onSubmit={sendMagicLink}>
                    <label htmlFor="sign-in-email">Email address</label>
                    <input autoComplete="email" id="sign-in-email" onChange={(event) => setEmail(event.target.value)} placeholder="you@university.edu" required type="email" value={email} />
                    <button className="primary-auth-button" disabled={isConnecting !== null || !email.trim()} type="submit">
                      {isConnecting === "email" ? "Sending link..." : "Send magic link"}
                      <ArrowRight aria-hidden="true" size={16} />
                    </button>
                  </form>
                )}
                <button aria-expanded={showInstitutional} className="auth-secondary-button" onClick={() => setShowInstitutional((value) => !value)} type="button">
                  <Building2 aria-hidden="true" size={16} /> Institutional access
                </button>
                {showInstitutional ? <p className="institutional-note">Institutional SSO is available when your organization has configured a Cortex Lab identity provider. Contact your research administrator to request access.</p> : null}
              </div>
            ) : <p className="sign-in-unavailable">Authentication is not configured in this environment.</p>}
            {error ? <p className="sign-in-error" role="alert">{error}</p> : null}
            <p className="sign-in-legal">By continuing, you agree to the <Link href="/terms">Terms of Use</Link> and <Link href="/privacy">Privacy Policy</Link>.</p>
          </>
        )}
      </section>
      <aside className="sign-in-aside" aria-hidden="true">
        <div className="sign-in-brain"><HeroBrain /></div>
        <div className="sign-in-aside-copy">
          <span className="eyebrow">Research workspace</span>
          <strong>Build the stimulus. Inspect the cortical response.</strong>
          <p>Multimodal experiments, simulated average-subject activation, and reproducible analysis in one place.</p>
        </div>
      </aside>
      <p className="sign-in-browse">New to Cortex Lab? <Link href="/library">Explore the public library</Link> before signing in.</p>
    </main>
  );
}

export default function SignInPage() {
  return <Suspense fallback={<main className="sign-in-page" />}><SignInContent /></Suspense>;
}
