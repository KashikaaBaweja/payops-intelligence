"use client";

import { TRACE_STAGES, stageMetrics, stageStatusLabel, type StageState } from "../lib/trace";
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
        const status = stageStatusLabel(state);
        return (
          <li key={stage.id} className={`stage ${state}`}>
            {index > 0 ? (
              <span className="flow-arrow" aria-hidden>
                ↓
              </span>
            ) : null}
            <div className="stage-head">
              <div className="stage-name">{stage.label}</div>
              <div className="stage-state">{status}</div>
            </div>
            <dl className="stage-metrics">
              <div>
                <dt>Status</dt>
                <dd>{status}</dd>
              </div>
              <div>
                <dt>Duration</dt>
                <dd className="mono">
                  {metrics.durationMs == null ? "—" : `${metrics.durationMs} ms`}
                </dd>
              </div>
              <div>
                <dt>Tool calls</dt>
                <dd className="mono">
                  {metrics.toolNames.length ? metrics.toolNames.join(", ") : "—"}
                </dd>
              </div>
              <div>
                <dt>Result</dt>
                <dd>{metrics.summary}</dd>
              </div>
            </dl>
            <div className="stage-summary">{metrics.summary}</div>
          </li>
        );
      })}
    </ol>
  );
}
