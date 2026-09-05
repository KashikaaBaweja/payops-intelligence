"use client";

import { useEffect, useState } from "react";
import { AcidTrack } from "./AcidTrack";
import { getLedgerAccounts, postLedgerTransfer } from "../lib/api";
import type { LedgerAccountView, TransferResult } from "../lib/types";

const FAIL_OPTIONS = [
  { value: "", label: "No injected failure (COMMIT)" },
  { value: "after_debit", label: "Fail after debit → ROLLBACK" },
  { value: "after_credit", label: "Fail after credit → ROLLBACK" },
  { value: "after_ledger", label: "Fail after ledger update → ROLLBACK" },
  { value: "before_commit", label: "Fail before commit → ROLLBACK" },
] as const;

function rupees(cents: number): string {
  return `INR ${(cents / 100).toFixed(2)}`;
}

export function LedgerPanel({ onComplete }: { onComplete?: (result: TransferResult) => void }) {
  const [accounts, setAccounts] = useState<LedgerAccountView[]>([]);
  const [isolation, setIsolation] = useState("");
  const [reason, setReason] = useState("");
  const [fromId, setFromId] = useState("M102-wallet");
  const [toId, setToId] = useState("M201-wallet");
  const [amount, setAmount] = useState("100");
  const [failAt, setFailAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TransferResult | null>(null);

  async function refreshAccounts() {
    const body = await getLedgerAccounts();
    setAccounts(body.accounts);
    setIsolation(body.isolation_level);
    setReason(body.isolation_reason);
  }

  useEffect(() => {
    refreshAccounts().catch(() => {
      setError("Ledger accounts are unavailable until the API is reachable.");
    });
  }, []);

  return (
    <section className="panel">
      <div className="panel-hd">
        Ledger transfer
        <span className="hint">Live database transaction — not a static ACID page</span>
      </div>
      <div className="panel-bd">
        <p className="banner">
          Live SQL transaction. Isolation: {isolation || "—"}. Injected failure rolls the
          same transaction back — balances do not change.
        </p>
        {reason ? <p className="banner">{reason}</p> : null}
        <AcidTrack result={result} />
        <div className="field">
          From account
          <select value={fromId} onChange={(event) => setFromId(event.target.value)}>
            {accounts.map((account) => (
              <option key={account.account_id} value={account.account_id}>
                {account.account_id} · {rupees(account.balance_cents)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          To account
          <select value={toId} onChange={(event) => setToId(event.target.value)}>
            {accounts.map((account) => (
              <option key={`to-${account.account_id}`} value={account.account_id}>
                {account.account_id} · {rupees(account.balance_cents)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          Amount (INR rupees)
          <input value={amount} onChange={(event) => setAmount(event.target.value)} inputMode="decimal" />
        </div>
        <label className="field">
          Failure point
          <select value={failAt} onChange={(event) => setFailAt(event.target.value)}>
            {FAIL_OPTIONS.map((option) => (
              <option key={option.value || "none"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <button
          className="btn"
          disabled={busy}
          onClick={async () => {
            const rupeesValue = Number(amount);
            if (!Number.isFinite(rupeesValue) || rupeesValue <= 0) {
              return;
            }
            setBusy(true);
            setError(null);
            try {
              const scored = await postLedgerTransfer({
                from_account_id: fromId,
                to_account_id: toId,
                amount_cents: Math.round(rupeesValue * 100),
                fail_at: failAt
                  ? (failAt as "after_debit" | "after_credit" | "after_ledger" | "before_commit")
                  : null,
              });
              setResult(scored);
              onComplete?.(scored);
              await refreshAccounts();
            } catch (err) {
              setResult(null);
              setError(err instanceof Error ? err.message : "Transfer failed.");
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Running transaction…" : "Run debit / credit / ledger"}
        </button>
        {error ? <p className="banner">{error}</p> : null}
        {!result ? (
          <div className="empty" style={{ marginTop: 12 }}>
            Run a transfer to see commit or rollback against the database.
          </div>
        ) : (
          <>
            <dl className="kv" style={{ marginTop: 12 }}>
              <dt>Transaction ID</dt>
              <dd className="mono">{result.transfer_id}</dd>
              <dt>Current state</dt>
              <dd>
                <span className={`chip ${result.status === "committed" ? "ok" : "warn"}`}>
                  {result.current_state}
                </span>
              </dd>
              <dt>Commit / Rollback</dt>
              <dd className="mono">{result.commit_or_rollback}</dd>
              <dt>Failure point</dt>
              <dd className="mono">{result.failure_point ?? "none"}</dd>
              <dt>Before balance</dt>
              <dd className="mono">
                {result.from_account_id} {rupees(result.before_balance.from)} →{" "}
                {result.to_account_id} {rupees(result.before_balance.to)}
              </dd>
              <dt>After balance</dt>
              <dd className="mono">
                {result.from_account_id} {rupees(result.after_balance.from)} →{" "}
                {result.to_account_id} {rupees(result.after_balance.to)}
              </dd>
            </dl>
            <table className="table" style={{ marginTop: 12 }}>
              <thead>
                <tr>
                  <th>Operation</th>
                  <th>State</th>
                  <th>Delta</th>
                </tr>
              </thead>
              <tbody>
                {result.operations.map((item, index) => (
                  <tr key={`${item.name}-${index}`}>
                    <td>{item.name}</td>
                    <td className="mono">{item.state}</td>
                    <td className="mono">
                      {item.delta_cents == null ? "—" : rupees(item.delta_cents)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ marginTop: 10, color: "var(--muted)" }}>
              Audit:{" "}
              {result.audit_events.length
                ? result.audit_events.map((event) => event.event).join(" → ")
                : "—"}
            </div>
            <p className="banner">{result.notes}</p>
          </>
        )}
      </div>
    </section>
  );
}
