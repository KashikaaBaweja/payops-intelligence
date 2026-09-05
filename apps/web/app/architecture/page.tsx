import dynamic from "next/dynamic";
import Link from "next/link";
import { TracePipeline } from "../../components/TracePipeline";
import { TRACE_STAGES } from "../../lib/trace";
import type { StageId, StageState } from "../../lib/trace";

const AgentOrbit = dynamic(
  () => import("../../components/landing/AgentOrbit").then((module) => module.AgentOrbit),
  { ssr: false, loading: () => <div className="graph-scene" aria-hidden /> },
);

const STATES = Object.fromEntries(
  TRACE_STAGES.map((stage) => [stage.id, "pending" as StageState]),
) as Record<StageId, StageState>;

export default function ArchitecturePage() {
  return (
    <div className="landing">
      <header className="landing-bar">
        <Link href="/" className="brand-lockup">
          <span className="mark" aria-hidden>
            PI
          </span>
          <span>
            <strong>PayIntel AI</strong>
            <small>How the graph actually runs</small>
          </span>
        </Link>
        <nav className="landing-nav" aria-label="Architecture">
          <Link className="btn btn-ghost" href="/">
            Product
          </Link>
          <Link className="btn btn-primary" href="/research" style={{ width: "auto" }}>
            Start Research
          </Link>
        </nav>
      </header>
      <main className="landing-section">
        <h1 className="page-title">Eight agents on one LangGraph FSM.</h1>
        <p className="page-lead">
          Orchestrator plans catalog tasks. Researcher and Retrieval loop retrieve → score →
          rewrite. Data Analyst uses allowlisted SQL. ML Agent runs classification or
          capture-latency regression, never mixed metrics. Transaction Agent checks
          payment invariants and can execute a live debit/credit with rollback. Critic
          and Writer cannot invent evidence.
        </p>
        <p className="page-lead">
          Isolation for ledger transfers is SQLite BEGIN IMMEDIATE or PostgreSQL
          SERIALIZABLE. Traces stay tool, query, evidence, and decision — not private
          chain-of-thought.
        </p>
        <section className="panel" style={{ marginTop: 28 }}>
          <div className="panel-hd">Agent network</div>
          <div className="panel-bd">
            <AgentOrbit />
            <TracePipeline states={STATES} events={[]} />
          </div>
        </section>
        <div className="cta-row">
          <Link className="btn" href="/dashboard">
            Open console
          </Link>
          <Link className="btn btn-ghost" href="/">
            Back
          </Link>
        </div>
      </main>
    </div>
  );
}
