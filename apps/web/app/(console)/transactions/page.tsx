"use client";

import { useEffect, useState } from "react";
import { AcidTrack } from "../../../components/AcidTrack";
import { LedgerPanel } from "../../../components/LedgerPanel";
import { EmptyState, ErrorState, LoadingState } from "../../../components/states/PageState";
import { listTransfers } from "../../../lib/api";
import type { TransferResult } from "../../../lib/types";
import { ApiError } from "../../../lib/types";

function processingLabel(row: TransferResult): string {
  const times = row.audit_events
    .map((event) => Date.parse(event.created_at))
    .filter((value) => Number.isFinite(value));
  if (times.length < 2) {
    return row.isolation_level;
  }
  return `${Math.max(...times) - Math.min(...times)} ms`;
}

export default function TransactionsPage() {
  const [rows, setRows] = useState<TransferResult[]>([]);
  const [open, setOpen] = useState<TransferResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  function refresh() {
    listTransfers()
      .then(setRows)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Ledger list failed."))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(null);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    refresh();
  }, []);

  return (
    <>
      <h1 className="page-title">Transaction monitor</h1>
      <p className="page-lead">
        Live ledger transfers. Amounts are INR. Risk here is the transfer outcome
        (committed vs rolled back), not a fraud label.
      </p>
      {loading ? <LoadingState label="Loading ledger…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      <section className="panel">
        <div className="panel-hd">Recent transfers</div>
        <div className="panel-bd">
          {!rows.length && !loading ? (
            <EmptyState
              title="No transfers yet"
              detail="Run a debit/credit below. Failure injection rolls the same SQL transaction back."
            />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Transaction ID</th>
                    <th>Status</th>
                    <th>Amount</th>
                    <th>Risk</th>
                    <th>Processing time</th>
                    <th>Settlement status</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.transfer_id}>
                      <td>
                        <button className="btn" type="button" onClick={() => setOpen(row)}>
                          {row.transfer_id}
                        </button>
                      </td>
                      <td>{row.status}</td>
                      <td className="mono">INR {(row.amount_cents / 100).toFixed(2)}</td>
                      <td>{row.status === "rolled_back" ? "rolled back" : "cleared"}</td>
                      <td className="mono">{processingLabel(row)}</td>
                      <td>{row.commit_or_rollback}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
      <LedgerPanel
        onComplete={(result) => {
          setRows((current) => [result, ...current.filter((row) => row.transfer_id !== result.transfer_id)]);
          setOpen(result);
        }}
      />
      {open ? (
        <div
          className="drawer"
          role="dialog"
          aria-modal="true"
          aria-label="Transfer detail"
          onClick={() => setOpen(null)}
        >
          <div className="drawer-panel" onClick={(event) => event.stopPropagation()}>
            <button className="btn" type="button" onClick={() => setOpen(null)}>
              Close
            </button>
            <h2 className="h1" style={{ marginTop: 16 }}>
              {open.transfer_id}
            </h2>
            <AcidTrack result={open} />
            <dl className="kv">
              <dt>Status</dt>
              <dd>{open.current_state}</dd>
              <dt>Amount</dt>
              <dd className="mono">INR {(open.amount_cents / 100).toFixed(2)}</dd>
              <dt>From</dt>
              <dd className="mono">{open.from_account_id}</dd>
              <dt>To</dt>
              <dd className="mono">{open.to_account_id}</dd>
              <dt>Risk</dt>
              <dd>{open.status === "rolled_back" ? "rolled back" : "cleared"}</dd>
              <dt>Processing</dt>
              <dd className="mono">{processingLabel(open)}</dd>
              <dt>Settlement</dt>
              <dd>{open.commit_or_rollback}</dd>
              <dt>Failure</dt>
              <dd>{open.failure_point ?? "none"}</dd>
            </dl>
          </div>
        </div>
      ) : null}
    </>
  );
}
