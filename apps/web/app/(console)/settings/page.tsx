"use client";

import { useEffect, useState } from "react";
import { ErrorState, LoadingState } from "../../../components/states/PageState";
import { getApiHealth } from "../../../lib/api";
import { ApiError } from "../../../lib/types";

export default function SettingsPage() {
  const [env, setEnv] = useState("");
  const [version, setVersion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getApiHealth()
      .then((body) => {
        setEnv(body.environment);
        setVersion(body.version || "0.1.0");
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "API unreachable."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <h1 className="page-title">Settings</h1>
      <p className="page-lead">
        Local operator profile. PayIntel demo mode does not collect accounts or API keys.
      </p>
      {loading ? <LoadingState label="Reading runtime config…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      <section className="panel">
        <div className="panel-hd">Operator</div>
        <div className="panel-bd">
          <dl className="kv">
            <dt>Profile</dt>
            <dd>Local operator</dd>
            <dt>Environment</dt>
            <dd className="mono">{env || "—"}</dd>
            <dt>API version</dt>
            <dd className="mono">{version || "—"}</dd>
            <dt>Auth</dt>
            <dd>None in local demo</dd>
          </dl>
        </div>
      </section>
    </>
  );
}
