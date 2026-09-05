"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  createInvestigation,
  deleteAllInvestigations,
  deleteInvestigation,
  getApiHealth,
  getEvidence,
  getMerchantHealth,
  getMerchantMetrics,
  getMerchantRegression,
  getMerchantRisk,
  getTrace,
  listInvestigations,
  postRiskWhatIf,
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
import { EvidenceList } from "./EvidenceList";
import { AgentGraph } from "./graph/AgentGraph";
import { LedgerPanel } from "./LedgerPanel";
import { RetrievalLoop } from "./RetrievalLoop";
import { TracePipeline } from "./TracePipeline";
import { ApiError } from "../lib/types";
import type {
  EvidenceItem,
  IncidentReport,
  InvestigationResponse,
  InvestigationSummary,
  MerchantHealthScore,
  MerchantMetricsResponse,
  MerchantRiskScore,
  MetricResult,
  RegressionScore,
  RiskWhatIfScore,
  TraceEvent,
} from "../lib/types";
import { forgetInvestigation, rememberInvestigation } from "../lib/session";
import { stageLabel, stageStates } from "../lib/trace";
import { OriginalQueryCard } from "./research/OriginalQueryCard";
import { QueryHistory, type QueryHistoryItem } from "./research/QueryHistory";
import { VoiceQueryButton } from "./research/VoiceQueryButton";
import { LANGUAGE_OPTIONS, speechRecognitionLang, type LanguageChoice } from "../lib/queryLanguage";
import { buildResearchRequest, type InputMethod } from "../lib/queryInput";

type ViewState = "idle" | "running" | "ready" | "failed";

const autoRunOnce = new Set<string>();

