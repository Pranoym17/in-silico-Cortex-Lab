"use client";

import Link from "next/link";
import NextImage from "next/image";
import { FormEvent, Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowRight, Building2, CheckCircle2, Eye, EyeOff, KeyRound, Mail } from "lucide-react";
import { HeroBrain } from "@/components/landing/HeroBrain";
import { getSupabaseBrowserClient, isSupabaseConfigured } from "@/lib/supabase";

function safeNextPath(value: string | null) {
  return value?.startsWith("/") && !value.startsWith("//") ? value : "/dashboard";
}

function SignInContent() {
  const searchParams = useSearchParams();
  const nextPath = useMemo(() => safeNextPath(searchParams.get("next")), [searchParams]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [authMode, setAuthMode] = useState<"sign-in" | "create-account">("sign-in");
  const [showPassword, setShowPassword] = useState(false);
  const [showMagicLink, setShowMagicLink] = useState(false);
  const [showInstitutional, setShowInstitutional] = useState(false);
  const [isConnecting, setIsConnecting] = useState<"google" | "credentials" | "magic-link" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmationMessage, setConfirmationMessage] = useState<string | null>(null);

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

  async function continueWithCredentials(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const supabase = getSupabaseBrowserClient();
    if (!supabase || !email.trim() || !password) return;

    if (authMode === "create-account" && password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setError(null);
    setIsConnecting("credentials");
    const result = authMode === "sign-in"
      ? await supabase.auth.signInWithPassword({ email: email.trim(), password })
      : await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: { emailRedirectTo: `${window.location.origin}${nextPath}` }
      });
    setIsConnecting(null);
    if (result.error) {
      setError(result.error.message);
      return;
    }

    if (authMode === "create-account" && !result.data.session) {
      setConfirmationMessage("Check your email to confirm the new account before signing in.");
      return;
    }
    window.location.assign(nextPath);
  }

  async function sendMagicLink() {
    const supabase = getSupabaseBrowserClient();
    if (!supabase || !email.trim()) return;
    setError(null);
    setIsConnecting("magic-link");
    const { error: signInError } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { emailRedirectTo: `${window.location.origin}${nextPath}` }
    });
    setIsConnecting(null);
    if (signInError) {
      setError(signInError.message);
      return;
    }
    setConfirmationMessage(`We sent a secure sign-in link to ${email.trim()}. It can be used once and expires shortly.`);
  }

  return (
    <main className="sign-in-page">
      <section className="sign-in-card" aria-labelledby="sign-in-title">
        <Link className="sign-in-brand" href="/">
          <NextImage alt="Cortex Lab" height={52} src="/brand/cortex-lab-logo.png" width={92} />
          <span>Cortex Lab</span>
        </Link>
        {confirmationMessage ? (
          <div className="sign-in-confirmation" role="status">
            <CheckCircle2 aria-hidden="true" size={28} />
            <h1 id="sign-in-title">Check your email</h1>
            <p>{confirmationMessage}</p>
            <button className="auth-secondary-button" onClick={() => setConfirmationMessage(null)} type="button">Use a different email</button>
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
                <div aria-label="Account action" className="auth-mode-tabs" role="tablist">
                  <button aria-selected={authMode === "sign-in"} className={authMode === "sign-in" ? "active" : ""} onClick={() => { setAuthMode("sign-in"); setError(null); }} role="tab" type="button">Sign in</button>
                  <button aria-selected={authMode === "create-account"} className={authMode === "create-account" ? "active" : ""} onClick={() => { setAuthMode("create-account"); setError(null); }} role="tab" type="button">Create account</button>
                </div>
                <button className="google-auth-button" disabled={isConnecting !== null} onClick={continueWithGoogle} type="button">
                  <img alt="" aria-hidden="true" className="google-glyph" src="/brand/google-g.svg" />
                  {isConnecting === "google" ? "Connecting..." : "Continue with Google"}
                  <ArrowRight aria-hidden="true" size={16} />
                </button>
                <div className="auth-divider"><span>or</span></div>
                <form className="sign-in-email-form" onSubmit={continueWithCredentials}>
                  <label htmlFor="sign-in-email">Email address</label>
                  <input autoComplete="email" id="sign-in-email" onChange={(event) => setEmail(event.target.value)} placeholder="you@university.edu" required type="email" value={email} />
                  <label htmlFor="sign-in-password">Password</label>
                  <div className="password-field">
                    <input autoComplete={authMode === "sign-in" ? "current-password" : "new-password"} id="sign-in-password" minLength={6} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" required type={showPassword ? "text" : "password"} value={password} />
                    <button aria-label={showPassword ? "Hide password" : "Show password"} className="password-visibility" onClick={() => setShowPassword((visible) => !visible)} title={showPassword ? "Hide password" : "Show password"} type="button">
                      {showPassword ? <EyeOff aria-hidden="true" size={17} /> : <Eye aria-hidden="true" size={17} />}
                    </button>
                  </div>
                  {authMode === "create-account" ? <>
                    <label htmlFor="sign-in-password-confirm">Confirm password</label>
                    <input autoComplete="new-password" id="sign-in-password-confirm" minLength={6} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="Repeat your password" required type="password" value={confirmPassword} />
                  </> : null}
                  <button className="primary-auth-button" disabled={isConnecting !== null || !email.trim() || !password} type="submit">
                    <KeyRound aria-hidden="true" size={16} />
                    {isConnecting === "credentials" ? "Please wait..." : authMode === "sign-in" ? "Sign in" : "Create account"}
                    <ArrowRight aria-hidden="true" size={16} />
                  </button>
                </form>
                <button className="auth-text-button" disabled={isConnecting !== null || !email.trim()} onClick={() => { setShowMagicLink((visible) => !visible); setError(null); }} type="button">
                  <Mail aria-hidden="true" size={15} /> Prefer a passwordless email link?
                </button>
                {showMagicLink ? <button className="auth-secondary-button" disabled={isConnecting !== null || !email.trim()} onClick={sendMagicLink} type="button">
                  <Mail aria-hidden="true" size={16} /> {isConnecting === "magic-link" ? "Sending link..." : "Send secure email link"}
                </button> : null}
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
