"use client";

import { useEffect, useState } from "react";
import { ErrorState, LoadingState } from "../../../../components/states/PageState";
import { getAdminDocuments } from "../../../../lib/auth";
import { ApiError } from "../../../../lib/types";

export default function AdminDocumentsPage() {
  const [docs, setDocs] = useState<Array<{ document_id: string; name: string; bytes: number }>>([]);
  const [backend, setBackend] = useState("—");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAdminDocuments()
      .then((body) => {
        setDocs(body.documents);
        setBackend(body.backend);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load documents."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <h1 className="page-title">Documents</h1>
      <p className="page-lead">Indexed corpus on disk. Retrieval backend: {backend}.</p>
      {loading ? <LoadingState label="Reading corpus…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Bytes</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((item) => (
              <tr key={item.document_id}>
                <td>{item.name}</td>
                <td>{item.bytes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
