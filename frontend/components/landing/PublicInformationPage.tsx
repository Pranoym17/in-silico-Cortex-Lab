import Link from "next/link";
import { ArrowLeft, ArrowUpRight, BrainCircuit } from "lucide-react";

type InformationSection = {
  heading: string;
  paragraphs: string[];
};

type PublicInformationPageProps = {
  eyebrow: string;
  title: string;
  introduction: string;
  sections: InformationSection[];
};

export function PublicInformationPage({ eyebrow, title, introduction, sections }: PublicInformationPageProps) {
  return (
    <main className="landing-info-page">
      <header className="landing-info-nav">
        <Link aria-label="Cortex Lab home" className="landing-brand" href="/">
          <span className="landing-brand-mark"><BrainCircuit aria-hidden="true" size={20} strokeWidth={1.7} /></span>
          <span className="landing-brand-copy">
            <strong>Cortex Lab</strong>
            <small>In-silico cortical research</small>
          </span>
        </Link>
        <Link className="landing-info-workspace-link" href="/dashboard">Open workspace <ArrowUpRight aria-hidden="true" size={15} /></Link>
      </header>

      <article className="landing-info-content">
        <Link className="landing-info-back" href="/"><ArrowLeft aria-hidden="true" size={15} /> Back to Cortex Lab</Link>
        <span className="landing-kicker"><i aria-hidden="true" /> {eyebrow}</span>
        <h1>{title}</h1>
        <p className="landing-info-introduction">{introduction}</p>
        <div className="landing-info-sections">
          {sections.map((section) => (
            <section key={section.heading}>
              <h2>{section.heading}</h2>
              {section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
            </section>
          ))}
        </div>
      </article>

      <footer className="landing-info-footer">
        <span>In-silico cortical research for transparent stimulus experiments.</span>
        <nav aria-label="Information navigation">
          <Link href="/research-use">Research use</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
          <Link href="/accessibility">Accessibility</Link>
        </nav>
      </footer>
    </main>
  );
}
