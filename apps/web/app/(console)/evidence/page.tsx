"use client";

import { useEffect, useState } from "react";
import { EvidenceList } from "../../../components/EvidenceList";
import { EmptyState, ErrorState, LoadingState } from "../../../components/states/PageState";
import { getEvidence, getInvestigation } from "../../../lib/api";
import { lastInvestigationId } from "../../../lib/session";
import type { EvidenceItem } from "../../../lib/types";
import { ApiError } from "../../../lib/types";

export default function EvidencePage() {
  const [items, setItems] = useState<EvidenceItem[]>([]);
  const [question, setQuestion] = useState("");
  const [opened, setOpened] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const id = lastInvestigationId();
    if (!id) {
      setLoading(false);
      return;
    }
    getInvestigation(id)
      .then(async (inv) => {
        setQuestion(inv.question);
        setOpened(inv.created_at);
        const refs = inv.report?.evidence ?? [];
        const loaded = await Promise.all(
          refs.map(async (ref) => {
            try {
              return await getEvidence(ref.evidence_id);
            } catch {
              return {
                evidence_id: ref.evidence_id,
                source: (ref.source as EvidenceItem["source"]) || "doc",
                doc_id: null,
                section: ref.label,
                chunk_id: null,
                score: null,
                text_snippet: "",
                metadata: {},
              } satisfies EvidenceItem;
            }
          }),
        );
        setItems(loaded);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Evidence unavailable."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <h1 className="page-title">Evidence</h1>
      <p className="page-lead">
        Retrieved passages for the last research run. Each card is a citation the critic can
        check — source, document, passage, score, and time.
      </p>
      {loading ? <LoadingState label="Resolving citations…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      {!loading && !question ? (
        <EmptyState
          title="No evidence in this browser"
          detail="Run a research question first. Retrieval writes evidence IDs the writer must cite."
        />
      ) : null}
      {question ? (
        <section className="panel">
          <div className="panel-hd">
            Last question
            <span className="hint">{question}</span>
          </div>
          <div className="panel-bd">
            <EvidenceList items={items} fallbackTime={opened} />
          </div>
        </section>
      ) : null}
    </>
  );
}
