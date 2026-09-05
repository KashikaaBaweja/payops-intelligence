import { formatTime } from "../lib/format";
import type { EvidenceItem } from "../lib/types";

function citationFor(item: EvidenceItem): string {
  const doc = item.doc_id ?? item.section ?? "corpus";
  const chunk = item.chunk_id ? `#${item.chunk_id}` : "";
  return `${item.evidence_id} · ${doc}${chunk}`;
}

function timestampFor(item: EvidenceItem, fallback?: string): string {
  const meta = item.metadata || {};
  const raw = meta.timestamp ?? meta.created_at ?? meta.indexed_at ?? fallback;
  return formatTime(typeof raw === "string" ? raw : fallback);
}

export function EvidenceList({
  items,
  loading,
  fallbackTime,
}: {
  items: EvidenceItem[];
  loading?: boolean;
  fallbackTime?: string;
}) {
  if (loading) {
    return <div className="loading-box">Collecting citations…</div>;
  }
  if (!items.length) {
    return (
      <div className="empty">
        No retrieved passages for this case. Run a research question that needs runbooks or
        settlement policy.
      </div>
    );
  }
  return (
    <div className="evidence-list">
      {items.map((item) => (
        <article key={item.evidence_id} className="evidence-item">
          <div className="evidence-hd">
            <span className="chip idle">{item.source}</span>
            <span className="mono faint">{item.evidence_id}</span>
          </div>
          <dl className="kv">
            <dt>Source</dt>
            <dd>{item.source}</dd>
            <dt>Document</dt>
            <dd className="mono">{item.doc_id ?? item.section ?? "—"}</dd>
            <dt>Relevance</dt>
            <dd className="mono">{item.score == null ? "—" : item.score.toFixed(2)}</dd>
            <dt>Citation</dt>
            <dd className="mono">{citationFor(item)}</dd>
            <dt>Timestamp</dt>
            <dd className="mono">{timestampFor(item, fallbackTime)}</dd>
          </dl>
          {item.section && item.doc_id ? (
            <div className="banner">{item.section}</div>
          ) : null}
          {item.text_snippet ? (
            <div className="snippet">{item.text_snippet}</div>
          ) : (
            <div className="empty">No passage text stored for this citation.</div>
          )}
        </article>
      ))}
    </div>
  );
}
