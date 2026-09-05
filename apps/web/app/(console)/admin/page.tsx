"use client";

import { useEffect, useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "../../../components/states/PageState";
import { getAdminOverview } from "../../../lib/auth";
import { dash } from "../../../lib/adminNav";
import { ApiError } from "../../../lib/types";

export default function AdminOverviewPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof getAdminOverview>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAdminOverview()
      .then(setData)
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Could not load admin overview.");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <h1 className="page-title">Admin Console</h1>
      <p className="page-lead">Monitor PayIntel AI infrastructure and activity.</p>
      {loading ? <LoadingState label="Loading infrastructure metrics…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      {data ? (
        <div className="stat-grid">
          <article className="stat-card">
            <span>Total Users</span>
            <strong>{dash(data.total_users)}</strong>
          </article>
          <article className="stat-card">
            <span>Active Users</span>
            <strong>{dash(data.active_users)}</strong>
          </article>
          <article className="stat-card">
            <span>Research Runs</span>
            <strong>{dash(data.research_runs)}</strong>
          </article>
          <article className="stat-card">
            <span>Documents Indexed</span>
            <strong>{dash(data.documents_indexed)}</strong>
          </article>
          <article className="stat-card">
            <span>Transactions Analyzed</span>
            <strong>{dash(data.transactions_analyzed)}</strong>
          </article>
          <article className="stat-card">
            <span>Agent Success Rate</span>
            <strong>
              {data.agent_success_rate == null ? "—" : `${Math.round(data.agent_success_rate * 100)}%`}
            </strong>
          </article>
          <article className="stat-card">
            <span>System Health</span>
            <strong>{dash(data.system_health)}</strong>
          </article>
        </div>
      ) : null}
      {!loading && !error && !data ? (
        <EmptyState title="No data available" detail="The admin overview did not return metrics." />
      ) : null}
    </>
  );
}
