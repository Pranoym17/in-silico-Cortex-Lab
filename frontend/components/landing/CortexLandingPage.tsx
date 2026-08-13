"use client";

import NextImage from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BrainCircuit,
  Check,
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
import { HeroBrain } from "./HeroBrain";

const modalityOptions = [
  { label: "Text", icon: Type },
  { label: "Image", icon: ImageIcon },
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

const templateIcons = [BrainCircuit, Type, ImageIcon, Activity, Mic, LibraryBig];

function useTypewriter(text: string, speed = 38, startDelay = 600) {
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    let interval: number | undefined;
    const timeout = window.setTimeout(() => {
      let index = 0;
      interval = window.setInterval(() => {
        index += 1;
        setDisplayed(text.slice(0, index));
        if (index >= text.length) {
          window.clearInterval(interval);
          setDone(true);
        }
      }, speed);
    }, startDelay);

    return () => {
      window.clearTimeout(timeout);
      if (interval) {
        window.clearInterval(interval);
      }
    };
  }, [speed, startDelay, text]);

  return { displayed, done };
}

export function CortexLandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [selectedModalities, setSelectedModalities] = useState<string[]>([]);
  const { displayed, done } = useTypewriter("Cortex Lab\nfor cortical research.");

  function closeMenu() {
    setMenuOpen(false);
  }

  function toggleModality(label: string) {
    setSelectedModalities((current) =>
      current.includes(label) ? current.filter((item) => item !== label) : [...current, label]
    );
  }

  return (
    <main className="landing-page" id="top">
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

        <nav className="landing-nav-links" aria-label="Landing navigation">
          <a href="#method">Method</a>
          <a href="#paradigms">Paradigms</a>
          <Link href="/library">Library</Link>
        </nav>

        <div className="landing-nav-actions">
          <Link className="landing-nav-cta pearl-link" href="/dashboard">Build an experiment <ArrowUpRight aria-hidden="true" size={15} /></Link>
          <button
            aria-controls="landing-mobile-menu"
            aria-expanded={menuOpen}
            aria-label={menuOpen ? "Close navigation" : "Open navigation"}
            className={menuOpen ? "landing-menu-toggle open" : "landing-menu-toggle"}
            onClick={() => setMenuOpen((open) => !open)}
            type="button"
          >
            <span />
            <span />
            <span />
          </button>
        </div>
      </header>

      <nav
        className={menuOpen ? "landing-mobile-menu open" : "landing-mobile-menu"}
        id="landing-mobile-menu"
        aria-hidden={!menuOpen}
        aria-label="Mobile navigation"
      >
        <a href="#method" onClick={closeMenu}>Method</a>
        <a href="#paradigms" onClick={closeMenu}>Paradigms</a>
        <Link href="/library" onClick={closeMenu}>Library</Link>
        <Link href="/dashboard" onClick={closeMenu}>Build an experiment <ArrowUpRight aria-hidden="true" size={18} /></Link>
      </nav>

      <section className="landing-hero" aria-labelledby="landing-title">
        <div className="landing-hero-copy landing-enter">
          <p className="landing-overline">IN-SILICO NEUROSCIENCE LAB</p>
          <h1 id="landing-title">
            {displayed}
            {!done ? <span aria-hidden="true" className="landing-type-cursor" /> : null}
          </h1>
          <p className="landing-hero-lead">
            Design a multimodal stimulus timeline, run a simulated response, and inspect the cortical surface in one research workspace.
          </p>

          <section className="landing-modality-picker" aria-labelledby="modality-picker-title">
            <h2 id="modality-picker-title">What will your experiment contain?</h2>
            <p>Select every stimulus modality that applies.</p>
            <div className="landing-modality-options">
              {modalityOptions.map(({ label, icon: Icon }) => {
                const selected = selectedModalities.includes(label);
                return (
                  <button
                    aria-pressed={selected}
                    className={selected ? "landing-modality-option active" : "landing-modality-option"}
                    key={label}
                    onClick={() => toggleModality(label)}
                    type="button"
                  >
                    <Icon aria-hidden="true" size={15} strokeWidth={1.7} />
                    {label}
                    {selected ? <Check aria-hidden="true" className="landing-modality-check" size={15} strokeWidth={2.2} /> : null}
                  </button>
                );
              })}
            </div>
            {selectedModalities.length === 0 ? (
              <p className="landing-selection-placeholder">Choose a modality to shape a new experiment.</p>
            ) : (
              <div className="landing-selection-feedback" role="status">
                <span>Ready to compose with: {selectedModalities.join(", ")}</span>
                <Link href="/dashboard">Open workspace <ArrowRight aria-hidden="true" size={14} /></Link>
              </div>
            )}
          </section>

          <p className="landing-hero-note">Cortex Lab presents simulated average-subject predictions for research use. It does not produce diagnostic or measured brain data.</p>
        </div>

        <div className="landing-hero-visual">
          <HeroBrain />
          <div className="landing-brain-readout landing-brain-readout-top">
            <span>Surface</span>
            <strong>fsaverage5</strong>
          </div>
          <div className="landing-brain-readout landing-brain-readout-bottom">
            <span>Interactive cortical mesh</span>
            <strong>Drag to inspect</strong>
          </div>
          <div className="landing-brain-axis" aria-hidden="true"><i /><span>20,484 surface vertices</span></div>
        </div>
      </section>

      <section className="landing-stat-strip" aria-label="Cortex Lab research capabilities">
        <div><strong>20,484</strong><span>surface vertices</span></div>
        <div><strong>6</strong><span>validated paradigms</span></div>
        <div><strong>4</strong><span>stimulus modalities</span></div>
        <div><strong>fsaverage5</strong><span>surface resolution</span></div>
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
