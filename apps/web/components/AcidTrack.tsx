import type { TransferOperation, TransferResult } from "../lib/types";

const IDLE_STEPS = [
  { name: "BEGIN", kind: "begin" },
  { name: "Operation 1", kind: "op" },
  { name: "Operation 2", kind: "op" },
  { name: "Operation 3", kind: "op" },
  { name: "COMMIT", kind: "commit" },
] as const;

function labelFor(name: string, index: number): string {
  if (name === "BEGIN") {
    return "BEGIN";
  }
  if (name === "COMMIT") {
    return "COMMIT";
  }
  if (name === "ROLLBACK") {
    return "ROLLBACK";
  }
  if (name === "FAILURE" || name.toLowerCase().includes("fail")) {
    return "FAILURE";
  }
  return `Operation ${index}`;
}

function visualSteps(result: TransferResult | null): { name: string; state: string }[] {
  if (!result) {
    return IDLE_STEPS.map((step) => ({ name: step.name, state: "pending" }));
  }
  const ops = result.operations.filter((item) => item.name !== "FAILURE");
  const failed = result.commit_or_rollback === "ROLLBACK";
  const steps: { name: string; state: string }[] = [];
  let opIndex = 0;
  for (const item of ops) {
    if (item.name === "BEGIN") {
      steps.push({ name: "BEGIN", state: item.state });
      continue;
    }
    if (item.name === "COMMIT") {
      steps.push({ name: "COMMIT", state: item.state });
      continue;
    }
    if (item.name === "ROLLBACK") {
      if (!steps.some((step) => step.name === "FAILURE")) {
        steps.push({ name: "FAILURE", state: "rolled_back" });
      }
      steps.push({ name: "ROLLBACK", state: item.state });
      continue;
    }
    opIndex += 1;
    steps.push({
      name: labelFor(item.name, opIndex),
      state: item.state,
    });
  }
  if (failed && !steps.some((step) => step.name === "ROLLBACK")) {
    steps.push({ name: "FAILURE", state: "rolled_back" });
    steps.push({ name: "ROLLBACK", state: "rolled_back" });
  }
  return steps;
}

function tone(name: string, state: string): string {
  if (name === "FAILURE" || name === "ROLLBACK" || state === "rolled_back") {
    return "fail";
  }
  if (state === "pending") {
    return "pending";
  }
  return "done";
}

export function AcidTrack({
  result,
  operations,
}: {
  result?: TransferResult | null;
  operations?: TransferOperation[];
}) {
  const source =
    result ??
    (operations
      ? ({
          operations,
          commit_or_rollback: operations.some((item) => item.name === "ROLLBACK")
            ? "ROLLBACK"
            : "COMMIT",
        } as TransferResult)
      : null);
  const steps = visualSteps(source);
  return (
    <ol className="acid-track" aria-label="Ledger transaction states">
      {steps.map((step, index) => (
        <li key={`${step.name}-${index}`} className="acid-node">
          {index > 0 ? (
            <span className="acid-arrow" aria-hidden>
              →
            </span>
          ) : null}
          <div className={`acid-step ${tone(step.name, step.state)}`}>
            <strong>{step.name}</strong>
            <span>{step.state === "pending" ? "idle" : step.state}</span>
          </div>
        </li>
      ))}
    </ol>
  );
}
