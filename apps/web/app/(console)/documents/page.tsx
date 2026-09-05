"use client";

import { useEffect, useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "../../../components/states/PageState";
import { listDocuments } from "../../../lib/api";
import type { CorpusDocument } from "../../../lib/types";
import { ApiError } from "../../../lib/types";

export default function DocumentsPage() {
  const [docs, setDocs] = useState<CorpusDocument[]>([]);
  const [backend, setBackend] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listDocuments()
      .then((body) => {
        setDocs(body.documents);
        setBackend(body.backend);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Corpus unavailable."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <h1 className="page-title">Documents</h1>
      <p className="page-lead">
        Files in the research corpus. Retrieval uses a hashing bag-of-words store
        ({backend || "unknown"} backend), not a hosted vector vendor.
      </p>
      {loading ? <LoadingState label="Reading corpus…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      <section className="panel">
        <div className="panel-hd">Indexed sources</div>
        <div className="panel-bd">
          {!docs.length && !loading ? (
            <EmptyState title="No corpus files" detail="Place markdown or JSON under docs/corpus." />
          ) : (
            <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Kind</th>
                  <th>Bytes</th>
                </tr>
              </thead>
              <tbody>
                {docs.map((item) => (
                  <tr key={item.document_id}>
                    <td>{item.name}</td>
                    <td>{item.kind}</td>
                    <td className="mono">{item.bytes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </div>
      </section>
    </>
  );
}
