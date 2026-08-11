"use client";

import Link from "next/link";
import { useState } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BrainCircuit,
  FlaskConical,
  Image,
  LibraryBig,
  Menu,
  Mic,
  ScanLine,
  Sparkles,
  Type,
  Video,
  X
} from "lucide-react";
import { HeroBrain } from "./HeroBrain";

const modalities = [
  { label: "Text", icon: Type },
  { label: "Images", icon: Image },
  { label: "Audio", icon: Mic },
  { label: "Video", icon: Video }
];

const templates = [
  "FFA faces versus houses",
  "Semantic N400",
  "Visual eccentricity",
  "Emotion processing",
  "Speech versus music",
  "Reading versus listening"
];

export function CortexLandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);

  function closeMenu() {
    setMenuOpen(false);
  }

  return (
    <main className="landing-page" id="top">
      <header className="landing-nav">
        <Link aria-label="Cortex Lab home" className="landing-brand" href="/">
          <span className="landing-brand-mark"><BrainCircuit aria-hidden="true" size={20} strokeWidth={1.7} /></span>
          <span className="landing-brand-copy">
            <strong>Cortex Lab</strong>
            <small>In-silico cortical research</small>
          </span>
        </Link>

        <nav className="landing-nav-links" aria-label="Landing navigation">
          <a href="#method">Method</a>
          <a href="#paradigms">Paradigms</a>
          <Link href="/library">Library</Link>
        </nav>

        <div className="landing-nav-actions">
          <Link className="landing-nav-cta" href="/dashboard">
            <span>Open workspace</span>
            <ArrowUpRight aria-hidden="true" size={15} strokeWidth={1.8} />
          </Link>
          <button
            aria-controls="landing-mobile-menu"
            aria-expanded={menuOpen}
            aria-label={menuOpen ? "Close navigation" : "Open navigation"}
            className="landing-menu-toggle"
            onClick={() => setMenuOpen((open) => !open)}
            type="button"
          >
            {menuOpen ? <X aria-hidden="true" size={19} /> : <Menu aria-hidden="true" size={19} />}
          </button>
        </div>
      </header>

      <nav className={menuOpen ? "landing-mobile-menu open" : "landing-mobile-menu"} id="landing-mobile-menu" aria-label="Mobile navigation">
        <a href="#method" onClick={closeMenu}>Method</a>
        <a href="#paradigms" onClick={closeMenu}>Paradigms</a>
        <Link href="/library" onClick={closeMenu}>Library</Link>
        <Link href="/dashboard" onClick={closeMenu}>Open workspace <ArrowUpRight aria-hidden="true" size={17} /></Link>
      </nav>

      <section className="landing-hero" aria-labelledby="landing-title">
        <div className="landing-hero-copy">
          <span className="landing-kicker"><i aria-hidden="true" /> Multimodal neural simulation</span>
          <h1 id="landing-title">Cortex Lab</h1>
          <p className="landing-hero-lead">Design a stimulus, follow it through time, and inspect a simulated cortical response.</p>
          <div className="landing-hero-actions">
            <Link className="landing-primary-action" href="/dashboard">
              <FlaskConical aria-hidden="true" size={16} strokeWidth={1.8} />
              Build an experiment
              <ArrowRight aria-hidden="true" size={16} strokeWidth={1.8} />
            </Link>
            <Link className="landing-secondary-action" href="/library">
              Browse research library
              <ArrowUpRight aria-hidden="true" size={15} strokeWidth={1.8} />
            </Link>
          </div>
          <p className="landing-hero-note">Research-use simulations. Cortex Lab does not produce measured or diagnostic brain data.</p>
        </div>

        <div className="landing-hero-visual">
          <HeroBrain />
          <div className="landing-brain-readout landing-brain-readout-top">
            <span>Surface</span>
            <strong>fsaverage5</strong>
          </div>
          <div className="landing-brain-readout landing-brain-readout-bottom">
            <span>Output</span>
            <strong>20,484 vertices</strong>
          </div>
          <div className="landing-brain-axis" aria-hidden="true"><i /><span>cortical surface</span></div>
        </div>

        <div className="landing-hero-footer" aria-label="Supported stimulus modalities">
          <span>Stimulus inputs</span>
          <div>
            {modalities.map(({ label, icon: Icon }) => (
              <span key={label}><Icon aria-hidden="true" size={15} strokeWidth={1.65} />{label}</span>
            ))}
          </div>
        </div>
      </section>

      <section className="landing-method" id="method" aria-labelledby="method-title">
        <div className="landing-section-heading">
          <span className="landing-kicker"><i aria-hidden="true" /> A deliberate research flow</span>
          <h2 id="method-title">One surface for the whole experiment.</h2>
        </div>
        <div className="landing-method-steps">
          <article>
            <span>01</span>
            <Type aria-hidden="true" size={21} strokeWidth={1.55} />
            <h3>Compose</h3>
            <p>Arrange text, image, audio, and video blocks with precise timing in a private experiment draft.</p>
          </article>
          <article>
            <span>02</span>
            <ScanLine aria-hidden="true" size={21} strokeWidth={1.55} />
            <h3>Run</h3>
            <p>Process each stimulus through the experiment pipeline and follow progress as the response is prepared.</p>
          </article>
          <article>
            <span>03</span>
            <Activity aria-hidden="true" size={21} strokeWidth={1.55} />
            <h3>Inspect</h3>
            <p>Move through activation frames, regions, cognitive-state estimates, and comparison analyses in one viewer.</p>
          </article>
        </div>
      </section>

      <section className="landing-paradigms" id="paradigms" aria-labelledby="paradigms-title">
        <div className="landing-paradigms-intro">
          <span className="landing-kicker"><i aria-hidden="true" /> Six ready starting points</span>
          <h2 id="paradigms-title">Begin with a paradigm. Keep the reasoning visible.</h2>
          <p>Each template opens as an editable private draft, ready for a real stimulus timeline.</p>
          <Link className="landing-text-link" href="/library">View the research library <ArrowRight aria-hidden="true" size={15} /></Link>
        </div>
        <ol className="landing-template-list">
          {templates.map((template, index) => (
            <li key={template}>
              <Link aria-label={`Browse ${template} in the research library`} href="/library">
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{template}</strong>
                <ArrowUpRight aria-hidden="true" size={17} strokeWidth={1.55} />
              </Link>
            </li>
          ))}
        </ol>
      </section>

      <section className="landing-research-use" id="research-use" aria-labelledby="research-use-title">
        <div>
          <span className="landing-kicker"><i aria-hidden="true" /> Built for research clarity</span>
          <h2 id="research-use-title">Useful when the result stays honest.</h2>
        </div>
        <div className="landing-research-points">
          <p><BrainCircuit aria-hidden="true" size={19} strokeWidth={1.55} /> Simulated average-subject cortical predictions, shown with their timing and provenance.</p>
          <p><Sparkles aria-hidden="true" size={19} strokeWidth={1.55} /> Private drafts by default, with publication and forking as deliberate research-sharing actions.</p>
          <p><LibraryBig aria-hidden="true" size={19} strokeWidth={1.55} /> Curated paradigms and modality-aware processing keep the experiment legible from input to result.</p>
        </div>
      </section>

      <footer className="landing-footer">
        <Link className="landing-brand landing-footer-brand" href="/">
          <span className="landing-brand-mark"><BrainCircuit aria-hidden="true" size={18} strokeWidth={1.7} /></span>
          <span className="landing-brand-copy"><strong>Cortex Lab</strong><small>Research workspace</small></span>
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
