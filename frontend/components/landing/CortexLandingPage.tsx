"use client";

import NextImage from "next/image";
import Link from "next/link";
import { useState } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BrainCircuit,
  CircleUserRound,
  FlaskConical,
  Image as ImageIcon,
  LibraryBig,
  Menu,
  Mic,
  ScanLine,
  Type,
  Video,
  X
} from "lucide-react";

const templates = [
  "FFA faces versus houses",
  "Semantic N400",
  "Visual eccentricity",
  "Emotion processing",
  "Speech versus music",
  "Reading versus listening"
];

const templateIcons = [BrainCircuit, Type, ImageIcon, Activity, Mic, LibraryBig];

export function CortexLandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);

  function closeMenu() {
    setMenuOpen(false);
  }

  return (
    <main className="landing-page" id="top">
      <section className="landing-hero" aria-labelledby="landing-title">
        <video
          aria-hidden="true"
          autoPlay
          className="landing-hero-video"
          loop
          muted
          playsInline
          preload="metadata"
          src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260715_082433_69699cf8-444b-4484-93cc-053e57896dfd.mp4"
        />
        <div aria-hidden="true" className="landing-hero-contrast" />
        <header className="landing-nav">
        <Link aria-label="Cortex Lab home" className="landing-brand" href="/">
          <NextImage
            alt="Cortex Lab"
            className="landing-brand-logo"
            height={76}
            priority
            src="/brand/cortex-lab-logo.png"
            width={138}
          />
        </Link>

        <nav className="landing-nav-links liquid-glass" aria-label="Landing navigation">
          <a href="#top">Home</a>
          <a href="#method">Method</a>
          <Link href="/library">Library</Link>
        </nav>

        <div className="landing-nav-actions">
          <Link aria-label="Sign in to Cortex Lab" className="landing-account-link liquid-glass" href="/sign-in"><CircleUserRound aria-hidden="true" size={19} strokeWidth={1.5} /></Link>
          <button
            aria-controls="landing-mobile-menu"
            aria-expanded={menuOpen}
            aria-label={menuOpen ? "Close navigation" : "Open navigation"}
            className={menuOpen ? "landing-menu-toggle open" : "landing-menu-toggle"}
            onClick={() => setMenuOpen((open) => !open)}
            type="button"
          >
            {menuOpen ? <X aria-hidden="true" size={19} /> : <Menu aria-hidden="true" size={19} />}
          </button>
        </div>
        </header>

        <nav
        className={menuOpen ? "landing-mobile-menu open" : "landing-mobile-menu"}
        id="landing-mobile-menu"
        aria-hidden={!menuOpen}
        aria-label="Mobile navigation"
      >
        <a href="#top" onClick={closeMenu}>Home</a>
        <a href="#method" onClick={closeMenu}>Method</a>
        <Link href="/library" onClick={closeMenu}>Library</Link>
        <Link className="landing-mobile-account" href="/sign-in" onClick={closeMenu}><CircleUserRound aria-hidden="true" size={19} /> Account</Link>
        </nav>

        <div className={menuOpen ? "landing-hero-content menu-open" : "landing-hero-content"}>
          <div className="landing-hero-copy">
          <div className="landing-hero-badge liquid-glass">
            <span>multimodal cortical research</span>
          </div>
          <h1 id="landing-title">
            Cortex Lab<br />
            <span>for cortical research.</span>
          </h1>
          <p className="landing-hero-lead">
            Design multimodal experiments. Inspect simulated cortical responses.
          </p>
          <Link className="landing-hero-cta liquid-glass" href="/dashboard">Build an experiment <ArrowRight aria-hidden="true" size={16} /></Link>
          </div>
          <div className="landing-hero-stats" aria-label="Cortex Lab research capabilities">
            <div><Activity aria-hidden="true" size={19} strokeWidth={1.45} /><strong>20,484</strong><span>surface vertices</span></div>
            <div><ScanLine aria-hidden="true" size={19} strokeWidth={1.45} /><strong>4 modalities</strong><span>one timeline</span></div>
          </div>
        </div>
      </section>

      <section className="landing-method" id="method" aria-labelledby="method-title">
        <div className="landing-section-heading">
          <p className="landing-overline">The workflow</p>
          <h2 id="method-title">A complete experiment, kept legible from stimulus to surface.</h2>
        </div>
        <div className="landing-method-steps">
          <article>
            <span>01</span>
            <Type aria-hidden="true" size={20} strokeWidth={1.5} />
            <h3>Compose</h3>
            <p>Arrange text, image, audio, and video blocks with their conditions and exact timing in a private draft.</p>
          </article>
          <article>
            <span>02</span>
            <ScanLine aria-hidden="true" size={20} strokeWidth={1.5} />
            <h3>Run</h3>
            <p>Process each stimulus through the experiment pipeline while live progress reports stay attached to the job.</p>
          </article>
          <article>
            <span>03</span>
            <Activity aria-hidden="true" size={20} strokeWidth={1.5} />
            <h3>Inspect</h3>
            <p>Move through activation frames, regions, cognitive states, and comparison analyses in a dedicated viewer.</p>
          </article>
        </div>
      </section>

      <section className="landing-paradigms" id="paradigms" aria-labelledby="paradigms-title">
        <div className="landing-paradigms-intro">
          <p className="landing-overline">Six research starting points</p>
          <h2 id="paradigms-title">Start with a paradigm. Keep the reasoning visible.</h2>
          <p>Each template opens as an editable private draft, ready for a real stimulus timeline.</p>
          <Link className="landing-text-link" href="/library">Browse the research library <ArrowRight aria-hidden="true" size={15} /></Link>
        </div>
        <ol className="landing-template-list">
          {templates.map((template, index) => {
            const Icon = templateIcons[index];
            return (
            <li key={template}>
              <Link aria-label={`Browse ${template} in the research library`} href="/library">
                <span className="landing-template-icon"><Icon aria-hidden="true" size={17} strokeWidth={1.7} /></span>
                <strong>{template}</strong>
                <ArrowUpRight aria-hidden="true" size={17} strokeWidth={1.55} />
              </Link>
            </li>
            );
          })}
        </ol>
      </section>

      <section className="landing-research-use" aria-labelledby="research-use-title">
        <div>
          <p className="landing-overline">Research clarity</p>
          <h2 id="research-use-title">A workspace that keeps the result in context.</h2>
        </div>
        <div className="landing-research-points">
          <p><BrainCircuit aria-hidden="true" size={19} strokeWidth={1.5} /> Simulated average-subject cortical predictions are shown with their timing and provenance.</p>
          <p><FlaskConical aria-hidden="true" size={19} strokeWidth={1.5} /> Experiments stay private by default. Publication and forking are explicit research-sharing actions.</p>
          <p><LibraryBig aria-hidden="true" size={19} strokeWidth={1.5} /> Curated paradigms and modality-aware processing preserve the line from input to result.</p>
        </div>
        <div className="landing-workspace-preview" aria-label="Cortex Lab workspace preview">
          <div className="workspace-preview-bar"><span /><span /><span /><strong>Visual eccentricity</strong><b>Validated</b></div>
          <div className="workspace-preview-body">
            <div className="workspace-preview-timeline">
              <span>Stimulus timeline</span>
              <div><i className="preview-image" /><i className="preview-text" /><i className="preview-audio" /><i className="preview-video" /></div>
              <small>00:00</small><small>00:10</small><small>00:20</small>
            </div>
            <div className="workspace-preview-surface">
              <span>Activation surface</span>
              <div className="workspace-preview-brain" aria-hidden="true"><i /><i /><i /><i /><i /></div>
              <div className="workspace-preview-scale"><i /><i /><i /><span>activation</span></div>
            </div>
          </div>
        </div>
      </section>

      <footer className="landing-footer">
        <Link aria-label="Cortex Lab home" className="landing-footer-brand" href="/">
          <NextImage alt="Cortex Lab" className="landing-footer-logo" height={64} src="/brand/cortex-lab-logo.png" width={116} />
        </Link>
        <p>In-silico cortical research for transparent stimulus experiments.</p>
        <nav aria-label="Footer navigation">
          <Link href="/dashboard">Workspace</Link>
          <Link href="/library">Library</Link>
          <Link href="/research-use">Research use</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
          <Link href="/accessibility">Accessibility</Link>
        </nav>
      </footer>
    </main>
  );
}
