import type { RunLogLine } from "../../lib/runLog";

export function AgentRunLog({
  lines,
  cursor,
}: {
  lines: RunLogLine[];
  cursor: number;
}) {
  const visible = lines.slice(0, Math.max(0, cursor));
  if (!visible.length) {
    return (
      <div className="empty">
        Execution log is empty until the orchestrator accepts a research question.
      </div>
    );
  }
  return (
    <ol className="run-log" aria-label="Agent execution log" aria-live="polite">
      {visible.map((line, index) => {
        const current = index === visible.length - 1;
        return (
          <li key={`${line.at}-${line.agent}-${index}`} className={current ? "is-current" : ""}>
            <time dateTime={line.at} className="mono">
              {line.at}
            </time>
            <div>
              <strong>{line.agent}</strong>
              {line.detail ? <span>→ {line.detail}</span> : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
