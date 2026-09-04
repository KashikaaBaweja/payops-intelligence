"use client";

import { TRACE_STAGES, type StageState } from "../lib/trace";

export function TracePipeline({
  states,
}: {
  states: Record<string, StageState>;
}) {
  return (
    <div className="pipeline" aria-label="Investigation trace">
      {TRACE_STAGES.map((stage, index) => (
        <span key={stage.id} style={{ display: "contents" }}>
          {index > 0 ? (
            <span className="arrow" aria-hidden>
              →
            </span>
          ) : null}
          <div className={`stage ${states[stage.id] ?? "pending"}`}>
            <div className="stage-name">{stage.label}</div>
            <div className="stage-state">{states[stage.id] ?? "pending"}</div>
          </div>
        </span>
      ))}
    </div>
  );
}
