"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "../../../components/states/PageState";
import {
  getSystemHealth,
  listDocuments,
  listInvestigations,
  listTransfers,
} from "../../../lib/api";
import { ApiError } from "../../../lib/types";
import type { InvestigationSummary } from "../../../lib/types";

export default function OverviewPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<InvestigationSummary[]>([]);
  const [totalRuns, setTotalRuns] = useState(0);
  const [docs, setDocs] = useState(0);
  const [transfers, setTransfers] = useState(0);
  const [pulse, setPulse] = useState("—");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [investigations, corpus, ledger, health] = await Promise.all([
          listInvestigations(),
          listDocuments(),
          listTransfers(),
          getSystemHealth(),
        ]);
        if (cancelled) {
          return;
        }
        setRuns(investigations.items);
        setTotalRuns(investigations.total);
        setDocs(corpus.documents.length);
        setTransfers(ledger.length);
        setPulse(health.status);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Could not load overview.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const completed = runs.filter((item) => item.status === "completed").length;
  const success = runs.length ? Math.round((completed / runs.length) * 100) : 0;

  return (
    <>
      <div>
        <h1 className="page-title">Overview</h1>
        <p className="page-lead">
          Live counts from the PayIntel API: investigation store, corpus on disk, and
          ledger transfers. Open the ML lab for holdout scores. System pulse is {pulse}.
        </p>
      </div>
      {loading ? <LoadingState label="Loading console metrics…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      {!loading && !error ? (
        <div className="stat-grid">
          <Link href="/reports" className="stat-card">
            <span>Research runs</span>
            <strong>{totalRuns}</strong>
          </Link>
          <Link href="/documents" className="stat-card">
            <span>Documents indexed</span>
            <strong>{docs}</strong>
          </Link>
          <Link href="/agents" className="stat-card">
            <span>Agent success rate</span>
            <strong>{runs.length ? `${success}%` : "—"}</strong>
          </Link>
          <Link href="/ml" className="stat-card">
            <span>ML lab</span>
            <strong>Open</strong>
          </Link>
          <Link href="/transactions" className="stat-card">
            <span>Transactions analyzed</span>
            <strong>{transfers}</strong>
          </Link>
        </div>
      ) : null}
      <section className="panel">
        <div className="panel-hd">Recent research</div>
        <div className="panel-bd">
          {!runs.length && !loading ? (
            <EmptyState
              title="No investigations yet"
              detail="Start from Research with a merchant question such as Harbor Retail GATEWAY_TIMEOUT."
            />
          ) : (
            <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Question</th>
                  <th>Status</th>
                  <th>Merchant</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((item) => (
                  <tr key={item.investigation_id}>
                    <td>
                      <Link href={`/reports/${item.investigation_id}`}>{item.question}</Link>
                    </td>
                    <td>{item.status}</td>
                    <td className="mono">{item.merchant_id ?? "—"}</td>
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
