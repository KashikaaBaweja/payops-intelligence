"use client";

import { useEffect, useState } from "react";
import { ErrorState, LoadingState } from "../../../../components/states/PageState";
import { getAdminAgents } from "../../../../lib/auth";
import { dash } from "../../../../lib/adminNav";
import { ApiError } from "../../../../lib/types";

export default function AdminAgentsPage() {
  const [rows, setRows] = useState<Awaited<ReturnType<typeof getAdminAgents>>>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAdminAgents()
      .then(setRows)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load agents."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <h1 className="page-title">Agents</h1>
      <p className="page-lead">Telemetry from stored investigation traces. Unused stages stay empty.</p>
      {loading ? <LoadingState label="Aggregating agent traces…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Agent</th>
              <th>Status</th>
              <th>Runs</th>
              <th>Success Rate</th>
              <th>Average Duration</th>
              <th>Last Run</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.agent}>
                <td>{item.agent}</td>
                <td>{dash(item.status)}</td>
                <td>{dash(item.runs)}</td>
                <td>{item.success_rate == null ? "—" : `${Math.round(item.success_rate * 100)}%`}</td>
                <td>{item.average_duration_ms == null ? "—" : `${item.average_duration_ms} ms`}</td>
                <td>{item.last_run ? new Date(item.last_run).toLocaleString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
