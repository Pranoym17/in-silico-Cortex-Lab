import Link from "next/link";

export default function DashboardPage() {
  return (
    <main className="shell">
      <h1>Experiments</h1>
      <div className="panel">
        <p>No experiments yet. The scaffold is ready for the builder and API integration.</p>
        <Link href="/builder/demo">Create demo experiment</Link>
      </div>
    </main>
  );
}

