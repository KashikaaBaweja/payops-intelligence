import { formatDuration, formatTime } from "../../lib/format";
import type { InputMethod } from "../../lib/queryInput";

export type QueryHistoryItem = {
  investigation_id: string;
  question: string;
  input_method: InputMethod;
  status: "completed" | "failed" | "running";
  created_at: string;
  duration_ms: number | null;
};

function statusLabel(status: QueryHistoryItem["status"]): string {
  if (status === "completed") {
    return "Completed";
  }
  if (status === "failed") {
    return "Failed";
  }
  return "Running";
}

export function QueryHistory({
  items,
  busy = false,
  onDelete,
  onClear,
}: {
  items: QueryHistoryItem[];
  busy?: boolean;
  onDelete: (id: string) => void;
  onClear: () => void;
}) {
  return (
    <section className="panel" id="query-history">
      <div className="panel-hd">
        Voice Query History
        <span className="query-history-actions">
          <span className="hint">Transcripts only — microphone audio is never stored</span>
          {items.some((item) => item.status !== "running") ? (
            <button type="button" className="btn btn-ghost" disabled={busy} onClick={onClear}>
              Clear history
            </button>
          ) : null}
        </span>
      </div>
      <div className="panel-bd">
        {items.length === 0 ? (
          <div className="empty">No queries yet. Run a voice or typed investigation.</div>
        ) : (
          <ol className="query-history">
            {items.map((item) => (
              <li key={item.investigation_id} className="query-history-item">
                <div className="query-history-meta">
                  <span className="query-history-method">
                    {item.input_method === "voice" ? "🎙️ Voice" : "⌨️ Text"}
                  </span>
                  <time dateTime={item.created_at}>{formatTime(item.created_at)}</time>
                  {item.status !== "running" ? (
                    <button
                      type="button"
                      className="btn btn-ghost"
                      disabled={busy}
                      onClick={() => onDelete(item.investigation_id)}
                    >
                      Delete
                    </button>
                  ) : null}
                </div>
                <p className="query-history-transcript">“{item.question}”</p>
                <div className="query-history-status">
                  <span>{statusLabel(item.status)}</span>
                  <span className="mono">
                    {item.status === "running" ? "—" : formatDuration(item.duration_ms)}
                  </span>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
