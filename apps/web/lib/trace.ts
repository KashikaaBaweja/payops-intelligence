import type { TraceEvent } from "./types";

export const TRACE_STAGES = [
  { id: "planner", label: "Orchestrator" },
  { id: "researcher", label: "Researcher" },
  { id: "rag", label: "RAG" },
  { id: "analyst", label: "Data Analyst" },
  { id: "risk", label: "ML Agent" },
  { id: "integrity", label: "Transaction Agent" },
  { id: "critic", label: "Critic" },
  { id: "writer", label: "Report" },
] as const;

export type StageId = (typeof TRACE_STAGES)[number]["id"];
export type StageState = "pending" | "active" | "complete" | "skipped";

export function stageForEvent(event: TraceEvent): StageId | null {
  if (event.node === "planner") {
    return "planner";
  }
  if (event.node === "investigate") {
    if (event.action.startsWith("rag_")) {
      return "rag";
    }
    if (event.tool === "search_docs" || event.decision === "retrieve_docs") {
      return "researcher";
    }
    if (
      event.tool === "ml_risk" ||
      event.tool === "ml_regression" ||
      event.decision === "score_risk" ||
      event.decision === "score_regression"
    ) {
      return "risk";
    }
    if (event.tool === "validate_integrity" || event.decision === "validate_integrity") {
      return "integrity";
    }
    return "analyst";
  }
  if (event.node === "aggregate" || event.node === "sufficiency" || event.node === "refine") {
    return "rag";
  }
  if (event.node === "incident_risk") {
    return "analyst";
  }
  if (event.node === "verifier" || event.node === "critic") {
    return "critic";
  }
  if (event.node === "writer") {
    return "writer";
  }
  return null;
}

export function stageStates(
  events: TraceEvent[],
  running: boolean,
): { states: Record<StageId, StageState>; current: StageId | null } {
  const seen = new Set<StageId>();
  let last: StageId | null = null;
  for (const event of events) {
    const stage = stageForEvent(event);
    if (stage) {
      seen.add(stage);
      last = stage;
    }
  }
  const states = {} as Record<StageId, StageState>;
  for (const stage of TRACE_STAGES) {
    if (seen.has(stage.id)) {
      states[stage.id] = running && stage.id === last ? "active" : "complete";
    } else if (running || seen.size === 0) {
      states[stage.id] = "pending";
    } else {
      states[stage.id] = "skipped";
    }
  }
  let current: StageId | null = null;
  if (running) {
    current = last;
  } else if (seen.has("writer")) {
    current = "writer";
  } else {
    current = last;
  }
  return { states, current };
}

export function stageMetrics(events: TraceEvent[], id: StageId) {
  const matched = events.filter((event) => stageForEvent(event) === id);
  const tools = new Set(
    matched.map((event) => event.tool).filter((tool): tool is string => Boolean(tool)),
  );
  const last = matched[matched.length - 1];
  const firstTs = Date.parse(matched[0]?.timestamp ?? "");
  const lastTs = Date.parse(last?.timestamp ?? "");
  const durationMs =
    Number.isFinite(firstTs) && Number.isFinite(lastTs) ? Math.max(0, lastTs - firstTs) : null;
  return {
    events: matched.length,
    tools: tools.size,
    toolNames: [...tools],
    durationMs,
    summary: last?.decision || last?.action || (matched.length ? "done" : "—"),
  };
}

export function stageStatusLabel(state: StageState): string {
  if (state === "complete") {
    return "✓";
  }
  if (state === "active") {
    return "running";
  }
  if (state === "skipped") {
    return "skipped";
  }
  return "waiting";
}

export function stageLabel(id: StageId | null): string {
  if (!id) {
    return "Idle";
  }
  return TRACE_STAGES.find((stage) => stage.id === id)?.label ?? id;
}
