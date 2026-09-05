import dynamic from "next/dynamic";
import Link from "next/link";

const AgentOrbit = dynamic(
  () => import("../components/landing/AgentOrbit").then((module) => module.AgentOrbit),
  { ssr: false, loading: () => <div className="graph-scene" aria-hidden /> },
);

const PILLARS = [
  {
    title: "Agentic RAG",
    body: "Retrieve, score, and rewrite until the critic has enough payment-ops evidence — or the loop reports insufficient sources.",
  },
  {
    title: "Scoped ML",
    body: "Classification and capture-latency regression stay separate. Holdout metrics are never mixed, and dummy scores are never invented.",
  },
  {
    title: "Transaction intelligence",
    body: "Catalog SQL plus a live debit/credit ledger. Injected failure rolls the same SQL transaction back so ACID is observable, not described.",
  },
];

export default function LandingPage() {
  return (
    <div className="landing">
      <header className="landing-bar">
        <Link href="/" className="brand-lockup">
          <span className="mark" aria-hidden>
            PI
          </span>
          <span>
            <strong>PayIntel AI</strong>
            <small>Agentic payment intelligence</small>
          </span>
        </Link>
        <nav className="landing-nav" aria-label="Landing">
          <Link className="btn btn-ghost" href="/architecture">
            Architecture
          </Link>
          <Link className="btn btn-primary" href="/research" style={{ width: "auto" }}>
            Start Research
          </Link>
        </nav>
      </header>
      <section className="hero">
        <div>
          <p className="chip idle">Deterministic graph · hashed RAG · scoped ML</p>
          <h1>AI that researches, analyzes and validates payment intelligence.</h1>
          <p>
            PayIntel combines Agentic RAG, leakage-safe machine learning, and transaction
            intelligence over a synthetic payments ledger. Agents retrieve, score, and
            rewrite queries, then a critic checks citations before the writer publishes a
            report. Demo mode does not call an LLM.
          </p>
          <div className="cta-row">
            <Link className="btn btn-primary" href="/research" style={{ width: "auto" }}>
              Start Research
            </Link>
            <Link className="btn btn-ghost" href="/architecture">
              Explore Architecture
            </Link>
          </div>
        </div>
        <AgentOrbit />
      </section>
      <section className="landing-section" aria-labelledby="how-heading">
        <h2 id="how-heading">Built for payment operations, not chat.</h2>
        <div className="pillar-grid">
          {PILLARS.map((pillar) => (
            <article className="stat-card" key={pillar.title}>
              <span>{pillar.title}</span>
              <p className="page-lead" style={{ marginTop: 10 }}>
                {pillar.body}
              </p>
            </article>
          ))}
        </div>
      </section>
      <section className="landing-section" aria-labelledby="flow-heading">
        <h2 id="flow-heading">From question to cited report.</h2>
        <p className="page-lead">
          Research workspace → agent execution → evidence → ML and ledger analysis →
          structured report. Every hop is a typed tool call with an audit trail.
        </p>
        <div className="cta-row">
          <Link className="btn" href="/dashboard">
            Open console
          </Link>
          <Link className="btn btn-ghost" href="/system">
            System health
          </Link>
        </div>
      </section>
    </div>
  );
}
