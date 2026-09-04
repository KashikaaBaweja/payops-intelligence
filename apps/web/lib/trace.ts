import type { TraceEvent } from "./types";

export const TRACE_STAGES = [
  { id: "planner", label: "Planner" },
  { id: "researcher", label: "Researcher" },
  { id: "analyst", label: "Data Analyst" },
  { id: "sufficiency", label: "Evidence Check" },
  { id: "refine", label: "Additional Research" },
  { id: "verifier", label: "Verifier" },
  { id: "critic", label: "Critic" },
  { id: "writer", label: "Final Report" },
] as const;

export type StageId = (typeof TRACE_STAGES)[number]["id"];
export type StageState = "pending" | "active" | "complete" | "skipped";

export function stageForEvent(event: TraceEvent): StageId | null {
  if (event.node === "planner") {
    return "planner";
  }
  if (event.node === "investigate") {
    if (event.tool === "search_docs" || event.decision === "retrieve_docs") {
      return "researcher";
    }
    return "analyst";
  }
  if (event.node === "aggregate" || event.node === "sufficiency" || event.node === "incident_risk") {
    return "sufficiency";
  }
  if (event.node === "refine") {
    return "refine";
  }
  if (event.node === "verifier") {
    return "verifier";
  }
  if (event.node === "critic") {
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
      states[stage.id] = "complete";
    } else if (running && stage.id === "planner" && seen.size === 0) {
      states[stage.id] = "active";
    } else if (running) {
      states[stage.id] = "pending";
    } else if (seen.size > 0) {
      states[stage.id] = "skipped";
    } else {
      states[stage.id] = "pending";
    }
  }
  let current: StageId | null = null;
  if (running) {
    current = last ?? "planner";
  } else if (seen.has("writer")) {
    current = "writer";
  } else {
    current = last;
  }
  return { states, current };
}

export function stageLabel(id: StageId | null): string {
  if (!id) {
    return "Idle";
  }
  return TRACE_STAGES.find((stage) => stage.id === id)?.label ?? id;
}
