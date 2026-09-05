"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "../../../components/states/PageState";
import { listInvestigations } from "../../../lib/api";
import { formatTime } from "../../../lib/format";
import type { InvestigationSummary } from "../../../lib/types";
import { ApiError } from "../../../lib/types";

export default function ReportsPage() {
  const [items, setItems] = useState<InvestigationSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listInvestigations()
      .then((body) => setItems(body.items))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Store unavailable."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <h1 className="page-title">Reports</h1>
      <p className="page-lead">Structured investigation reports from the durable audit store.</p>
      {loading ? <LoadingState label="Loading reports…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      <section className="panel">
        <div className="panel-hd">Investigation archive</div>
        <div className="panel-bd">
          {!items.length && !loading ? (
            <EmptyState title="No reports" detail="Complete a research run to persist a report." />
          ) : (
            <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Question</th>
                  <th>Confidence</th>
                  <th>Opened</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.investigation_id}>
                    <td>
                      <Link href={`/reports/${item.investigation_id}`}>{item.question}</Link>
                    </td>
                    <td className="mono">
                      {item.confidence == null ? "—" : item.confidence.toFixed(2)}
                    </td>
                    <td>{formatTime(item.created_at)}</td>
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
