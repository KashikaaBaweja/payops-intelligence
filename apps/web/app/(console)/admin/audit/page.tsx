"use client";

import { useEffect, useState } from "react";
import { ErrorState, LoadingState } from "../../../../components/states/PageState";
import { getAdminAudit } from "../../../../lib/auth";
import { dash } from "../../../../lib/adminNav";
import { ApiError } from "../../../../lib/types";

export default function AdminAuditPage() {
  const [rows, setRows] = useState<Awaited<ReturnType<typeof getAdminAudit>>["items"]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAdminAudit()
      .then((body) => setRows(body.items))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load audit log."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <h1 className="page-title">Audit Logs</h1>
      <p className="page-lead">Security-sensitive actions. Passwords and tokens are never stored here.</p>
      {loading ? <LoadingState label="Loading audit events…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Event</th>
              <th>Actor</th>
              <th>Resource</th>
              <th>Metadata</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.event_id}>
                <td>{new Date(item.timestamp).toLocaleString()}</td>
                <td>{item.event_type}</td>
                <td>{dash(item.actor_id)}</td>
                <td>{dash(item.resource_id)}</td>
                <td className="mono">{JSON.stringify(item.metadata)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
