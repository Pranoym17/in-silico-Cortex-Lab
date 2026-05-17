import Link from "next/link";

export default function HomePage() {
  return (
    <main className="shell">
      <section className="panel">
        <h1>Cortex Lab</h1>
        <p>Design multimodal neuroscience experiments and stream TRIBE v2 activation predictions into a 3D cortical viewer.</p>
        <Link href="/dashboard">Open dashboard</Link>
      </section>
    </main>
  );
}

