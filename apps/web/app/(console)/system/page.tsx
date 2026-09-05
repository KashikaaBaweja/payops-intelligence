"use client";

import { useEffect, useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "../../../components/states/PageState";
import { getSystemHealth } from "../../../lib/api";
import type { ServiceStatus, SystemHealthResponse } from "../../../lib/types";
import { ApiError } from "../../../lib/types";

const LABELS: Record<string, string> = {
  api: "API health",
  database: "Database",
  vector_db: "Vector DB",
  llm: "LLM",
  agents: "Agents",
  ml: "ML service",
};

function tone(status: ServiceStatus["status"]): string {
  if (status === "ok") {
    return "ok";
  }
  if (status === "disabled") {
    return "idle";
  }
  if (status === "degraded") {
    return "warn";
  }
  return "bad";
}

export default function SystemPage() {
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const body = await getSystemHealth();
        if (!cancelled) {
          setHealth(body);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Health endpoint unreachable.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    load();
    const timer = window.setInterval(load, 8000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <>
      <h1 className="page-title">System health</h1>
      <p className="page-lead">
        Status comes from GET /health/services on each refresh. LLM is reported disabled in
        demo mode because there is no model client.
      </p>
      {loading ? <LoadingState label="Pinging services…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      {health ? (
        <>
          <p>
            <span className={`chip ${tone(health.status)}`}>{health.status}</span>{" "}
            <span className="mono faint">
              {health.environment} · {health.version}
            </span>
          </p>
          <div className="stat-grid">
            {health.services.map((service) => (
              <article className="stat-card" key={service.name}>
                <span>{LABELS[service.name] ?? service.name.replaceAll("_", " ")}</span>
                <strong>
                  <span className={`chip ${tone(service.status)}`}>{service.status}</span>
                </strong>
                <div className="banner">{service.detail}</div>
              </article>
            ))}
          </div>
        </>
      ) : null}
      {!loading && !health && !error ? (
        <EmptyState title="No health payload" detail="The API did not return service rows." />
      ) : null}
    </>
  );
}
