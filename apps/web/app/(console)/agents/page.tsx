"use client";

import { useEffect, useMemo, useState } from "react";
import { AgentGraph } from "../../../components/graph/AgentGraph";
import { TracePipeline } from "../../../components/TracePipeline";
import { EmptyState, ErrorState, LoadingState } from "../../../components/states/PageState";
import { getInvestigation, getTrace } from "../../../lib/api";
import { lastInvestigationId } from "../../../lib/session";
import { stageStates } from "../../../lib/trace";
import type { TraceEvent } from "../../../lib/types";
import { ApiError } from "../../../lib/types";

export default function AgentsPage() {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [question, setQuestion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const { states } = useMemo(() => stageStates(events, false), [events]);

  useEffect(() => {
    const id = lastInvestigationId();
    if (!id) {
      setLoading(false);
      return;
    }
    Promise.all([getInvestigation(id), getTrace(id)])
      .then(([inv, trace]) => {
        setQuestion(inv.question);
        setEvents(trace.events?.length ? trace.events : inv.report?.agent_execution_summary ?? []);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Trace unavailable."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <h1 className="page-title">Agents</h1>
      <p className="page-lead">
        Orchestrator through Writer for the last research run. Each node shows status, tool
        count, and the last decision — not hidden model reasoning.
      </p>
      {loading ? <LoadingState label="Loading agent trace…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      {!loading && !events.length ? (
        <EmptyState
          title="No agent run in this browser"
          detail="Run a question from Research. The graph writes a safe execution trace."
        />
      ) : null}
      {events.length ? (
        <section className="panel">
          <div className="panel-hd">
            Last question
            <span className="hint">{question}</span>
          </div>
          <div className="panel-bd">
            <AgentGraph states={states} events={events} question={question} caption="Last execution" />
            <TracePipeline states={states} events={events} />
          </div>
        </section>
      ) : null}
    </>
  );
}
