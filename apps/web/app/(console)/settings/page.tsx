"use client";

import { useEffect, useState } from "react";
import { useAuth } from "../../../components/auth/AuthProvider";
import { ErrorState, LoadingState } from "../../../components/states/PageState";
import { getApiHealth } from "../../../lib/api";
import { ApiError } from "../../../lib/types";

export default function SettingsPage() {
  const { user } = useAuth();
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
      <p className="page-lead">Workspace runtime. Secrets and password hashes are never displayed.</p>
      {loading ? <LoadingState label="Reading runtime config…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      <section className="panel">
        <div className="panel-hd">Operator</div>
        <div className="panel-bd">
          <dl className="kv">
            <dt>Name</dt>
            <dd>{user?.name ?? "—"}</dd>
            <dt>Email</dt>
            <dd>{user?.email ?? "—"}</dd>
            <dt>Role</dt>
            <dd>{user?.role ?? "—"}</dd>
            <dt>Environment</dt>
            <dd className="mono">{env || "—"}</dd>
            <dt>API version</dt>
            <dd className="mono">{version || "—"}</dd>
            <dt>Auth</dt>
            <dd>HttpOnly session cookie</dd>
          </dl>
        </div>
      </section>
    </>
  );
}
