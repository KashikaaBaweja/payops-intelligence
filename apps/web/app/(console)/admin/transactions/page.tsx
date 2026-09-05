"use client";

import { useEffect, useState } from "react";
import { ErrorState, LoadingState } from "../../../../components/states/PageState";
import { getAdminTransaction, getAdminTransactions } from "../../../../lib/auth";
import { dash } from "../../../../lib/adminNav";
import { ApiError } from "../../../../lib/types";

export default function AdminTransactionsPage() {
  const [rows, setRows] = useState<Awaited<ReturnType<typeof getAdminTransactions>>>([]);
  const [detail, setDetail] = useState<Awaited<ReturnType<typeof getAdminTransaction>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAdminTransactions()
      .then(setRows)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load transactions."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <h1 className="page-title">Transactions</h1>
      <p className="page-lead">Live ledger transfers. Risk is shown only when a stored score exists.</p>
      {loading ? <LoadingState label="Loading transfers…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      {!loading && !error && rows.length === 0 ? (
        <p className="page-lead">No data available</p>
      ) : null}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Transaction ID</th>
              <th>Amount</th>
              <th>Status</th>
              <th>Risk Level</th>
              <th>Processing State</th>
              <th>Created At</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.transaction_id}>
                <td>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() =>
                      void getAdminTransaction(item.transaction_id)
                        .then(setDetail)
                        .catch((err) =>
                          setError(err instanceof ApiError ? err.message : "Could not load detail."),
                        )
                    }
                  >
                    {item.transaction_id}
                  </button>
                </td>
                <td>{item.amount_cents == null ? "—" : (item.amount_cents / 100).toFixed(2)}</td>
                <td>{dash(item.status)}</td>
                <td>{dash(item.risk_level)}</td>
                <td>{dash(item.processing_state)}</td>
                <td>{item.created_at ? new Date(item.created_at).toLocaleString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {detail ? (
        <section className="panel" style={{ marginTop: 20 }}>
          <div className="panel-hd">Transaction {detail.transaction_id}</div>
          <div className="panel-bd">
            <p>Validation: {dash(detail.validation)}</p>
            <p>Risk analysis: {dash(detail.risk_analysis)}</p>
            <h3>Timeline</h3>
            <pre className="mono">{detail.timeline.length ? JSON.stringify(detail.timeline, null, 2) : "—"}</pre>
            <h3>Audit events</h3>
            <pre className="mono">
              {detail.audit_events.length ? JSON.stringify(detail.audit_events, null, 2) : "—"}
            </pre>
          </div>
        </section>
      ) : null}
    </>
  );
}
