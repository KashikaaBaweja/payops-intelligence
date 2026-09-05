"use client";

import { useEffect, useState } from "react";
import { ErrorState, LoadingState } from "../../../../components/states/PageState";
import { getAdminSettings } from "../../../../lib/auth";
import { dash } from "../../../../lib/adminNav";
import { ApiError } from "../../../../lib/types";

export default function AdminSettingsPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof getAdminSettings>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAdminSettings()
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load settings."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <h1 className="page-title">Settings</h1>
      <p className="page-lead">Non-secret runtime configuration. SMTP credentials are never returned.</p>
      {loading ? <LoadingState label="Reading admin settings…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      {data ? (
        <section className="panel">
          <div className="panel-hd">Runtime</div>
          <div className="panel-bd">
            <dl className="kv">
              <dt>Environment</dt>
              <dd>{dash(data.environment)}</dd>
              <dt>Vector backend</dt>
              <dd>{dash(data.vector_backend)}</dd>
              <dt>LLM provider</dt>
              <dd>{dash(data.llm_provider)}</dd>
              <dt>Session TTL</dt>
              <dd>{dash(data.session_ttl_hours)} hours</dd>
              <dt>SMTP</dt>
              <dd>{data.smtp_configured ? "Configured" : "Not configured"}</dd>
              <dt>Public URL</dt>
              <dd>{dash(data.public_app_url)}</dd>
            </dl>
          </div>
        </section>
      ) : null}
    </>
  );
}
