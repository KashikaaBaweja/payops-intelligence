"use client";

import { useEffect, useState } from "react";
import { ErrorState, LoadingState } from "../../../../components/states/PageState";
import { getAdminMl } from "../../../../lib/auth";
import { dash } from "../../../../lib/adminNav";
import { ApiError } from "../../../../lib/types";

export default function AdminMlPage() {
  const [rows, setRows] = useState<Awaited<ReturnType<typeof getAdminMl>>>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAdminMl()
      .then(setRows)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load models."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <h1 className="page-title">ML Models</h1>
      <p className="page-lead">Holdout metrics from the live trainer. Missing scores stay blank.</p>
      {loading ? <LoadingState label="Fitting holdout views…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      {rows.map((item) => (
        <section className="panel" key={item.model_name}>
          <div className="panel-hd">{item.model_name}</div>
          <div className="panel-bd">
            <dl className="kv">
              <dt>Task</dt>
              <dd>{item.task}</dd>
              <dt>Version</dt>
              <dd>{dash(item.version)}</dd>
              <dt>Dataset</dt>
              <dd>{dash(item.dataset_version)}</dd>
              <dt>Last trained</dt>
              <dd>{item.last_trained ? new Date(item.last_trained).toLocaleString() : "—"}</dd>
            </dl>
            {Object.keys(item.metrics).length ? (
              <dl className="kv" style={{ marginTop: 12 }}>
                {Object.entries(item.metrics).map(([key, value]) => (
                  <div key={key} style={{ display: "contents" }}>
                    <dt>{key}</dt>
                    <dd>{String(value)}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="page-lead">No data available</p>
            )}
            {item.notes ? <p className="banner">{item.notes}</p> : null}
          </div>
        </section>
      ))}
    </>
  );
}
