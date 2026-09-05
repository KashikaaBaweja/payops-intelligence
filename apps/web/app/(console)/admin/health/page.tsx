"use client";

import { useEffect, useState } from "react";
import { ErrorState, LoadingState } from "../../../../components/states/PageState";
import { getAdminHealth } from "../../../../lib/auth";
import { dash } from "../../../../lib/adminNav";
import { ApiError } from "../../../../lib/types";

export default function AdminHealthPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof getAdminHealth>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAdminHealth()
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load health."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <h1 className="page-title">System Health</h1>
      <p className="page-lead">Live service probes. Overall status: {dash(data?.status)}.</p>
      {loading ? <LoadingState label="Probing services…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Service</th>
              <th>Status</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {(data?.services ?? []).map((item) => (
              <tr key={item.name}>
                <td>{item.name}</td>
                <td>{item.status}</td>
                <td>{item.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
