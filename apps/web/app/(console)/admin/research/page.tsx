"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ErrorState, LoadingState } from "../../../../components/states/PageState";
import { getAdminResearch } from "../../../../lib/auth";
import { dash } from "../../../../lib/adminNav";
import { ApiError } from "../../../../lib/types";

export default function AdminResearchPage() {
  const [rows, setRows] = useState<Awaited<ReturnType<typeof getAdminResearch>>["items"]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAdminResearch()
      .then((body) => {
        setRows(body.items);
        setTotal(body.total);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load runs."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <h1 className="page-title">Research Runs</h1>
      <p className="page-lead">Persisted investigations. Total {dash(total)}.</p>
      {loading ? <LoadingState label="Loading research runs…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Question</th>
              <th>Status</th>
              <th>Method</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.investigation_id}>
                <td>
                  <Link href={`/reports/${item.investigation_id}`}>{item.question}</Link>
                </td>
                <td>{item.status}</td>
                <td>{item.input_method}</td>
                <td>{item.duration_ms == null ? "—" : `${item.duration_ms} ms`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
