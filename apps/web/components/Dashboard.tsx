"use client";

import { useEffect, useMemo, useState } from "react";
import {
  createInvestigation,
  getApiHealth,
  getEvidence,
  getMerchantHealth,
  getMerchantMetrics,
  getTrace,
} from "../lib/api";
import {
  MERCHANTS,
  SAMPLE_QUESTIONS,
  formatMetricValue,
  formatPercent,
  formatTime,
  merchantFromQuestion,
  shortId,
} from "../lib/format";
import { TracePipeline } from "./TracePipeline";
import { ApiError } from "../lib/types";
import type {
  EvidenceItem,
  IncidentReport,
  InvestigationResponse,
  MerchantHealthScore,
  MerchantMetricsResponse,
  MetricResult,
  TraceEvent,
} from "../lib/types";
import { stageLabel, stageStates } from "../lib/trace";

type ViewState = "idle" | "running" | "ready" | "failed";

export function Dashboard() {
  const [question, setQuestion] = useState<string>(SAMPLE_QUESTIONS[0].question);
  const [merchantId, setMerchantId] = useState<string>("M102");
  const [view, setView] = useState<ViewState>("idle");
  const [error, setError] = useState<{ message: string; requestId?: string } | null>(null);
  const [investigation, setInvestigation] = useState<InvestigationResponse | null>(null);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [metrics, setMetrics] = useState<MetricResult[]>([]);
  const [health, setHealth] = useState<MerchantHealthScore | null>(null);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [environment, setEnvironment] = useState("local");

  useEffect(() => {
    let cancelled = false;
    async function ping() {
      try {
        const body = await getApiHealth();
        if (!cancelled) {
          setApiOk(true);
          setEnvironment(body.environment);
        }
      } catch {
        if (!cancelled) {
          setApiOk(false);
        }
      }
    }
    ping();
    const timer = window.setInterval(ping, 4000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const report: IncidentReport | null = investigation?.report ?? null;
  const { states, current } = useMemo(
    () => stageStates(events, view === "running"),
    [events, view],
  );

  async function runInvestigation() {
    const trimmed = question.trim();
    if (trimmed.length < 3) {
      setError({ message: "Enter an investigation question (at least 3 characters)." });
      return;
    }
    setView("running");
    setError(null);
    setInvestigation(null);
    setEvents([]);
    setEvidence([]);
    setMetrics([]);
    setHealth(null);
    try {
      const created = await createInvestigation({
        question: trimmed,
        merchant_id: merchantId || null,
      });
      setInvestigation(created);
      const trace = created.investigation_id
        ? await getTrace(created.investigation_id).catch(() => ({
            events: created.report?.agent_execution_summary ?? [],
          }))
        : { events: created.report?.agent_execution_summary ?? [] };
      setEvents(trace.events?.length ? trace.events : created.report?.agent_execution_summary ?? []);
      const refs = created.report?.evidence ?? [];
      const loaded = await Promise.all(
        refs.map(async (ref) => {
          try {
            return await getEvidence(ref.evidence_id);
          } catch {
            return {
              evidence_id: ref.evidence_id,
              source: (ref.source as EvidenceItem["source"]) || "doc",
              doc_id: null,
              section: ref.label,
              chunk_id: null,
              score: null,
              text_snippet: "",
              metadata: {},
            } satisfies EvidenceItem;
          }
        }),
      );
      setEvidence(loaded);
      const merchant = created.report?.merchant_id || merchantId || merchantFromQuestion(trimmed);
      const reportMetrics = created.report?.observed_metrics ?? [];
      setMetrics(reportMetrics);
      if (merchant) {
        const extra: MerchantMetricsResponse | null = await getMerchantMetrics(merchant).catch(
          () => null,
        );
        if (extra?.metrics?.length) {
          setMetrics(extra.metrics);
        }
        const score = await getMerchantHealth(merchant).catch(() => null);
        setHealth(score);
      }
      setView(created.status === "failed" ? "failed" : "ready");
    } catch (err) {
      const apiError = err instanceof ApiError ? err : null;
      setView("failed");
      setError({
        message:
          apiError?.message ||
          (err instanceof Error ? err.message : "Investigation failed."),
        requestId: apiError?.requestId,
      });
    }
  }

  const statusChip = statusFor(view, report);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">PayOps</span>
          <span className="brand-title">Investigation console</span>
        </div>
        <div className="topbar-meta">
          <span className="mono">{environment}</span>
          <span className="chip idle">
            <span className={`dot ${apiOk === true ? "ok" : apiOk === false ? "bad" : ""}`} />
            API {apiOk === true ? "connected" : apiOk === false ? "unreachable" : "checking"}
          </span>
        </div>
      </header>
      <div className="workspace">
        <aside className="rail">
          <div>
            <div className="h1">New investigation</div>
            <p className="banner">
              Synthetic ops data only. The trace shows tools and decisions, not hidden model
              reasoning.
            </p>
          </div>
          <label className="field">
            Question
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              disabled={view === "running"}
            />
          </label>
          <label className="field">
            Merchant
            <select
              value={merchantId}
              disabled={view === "running"}
              onChange={(event) => setMerchantId(event.target.value)}
            >
              <option value="">None (docs-only questions)</option>
              {MERCHANTS.map((merchant) => (
                <option key={merchant.id} value={merchant.id}>
                  {merchant.id} {merchant.name}
                </option>
              ))}
            </select>
          </label>
          <button className="btn btn-primary" disabled={view === "running"} onClick={runInvestigation}>
            {view === "running" ? "Running…" : "Run investigation"}
          </button>
          <div>
            <div className="panel-hd" style={{ padding: "0 0 8px", border: 0 }}>
              Sample incidents
            </div>
            <div className="samples">
              {SAMPLE_QUESTIONS.map((sample) => (
                <button
                  key={sample.label}
                  className="sample"
                  disabled={view === "running"}
                  onClick={() => {
                    setQuestion(sample.question);
                    setMerchantId(sample.merchant_id ?? "");
                  }}
                >
                  {sample.label}
                </button>
              ))}
            </div>
          </div>
          <div className="status-block">
            <div className="panel-hd" style={{ padding: 0, border: 0, marginBottom: 8 }}>
              Investigation status
            </div>
            <span className={`chip ${statusChip.tone}`}>{statusChip.label}</span>
            <dl className="kv" style={{ marginTop: 10 }}>
              <dt>Step</dt>
              <dd>{view === "idle" ? "Idle" : stageLabel(current)}</dd>
              <dt>Case</dt>
              <dd className="mono">
                {investigation?.investigation_id
                  ? shortId(investigation.investigation_id)
                  : "—"}
              </dd>
              <dt>Incident</dt>
              <dd className="mono">{report?.incident_id ?? "—"}</dd>
              <dt>Opened</dt>
              <dd>{investigation ? formatTime(investigation.created_at) : "—"}</dd>
            </dl>
          </div>
        </aside>
        <main className="main">
          {apiOk === false ? (
            <div className="error-box" role="alert">
              API unreachable. From the repo root:{" "}
              <span className="mono">
                source .venv/bin/activate && PYTHONPATH=packages:. uvicorn apps.api.main:app
                --reload --port 8000
              </span>
              . This page retries every few seconds.
            </div>
          ) : null}
          {error ? (
            <div className="error-box" role="alert">
              {error.message}
              {error.requestId ? (
                <div className="mono" style={{ marginTop: 6, color: "var(--faint)" }}>
                  request {error.requestId}
                </div>
              ) : null}
            </div>
          ) : null}

          <section className="panel">
            <div className="panel-hd">
              Investigation trace
              <span className="hint">Structured events only — no chain-of-thought</span>
            </div>
            <div className="panel-bd">
              <TracePipeline states={states} />
            </div>
          </section>

          <section className="panel">
            <div className="panel-hd">
              Agent execution timeline
              <span className="hint">node · action · tool · query · evidence IDs · decision</span>
            </div>
            <div className="panel-bd" style={{ padding: 0 }}>
              {view === "running" ? (
                <div className="loading-box">Orchestrator running. Trace events appear when the graph finishes.</div>
              ) : events.length === 0 ? (
                <div className="empty">No execution events yet. Run an investigation to populate the timeline.</div>
              ) : (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Node</th>
                      <th>Action</th>
                      <th>Tool</th>
                      <th>Query</th>
                      <th>Evidence</th>
                      <th>Decision</th>
                      <th>Verify</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((event, index) => (
                      <tr key={`${event.node}-${event.timestamp}-${index}`}>
                        <td className="mono">{formatTime(event.timestamp).slice(11, 19)}</td>
                        <td>{event.node}</td>
                        <td>{event.action}</td>
                        <td className="mono">{event.tool ?? "—"}</td>
                        <td>{event.search_query ?? "—"}</td>
                        <td className="mono">{event.evidence_ids.length}</td>
                        <td>{event.decision ?? "—"}</td>
                        <td>{event.verification_status ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>

          <div className="grid-2">
            <section className="panel">
              <div className="panel-hd">Retrieved evidence</div>
              <div className="panel-bd">
                {view === "running" ? (
                  <div className="loading-box">Collecting citations…</div>
                ) : evidence.length === 0 ? (
                  <div className="empty">No evidence retrieved for this case.</div>
                ) : (
                  evidence.map((item) => (
                    <article key={item.evidence_id} className="evidence-item">
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                        <span className="chip idle">{item.source}</span>
                        <span className="mono" style={{ color: "var(--faint)" }}>
                          {item.evidence_id}
                        </span>
                      </div>
                      {item.section ? (
                        <div style={{ marginTop: 6, color: "var(--muted)" }}>{item.section}</div>
                      ) : null}
                      {item.text_snippet ? <div className="snippet">{item.text_snippet}</div> : null}
                    </article>
                  ))
                )}
              </div>
            </section>
            <section className="panel">
              <div className="panel-hd">Transaction metrics</div>
              <div className="panel-bd" style={{ padding: 0 }}>
                {view === "running" ? (
                  <div className="loading-box">Querying catalog metrics…</div>
                ) : metrics.length === 0 ? (
                  <div className="empty">
                    No catalog metrics. Docs-only questions do not call the SQL gateway.
                  </div>
                ) : (
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th>Value</th>
                        <th>n</th>
                        <th>Operation</th>
                      </tr>
                    </thead>
                    <tbody>
                      {metrics.map((metric) => (
                        <tr key={`${metric.operation}-${metric.metric}`}>
                          <td>{metric.metric}</td>
                          <td className="mono">{formatMetricValue(metric)}</td>
                          <td>{metric.sample_size ?? "—"}</td>
                          <td className="mono">{metric.operation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </section>
          </div>

          <div className="grid-2">
            <section className="panel">
              <div className="panel-hd">Incident findings</div>
              <div className="panel-bd">
                {view === "running" ? (
                  <div className="loading-box">Waiting for the writer…</div>
                ) : !report ? (
                  <div className="empty">Findings appear after a completed investigation.</div>
                ) : (
                  <>
                    <p>{report.likely_cause.cause}</p>
                    {report.findings.length === 0 ? (
                      <div className="empty">Writer returned no finding lines.</div>
                    ) : (
                      report.findings.map((finding, index) => (
                        <div key={`${index}-${finding.slice(0, 24)}`} className="finding">
                          {finding}
                        </div>
                      ))
                    )}
                  </>
                )}
              </div>
            </section>
            <section className="panel">
              <div className="panel-hd">Confidence</div>
              <div className="panel-bd">
                {view === "running" ? (
                  <div className="loading-box">Verifier has not scored this case yet.</div>
                ) : !report ? (
                  <div className="empty">Confidence is produced with the final report.</div>
                ) : (
                  <>
                    <div className="score-row">
                      <div className="score">{formatPercent(report.confidence)}</div>
                      <span className={`chip ${report.evidence_sufficient ? "ok" : "warn"}`}>
                        {report.evidence_sufficient ? "Evidence sufficient" : "Insufficient evidence"}
                      </span>
                      <span className={`chip ${severityTone(report.severity)}`}>{report.severity}</span>
                    </div>
                    <dl className="kv">
                      <dt>Cause</dt>
                      <dd>{report.likely_cause.cause}</dd>
                      <dt>Category</dt>
                      <dd>{report.likely_cause.category}</dd>
                    </dl>
                  </>
                )}
              </div>
            </section>
          </div>

          <section className="panel">
            <div className="panel-hd">
              Merchant health
              <span className="hint">Deterministic score — no ML model</span>
            </div>
            <div className="panel-bd">
              {view === "running" ? (
                <div className="loading-box">Scoring merchant factors…</div>
              ) : !health ? (
                <div className="empty">
                  No merchant health for this run. Choose a merchant or ask about M102 / M201.
                </div>
              ) : (
                <>
                  <div className="score-row">
                    <div className="score">{health.score.toFixed(0)}</div>
                    <span className={`chip ${health.band === "healthy" ? "ok" : health.band === "degraded" ? "warn" : "bad"}`}>
                      {health.band}
                    </span>
                    <span className="mono" style={{ color: "var(--muted)" }}>
                      {health.merchant_id}
                    </span>
                  </div>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Factor</th>
                        <th>Value</th>
                        <th>Score</th>
                        <th>Weight</th>
                        <th>Band</th>
                      </tr>
                    </thead>
                    <tbody>
                      {health.factors.map((factor) => (
                        <tr key={factor.name}>
                          <td>{factor.name}</td>
                          <td className="mono">{factor.value.toFixed(3)}</td>
                          <td className="mono">{factor.score.toFixed(0)}</td>
                          <td className="mono">{(factor.weight * 100).toFixed(0)}%</td>
                          <td>{factor.band}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {health.penalties.length ? (
                    <div style={{ marginTop: 10, color: "var(--muted)" }}>
                      Penalties: {health.penalties.map((item) => `${item.factor} −${item.points}`).join(" · ")}
                    </div>
                  ) : (
                    <div style={{ marginTop: 10, color: "var(--ok)" }}>No penalties.</div>
                  )}
                </>
              )}
            </div>
          </section>

          <section className="panel">
            <div className="panel-hd">Final investigation report</div>
            <div className="panel-bd">
              {view === "running" ? (
                <div className="loading-box">Drafting the structured report…</div>
              ) : !report ? (
                <div className="empty">The report is empty until an investigation completes.</div>
              ) : (
                <>
                  <h2 className="h1">{report.executive_summary}</h2>
                  <dl className="kv">
                    <dt>Merchant</dt>
                    <dd>{report.merchant_id ?? "—"}</dd>
                    <dt>Window</dt>
                    <dd>
                      {report.time_window
                        ? `${formatTime(report.time_window.start)} → ${formatTime(report.time_window.end)}`
                        : "—"}
                    </dd>
                  </dl>
                  {report.recommended_actions.length ? (
                    <ul className="actions">
                      {report.recommended_actions.map((action) => (
                        <li key={action}>{action}</li>
                      ))}
                    </ul>
                  ) : null}
                  {report.alternative_hypotheses.length ? (
                    <div style={{ marginTop: 10, color: "var(--muted)" }}>
                      Alternatives:{" "}
                      {report.alternative_hypotheses.map((item) => item.cause).join(" · ")}
                    </div>
                  ) : null}
                </>
              )}
            </div>
          </section>

          <section className="panel">
            <div className="panel-hd">Source references</div>
            <div className="panel-bd" style={{ padding: 0 }}>
              {view === "running" ? (
                <div className="loading-box">Resolving citations…</div>
              ) : !report?.sources?.length && !report?.evidence?.length ? (
                <div className="empty">No source references yet.</div>
              ) : (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Evidence ID</th>
                      <th>Source</th>
                      <th>Label</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(report?.sources?.length ? report.sources : report?.evidence ?? []).map((ref) => (
                      <tr key={ref.evidence_id}>
                        <td className="mono">{ref.evidence_id}</td>
                        <td>{ref.source}</td>
                        <td>{ref.label}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

function statusFor(
  view: ViewState,
  report: IncidentReport | null,
): { label: string; tone: string } {
  if (view === "running") {
    return { label: "Investigating", tone: "run" };
  }
  if (view === "failed") {
    return { label: "Failed", tone: "bad" };
  }
  if (view === "idle") {
    return { label: "Idle", tone: "idle" };
  }
  if (report && !report.evidence_sufficient) {
    return { label: "Completed · insufficient evidence", tone: "warn" };
  }
  return { label: "Completed", tone: "ok" };
}

function severityTone(severity: IncidentReport["severity"]): string {
  if (severity === "critical" || severity === "high") {
    return "bad";
  }
  if (severity === "medium") {
    return "warn";
  }
  return "ok";
}
