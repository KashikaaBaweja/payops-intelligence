"use client";

import { TRACE_STAGES, stageMetrics, type StageState } from "../lib/trace";
import type { TraceEvent } from "../lib/types";

export function TracePipeline({
  states,
  events = [],
}: {
  states: Record<string, StageState>;
  events?: TraceEvent[];
}) {
  return (
    <ol className="pipeline agent-flow" aria-label="Agent execution">
      {TRACE_STAGES.map((stage, index) => {
        const metrics = stageMetrics(events, stage.id);
        const state = states[stage.id] ?? "pending";
        return (
          <li key={stage.id} className={`stage ${state}`}>
            {index > 0 ? (
              <span className="flow-arrow" aria-hidden>
                ↓
              </span>
            ) : null}
            <div className="stage-name">{stage.label}</div>
            <div className="stage-state">{state}</div>
            <dl className="stage-metrics">
              <div>
                <dt>Status</dt>
                <dd>{state}</dd>
              </div>
              <div>
                <dt>Duration</dt>
                <dd className="mono">
                  {metrics.durationMs == null ? "—" : `${metrics.durationMs} ms`}
                </dd>
              </div>
              <div>
                <dt>Tools</dt>
                <dd className="mono">{metrics.tools}</dd>
              </div>
              <div>
                <dt>Events</dt>
                <dd className="mono">{metrics.events}</dd>
              </div>
            </dl>
            <div className="stage-summary">{metrics.summary}</div>
          </li>
        );
      })}
    </ol>
  );
}
