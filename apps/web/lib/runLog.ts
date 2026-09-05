import { stageForEvent, stageLabel, type StageId } from "./trace";
import type { TraceEvent } from "./types";

export type GraphId = StageId | "evidence" | "classification" | "query";

export type RunLogLine = {
  at: string;
  agent: string;
  detail: string;
  node: GraphId;
};

export const SETTLEMENT_DEMO_LOG: RunLogLine[] = [
  {
    at: "10:31:04",
    agent: "Query received",
    detail: "Why did settlement delays increase for merchants in the last quarter?",
    node: "query",
  },
  {
    at: "10:31:05",
    agent: "Orchestrator",
    detail: "Classified as research + analytics task",
    node: "planner",
  },
  {
    at: "10:31:05",
    agent: "Researcher",
    detail: "Searching settlement documentation",
    node: "researcher",
  },
  {
    at: "10:31:07",
    agent: "RAG",
    detail: "6 documents retrieved",
    node: "rag",
  },
  {
    at: "10:31:08",
    agent: "Evidence evaluator",
    detail: "Evidence insufficient",
    node: "evidence",
  },
  {
    at: "10:31:08",
    agent: "Researcher",
    detail: "Rewriting query",
    node: "researcher",
  },
  {
    at: "10:31:10",
    agent: "RAG",
    detail: "8 additional documents retrieved",
    node: "rag",
  },
  {
    at: "10:31:11",
    agent: "Data Analyst",
    detail: "Dataset analyzed",
    node: "analyst",
  },
  {
    at: "10:31:13",
    agent: "ML Agent",
    detail: "Regression model selected",
    node: "risk",
  },
  {
    at: "10:31:15",
    agent: "Transaction Agent",
    detail: "Transaction consistency verified",
    node: "integrity",
  },
  {
    at: "10:31:16",
    agent: "Critic",
    detail: "Findings verified",
    node: "critic",
  },
  {
    at: "10:31:17",
    agent: "Report Agent",
    detail: "Final report generated",
    node: "writer",
  },
];

function clock(iso: string | undefined): string {
  if (!iso) {
    return "—";
  }
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return iso.slice(11, 19) || iso;
  }
  return parsed.toISOString().slice(11, 19);
}

function detailFor(event: TraceEvent, stage: StageId | null): string {
  if (event.search_query && (stage === "researcher" || stage === "rag")) {
    if (event.action.includes("rewrite") || event.decision === "rewrite") {
      return "Rewriting query";
    }
    const count = event.evidence_ids.length;
    if (count) {
      return `${count} document${count === 1 ? "" : "s"} retrieved`;
    }
    return `Searching ${event.search_query}`;
  }
  if (stage === "planner") {
    return event.decision || "Classified as research + analytics task";
  }
  if (stage === "rag" && (event.decision === "rewrite" || event.action.includes("insufficient"))) {
    return "Evidence insufficient";
  }
  if (stage === "analyst") {
    return "Dataset analyzed";
  }
  if (stage === "risk") {
    if (event.tool === "ml_regression" || event.decision === "score_regression") {
      return "Regression model selected";
    }
    return "Classification model selected";
  }
  if (stage === "integrity") {
    return "Transaction consistency verified";
  }
  if (stage === "critic") {
    return event.verification_status === "passed" || event.decision === "accept"
      ? "Findings verified"
      : event.decision || "Findings reviewed";
  }
  if (stage === "writer") {
    return "Final report generated";
  }
  return event.decision || event.action.replaceAll("_", " ");
}

export function linesFromTrace(events: TraceEvent[], question?: string): RunLogLine[] {
  const lines: RunLogLine[] = [];
  if (question) {
    lines.push({
      at: clock(events[0]?.timestamp),
      agent: "Query received",
      detail: question,
      node: "query",
    });
  }
  for (const event of events) {
    const stage = stageForEvent(event);
    const evidence =
      event.node === "sufficiency" ||
      event.action.includes("insufficient") ||
      event.decision === "rewrite";
    lines.push({
      at: clock(event.timestamp),
      agent: evidence && stage === "rag" ? "Evidence evaluator" : stageLabel(stage),
      detail: detailFor(event, stage),
      node: evidence && stage === "rag" ? "evidence" : stage ?? "query",
    });
  }
  return lines;
}

export function lightingFromLines(lines: RunLogLine[], cursor: number): {
  active: GraphId[];
  complete: GraphId[];
} {
  const visible = lines.slice(0, Math.max(0, cursor));
  const current = visible[visible.length - 1];
  const complete = visible
    .slice(0, -1)
    .map((line) => line.node)
    .filter((node) => node !== "query");
  return {
    active: current && current.node !== "query" ? [current.node] : [],
    complete,
  };
}