export function Dashboard({
  initialQuestion,
  initialInputMethod = "text",
  autoRun = false,
}: {
  initialQuestion?: string;
  initialInputMethod?: InputMethod;
  autoRun?: boolean;
}) {
  const [question, setQuestion] = useState<string>(
    initialQuestion || SAMPLE_QUESTIONS[0].question,
  );
  const [merchantId, setMerchantId] = useState<string>(
    merchantFromQuestion(initialQuestion || "") || "M102",
  );
  const [view, setView] = useState<ViewState>("idle");
  const [error, setError] = useState<{ message: string; requestId?: string } | null>(null);
  const [investigation, setInvestigation] = useState<InvestigationResponse | null>(null);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [metrics, setMetrics] = useState<MetricResult[]>([]);
  const [health, setHealth] = useState<MerchantHealthScore | null>(null);
  const [risk, setRisk] = useState<MerchantRiskScore | null>(null);
  const [regression, setRegression] = useState<RegressionScore | null>(null);
  const [whatIf, setWhatIf] = useState<RiskWhatIfScore | null>(null);
  const [whatIfAmount, setWhatIfAmount] = useState("15000");
  const [whatIfMethod, setWhatIfMethod] = useState("upi");
  const [whatIfBusy, setWhatIfBusy] = useState(false);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [environment, setEnvironment] = useState("local");
  const [inputMethod, setInputMethod] = useState<InputMethod>(initialInputMethod);
  const [language, setLanguage] = useState<LanguageChoice>("auto");
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [submittedRun, setSubmittedRun] = useState<{
    query: string;
    input_method: InputMethod;
    query_language?: string;
  } | null>(null);
  const [history, setHistory] = useState<QueryHistoryItem[]>([]);
  const [historyBusy, setHistoryBusy] = useState(false);

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

  useEffect(() => {
    let cancelled = false;
    listInvestigations()
      .then((body) => {
        if (!cancelled) {
          setHistory(body.items.map(toHistoryItem));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHistory([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const report: IncidentReport | null = investigation?.report ?? null;
  const { states, current } = useMemo(
    () => stageStates(events, view === "running"),
    [events, view],
  );

  async function runInvestigation() {
    const body = buildResearchRequest(question, inputMethod, merchantId || null, 3, language);
    if (!body) {
      setError({ message: "Enter an investigation question (at least 3 characters)." });
      return;
    }
    setSubmittedRun({
      query: body.query,
      input_method: body.input_method,
      query_language: body.language === "auto" ? undefined : body.language,
    });
    if (body.input_method === "voice") {
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      window.requestAnimationFrame(() => {
        document.getElementById("agent-execution")?.scrollIntoView({
          block: "start",
          behavior: reduce ? "auto" : "smooth",
        });
      });
    }
    setView("running");
    setError(null);
    setInvestigation(null);
    setEvents([]);
    setEvidence([]);
    setMetrics([]);
    setHealth(null);
    setRisk(null);
    setRegression(null);
    setWhatIf(null);
    try {
      const created = await createInvestigation(body);
      rememberInvestigation(created.investigation_id);
      setInvestigation(created);
      setSubmittedRun({
        query: created.question || created.original_query || body.query,
        input_method: created.input_method || body.input_method,
        query_language: created.query_language,
      });
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
      const merchant = created.report?.merchant_id || merchantId || merchantFromQuestion(body.query);
      const reportMetrics = created.report?.observed_metrics ?? [];
      setMetrics(reportMetrics);
      const runEvents = trace.events?.length
        ? trace.events
        : created.report?.agent_execution_summary ?? [];
      if (merchant) {
        if (!reportMetrics.length) {
          const extra: MerchantMetricsResponse | null = await getMerchantMetrics(merchant).catch(
            () => null,
          );
          if (extra?.metrics?.length) {
            setMetrics(extra.metrics);
          }
        }
        const score = await getMerchantHealth(merchant).catch(() => null);
        setHealth(score);
        if (usedMlTask(runEvents, ["ml_risk"], ["score_risk"])) {
          setRisk(await getMerchantRisk(merchant).catch(() => null));
        }
        if (usedMlTask(runEvents, ["ml_regression"], ["score_regression"])) {
          setRegression(await getMerchantRegression(merchant).catch(() => null));
        }
      }
      setView(created.status === "failed" ? "failed" : "ready");
      const listed = await listInvestigations().catch(() => null);
      if (listed) {
        setHistory(listed.items.map(toHistoryItem));
      }
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

  const runRef = useRef(runInvestigation);
  runRef.current = runInvestigation;
  useEffect(() => {
    if (!autoRun || !initialQuestion) {
      return;
    }
    const key = `${initialInputMethod}:${initialQuestion}`;
    if (autoRunOnce.has(key)) {
      return;
    }
    autoRunOnce.add(key);
    void runRef.current();
  }, [autoRun, initialQuestion, initialInputMethod]);

  const statusChip = statusFor(view, report);

  return (
    <div className="research-layout">
      <div>
        <h1 className="page-title">Research workspace</h1>
        <p className="page-lead">
          Query, plan, agent status, evidence, ML, transaction checks, and the written report.
          API {apiOk === true ? "connected" : apiOk === false ? "unreachable" : "checking"} ·{" "}
          {environment}
        </p>
      </div>
      <section className="panel research-composer">
        <div className="panel-hd">Query</div>
        <div className="panel-bd">
          <div className="field">
            <label htmlFor="research-question">Research question</label>
            <div className="query-input-wrap">
              <textarea
                id="research-question"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                disabled={view === "running"}
              />
              <VoiceQueryButton
                disabled={view === "running"}
                value={question}
                speechLang={speechRecognitionLang(language, question)}
                onChange={setQuestion}
                onError={(message) => setError({ message })}
                onClearError={() => setError(null)}
                onVoiceOrigin={() => setInputMethod("voice")}
                onBusyChange={setVoiceBusy}
              />
            </div>
          </div>
          <label className="field">
            Query language
            <select
              value={language}
              disabled={view === "running"}
              onChange={(event) => setLanguage(event.target.value as LanguageChoice)}
            >
              {LANGUAGE_OPTIONS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
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
          <button
            className="btn btn-primary"
            disabled={view === "running" || voiceBusy}
            onClick={runInvestigation}
          >
            {view === "running" ? "Running…" : "Run investigation"}
          </button>
          <div className="samples" style={{ marginTop: 12 }}>
            {SAMPLE_QUESTIONS.map((sample) => (
              <button
                key={sample.label}
                className="sample"
                disabled={view === "running"}
                type="button"
                onClick={() => {
                  setQuestion(sample.question);
                  setMerchantId(sample.merchant_id ?? "");
                  setInputMethod("text");
                }}
              >
                {sample.label}
              </button>
            ))}
          </div>
        </div>
      </section>
      <div className="workspace" style={{ gridTemplateColumns: "1fr" }}>
        <aside className="rail" style={{ borderRight: 0 }}>
          <div className="status-block">
            <div className="panel-hd" style={{ padding: 0, border: 0, marginBottom: 8 }}>
              Investigation status
            </div>
            <span className={`chip ${statusChip.tone}`}>{statusChip.label}</span>
            <dl className="kv" style={{ marginTop: 10 }}>
              <dt>Step</dt>
              <dd>
                {view === "idle"
                  ? "Idle"
                  : view === "running" && !current
                    ? "Waiting"
                    : stageLabel(current)}
              </dd>
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

          <QueryHistory
            items={visibleHistory(history, view, submittedRun)}
            busy={historyBusy || view === "running"}
            onDelete={async (id) => {
              setHistoryBusy(true);
              try {
                await deleteInvestigation(id);
                forgetInvestigation(id);
                setHistory((current) => current.filter((item) => item.investigation_id !== id));
              } catch (err) {
                setError({
                  message: err instanceof ApiError ? err.message : "Could not delete that query.",
                  requestId: err instanceof ApiError ? err.requestId : undefined,
                });
              } finally {
                setHistoryBusy(false);
              }
            }}
            onClear={async () => {
              setHistoryBusy(true);
              try {
                await deleteAllInvestigations();
                forgetInvestigation();
                setHistory([]);
              } catch (err) {
                setError({
                  message: err instanceof ApiError ? err.message : "Could not clear query history.",
                  requestId: err instanceof ApiError ? err.requestId : undefined,
                });
              } finally {
                setHistoryBusy(false);
              }
            }}
          />

          <section className="panel">
            <div className="panel-hd">Research plan</div>
            <div className="panel-bd">
              {view === "running" ? (
                <div className="loading-box">
                  Waiting for planner events from the investigation graph.
                </div>
              ) : (
                <ResearchPlan events={events} question={submittedRun?.query ?? question} />
              )}
            </div>
          </section>

          <section className="panel" id="agent-execution">
            <div className="panel-hd">
              Agent status
              <span className="hint">
                Nodes update from investigation trace events only — no simulated progress
              </span>
            </div>
            <div className="panel-bd">
              {submittedRun ? (
                <OriginalQueryCard
                  transcript={submittedRun.query}
                  queryLanguage={investigation?.query_language || submittedRun.query_language}
                  inputMethod={submittedRun.input_method}
                />
              ) : null}
              <AgentGraph
                states={states}
                events={events}
                question={submittedRun?.query ?? question}
                caption={
                  view === "running"
                    ? "Waiting for execution events"
                    : events.length
                      ? "Agent execution"
                      : "Agent architecture"
                }
              />
              <TracePipeline states={states} events={events} />
            </div>
          </section>

          <section className="panel">
            <div className="panel-hd">
              Agent execution timeline
              <span className="hint">node · action · tool · query · evidence IDs · decision</span>
            </div>
            <div className="panel-bd" style={{ padding: 0 }}>
              {view === "running" ? (
                <div className="loading-box">
                  Trace events appear when the graph publishes them. Nodes stay waiting until then.
                </div>
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

          <section className="panel">
            <div className="panel-hd">
              Agentic retrieval
              <span className="hint">Search rounds, rewrites, latency — no chain-of-thought</span>
            </div>
            <div className="panel-bd">
              {view === "running" ? (
                <div className="loading-box">Running retrieve → evaluate → rewrite…</div>
              ) : (
                <RetrievalLoop retrieval={report?.retrieval ?? null} />
              )}
            </div>
          </section>

          <div className="grid-2">
            <section className="panel" id="research-evidence">
              <div className="panel-hd">Evidence</div>
              <div className="panel-bd">
                <EvidenceList
                  items={evidence}
                  loading={view === "running"}
                  fallbackTime={investigation?.created_at}
                />
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
            <section className="panel" id="research-confidence">
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

          <section className="panel" id="research-ml">
            <div className="panel-hd">
              Failure classifier
              <span className="hint">Classification only — not a fraud decision</span>
            </div>
            <div className="panel-bd">
              {view === "running" ? (
                <div className="loading-box">Fitting the holdout classifier…</div>
              ) : !risk ? (
                <div className="empty">
                  No classifier on this run. Ask about predicted risk or classification for a merchant.
                </div>
              ) : (
                <>
                  <div className="score-row">
                    <div className="score">{formatPercent(risk.risk_probability)}</div>
                    <span className={`chip ${risk.risk_class === "HIGH" ? "bad" : risk.risk_class === "MEDIUM" ? "warn" : "ok"}`}>
                      {risk.prediction} · {risk.risk_class}
                    </span>
                    <span className={`chip ${risk.next_action === "investigate" ? "warn" : "idle"}`}>
                      {risk.next_action}
                    </span>
                  </div>
                  <dl className="kv">
                    <dt>Class probabilities</dt>
                    <dd className="mono">
                      succeeded {formatPercent(risk.class_probabilities.succeeded ?? 0)} · failed{" "}
                      {formatPercent(risk.class_probabilities.failed ?? 0)}
                    </dd>
                    <dt>Holdout</dt>
                    <dd className="mono">
                      Acc {risk.quality.accuracy.toFixed(2)} · P {risk.quality.precision.toFixed(2)} · R{" "}
                      {risk.quality.recall.toFixed(2)} · F1 {risk.quality.f1.toFixed(2)} · ROC-AUC{" "}
                      {risk.quality.roc_auc == null ? "n/a" : risk.quality.roc_auc.toFixed(2)}
                    </dd>
                    <dt>Confusion</dt>
                    <dd className="mono">
                      TP {risk.quality.confusion_matrix.true_positive} · FP{" "}
                      {risk.quality.confusion_matrix.false_positive} · FN{" "}
                      {risk.quality.confusion_matrix.false_negative} · TN{" "}
                      {risk.quality.confusion_matrix.true_negative}
                    </dd>
                    <dt>Sample</dt>
                    <dd className="mono">
                      {risk.sample_size} payments · {risk.fail_count} failed
                    </dd>
                    <dt>Version</dt>
                    <dd className="mono">
                      {risk.card
                        ? `${risk.card.model_version} · ${risk.card.dataset_version}`
                        : "—"}
                    </dd>
                  </dl>
                  {risk.contributions.length ? (
                    <div style={{ marginTop: 10, color: "var(--muted)" }}>
                      Features:{" "}
                      {risk.contributions
                        .map((item) => `${item.feature} ${item.contribution >= 0 ? "+" : ""}${item.contribution.toFixed(2)}`)
                        .join(" · ")}
                    </div>
                  ) : null}
                  <p className="banner">{risk.notes}</p>
                  <div className="field" style={{ marginTop: 12 }}>
                    What-if amount (INR rupees)
                    <input
                      value={whatIfAmount}
                      onChange={(event) => setWhatIfAmount(event.target.value)}
                      inputMode="numeric"
                    />
                  </div>
                  <label className="field">
                    What-if method
                    <select value={whatIfMethod} onChange={(event) => setWhatIfMethod(event.target.value)}>
                      <option value="upi">upi</option>
                      <option value="card">card</option>
                      <option value="netbanking">netbanking</option>
                      <option value="wallet">wallet</option>
                    </select>
                  </label>
                  <button
                    className="btn"
                    disabled={whatIfBusy}
                    onClick={async () => {
                      const rupees = Number(whatIfAmount);
                      if (!Number.isFinite(rupees) || rupees <= 0) {
                        return;
                      }
                      setWhatIfBusy(true);
                      try {
                        const scored = await postRiskWhatIf(risk.merchant_id, {
                          method_id: whatIfMethod,
                          amount_cents: Math.round(rupees * 100),
                        });
                        setWhatIf(scored);
                      } catch {
                        setWhatIf(null);
                      } finally {
                        setWhatIfBusy(false);
                      }
                    }}
                  >
                    {whatIfBusy ? "Rescoring…" : "Rescore hypothetical payment"}
                  </button>
                  {whatIf ? (
                    <dl className="kv" style={{ marginTop: 12 }}>
                      <dt>What-if risk</dt>
                      <dd>
                        {formatPercent(whatIf.risk_probability)} {whatIf.risk_class}
                      </dd>
                    </dl>
                  ) : null}
                </>
              )}
            </div>
          </section>

          <section className="panel">
            <div className="panel-hd">
              Capture-latency regressor
              <span className="hint">Separate model — MAE / RMSE / R² only</span>
            </div>
            <div className="panel-bd">
              {view === "running" ? (
                <div className="loading-box">Fitting the holdout regressor…</div>
              ) : !regression ? (
                <div className="empty">
                  No regressor on this run. Ask about capture latency or expected delay for a merchant.
                </div>
              ) : (
                <>
                  <div className="score-row">
                    <div className="score">{regression.prediction.toFixed(2)}</div>
                    <span className="chip idle">{regression.unit}</span>
                    <span className="chip idle">{regression.target}</span>
                  </div>
                  <dl className="kv">
                    <dt>Holdout</dt>
                    <dd className="mono">
                      MAE {regression.quality.mae.toFixed(2)} · RMSE {regression.quality.rmse.toFixed(2)}{" "}
                      · R² {regression.quality.r2.toFixed(2)}
                    </dd>
                    <dt>Sample</dt>
                    <dd className="mono">{regression.sample_size} captured payments</dd>
                    <dt>Version</dt>
                    <dd className="mono">
                      {regression.card.model_version} · {regression.card.dataset_version}
                    </dd>
                  </dl>
                  {regression.contributions.length ? (
                    <div style={{ marginTop: 10, color: "var(--muted)" }}>
                      Features:{" "}
                      {regression.contributions
                        .map((item) => `${item.feature} ${item.contribution >= 0 ? "+" : ""}${item.contribution.toFixed(2)}`)
                        .join(" · ")}
                    </div>
                  ) : null}
                  <p className="banner">{regression.notes}</p>
                </>
              )}
            </div>
          </section>

          <div id="research-transactions">
            <LedgerPanel />
          </div>

          <section className="panel" id="research-report">
            <div className="panel-hd">Final investigation report</div>
            <div className="panel-bd">
              {view === "running" ? (
                <div className="loading-box">Drafting the structured report…</div>
              ) : !report ? (
                <div className="empty">The report is empty until an investigation completes.</div>
              ) : (
                <>
                  <h2 className="h1">{report.executive_summary}</h2>
                  <a className="btn btn-ghost" href="#why-this-result" style={{ width: "auto", margin: "12px 0" }}>
                    Why this result?
                  </a>
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

          <section className="panel" id="why-this-result">
            <div className="panel-hd">Why this result?</div>
            <div className="panel-bd">
              {!report ? (
                <div className="empty">
                  The writer has not published a report yet. This section cites the same
                  evidence, tools, and confidence the graph actually produced.
                </div>
              ) : (
                <>
                  <p>{report.likely_cause.cause}</p>
                  <dl className="kv">
                    <dt>Confidence</dt>
                    <dd className="mono">{formatPercent(report.confidence)}</dd>
                    <dt>Evidence</dt>
                    <dd>
                      {report.evidence_sufficient ? "Sufficient" : "Insufficient"} ·{" "}
                      {report.evidence.length} citations
                    </dd>
                    <dt>Retrieval</dt>
                    <dd>
                      {report.retrieval
                        ? `${report.retrieval.iterations} rounds · ${report.retrieval.sufficient ? "enough sources" : "not enough sources"}`
                        : "No retrieval summary"}
                    </dd>
                  </dl>
                  <div className="cta-row" style={{ marginTop: 12 }}>
                    <a className="btn btn-ghost" href="#research-evidence">
                      Evidence
                    </a>
                    <a className="btn btn-ghost" href="#research-ml">
                      ML Analysis
                    </a>
                    <a className="btn btn-ghost" href="#research-transactions">
                      Transaction Analysis
                    </a>
                    <a className="btn btn-ghost" href="#research-confidence">
                      Confidence
                    </a>
                    <a className="btn btn-ghost" href="#research-sources">
                      Sources
                    </a>
                  </div>
                </>
              )}
            </div>
          </section>

          <section className="panel" id="research-sources">
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

function toHistoryItem(item: InvestigationSummary): QueryHistoryItem {
  return {
    investigation_id: item.investigation_id,
    question: item.question,
    input_method: item.input_method === "voice" ? "voice" : "text",
    status: item.status,
    created_at: item.created_at,
    duration_ms: item.duration_ms ?? null,
  };
}

function visibleHistory(
  history: QueryHistoryItem[],
  view: ViewState,
  submitted: { query: string; input_method: InputMethod } | null,
): QueryHistoryItem[] {
  if (view !== "running" || !submitted) {
    return history;
  }
  return [
    {
      investigation_id: "pending",
      question: submitted.query,
      input_method: submitted.input_method,
      status: "running",
      created_at: new Date().toISOString(),
      duration_ms: null,
    },
    ...history,
  ];
}

function usedMlTask(events: TraceEvent[], tools: string[], decisions: string[]): boolean {
  return events.some(
    (event) =>
      (event.tool != null && tools.includes(event.tool)) ||
      (event.decision != null && decisions.includes(event.decision)),
  );
}

function ResearchPlan({ events, question }: { events: TraceEvent[]; question: string }) {
  const planner = events.filter((event) => event.node === "planner");
  if (!planner.length) {
    return (
      <div className="empty">
        The orchestrator has not published a plan. Submit a question such as settlement delay
        analysis for Harbor Retail.
      </div>
    );
  }
  return (
    <ol className="plan-list">
      <li>
        <strong>Question</strong>
        <span>{question}</span>
      </li>
      {planner.map((event, index) => (
        <li key={`${event.timestamp}-${index}`}>
          <strong>{event.action}</strong>
          <span>
            {event.decision ?? "queued"}
            {event.tool ? ` · ${event.tool}` : ""}
          </span>
        </li>
      ))}
    </ol>
  );
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
