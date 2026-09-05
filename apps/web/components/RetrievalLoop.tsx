"use client";

import type { RetrievalSummary } from "../lib/types";

export function RetrievalLoop({ retrieval }: { retrieval: RetrievalSummary | null }) {
  if (!retrieval || retrieval.rounds.length === 0) {
    return <div className="empty">No document retrieval rounds for this case.</div>;
  }
  return (
    <div className="retrieval-loop">
      <div className="score-row" style={{ marginBottom: 12 }}>
        <span className={`chip ${retrieval.sufficient ? "ok" : "warn"}`}>
          {retrieval.sufficient ? "Evidence sufficient" : "Evidence insufficient"}
        </span>
        <span className="mono" style={{ color: "var(--muted)" }}>
          {retrieval.iterations} / {retrieval.max_iterations} searches · {retrieval.latency_ms.toFixed(0)}{" "}
          ms
        </span>
        {retrieval.conflicting ? <span className="chip warn">Conflicting sources</span> : null}
      </div>
      {retrieval.rounds.map((step, index) => (
        <div key={`${step.search_index}-${step.query}`}>
          <article className="retrieval-step">
            <div className="retrieval-step-hd">
              <strong>Search #{step.search_index}</strong>
              <span className={`chip ${step.sufficient ? "ok" : "warn"}`}>{labelFor(step.decision)}</span>
            </div>
            <div className="snippet">{step.query}</div>
            <div className="mono" style={{ color: "var(--faint)", marginTop: 6 }}>
              retrieved {step.retrieved} · kept {step.kept} · rejected {step.rejected} ·{" "}
              {step.latency_ms.toFixed(0)} ms
            </div>
          </article>
          {index < retrieval.rounds.length - 1 ? (
            <div className="retrieval-arrow">
              → query rewritten
              {retrieval.rounds[index + 1]?.rewrite_reason
                ? ` · ${retrieval.rounds[index + 1].rewrite_reason}`
                : ""}
            </div>
          ) : null}
        </div>
      ))}
      {retrieval.sufficient ? (
        <div className="retrieval-arrow">→ excerpt generated from cited sources</div>
      ) : null}
      {retrieval.grounded_excerpt ? (
        <div className="snippet" style={{ marginTop: 10 }}>
          {retrieval.grounded_excerpt}
        </div>
      ) : null}
    </div>
  );
}

function labelFor(decision: RetrievalSummary["rounds"][number]["decision"]): string {
  if (decision === "sufficient") {
    return "evidence sufficient";
  }
  if (decision === "rewrite") {
    return "insufficient evidence";
  }
  if (decision === "no_results") {
    return "no results";
  }
  return "iteration cap";
}
