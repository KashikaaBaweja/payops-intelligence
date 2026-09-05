"use client";

import { useEffect, useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "./states/PageState";
import { getInvestigation } from "../lib/api";
import { formatMetricValue, formatPercent, formatTime } from "../lib/format";
import type { InvestigationResponse } from "../lib/types";
import { ApiError } from "../lib/types";

export function ReportDetail({ id }: { id: string }) {
  const [record, setRecord] = useState<InvestigationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getInvestigation(id)
      .then(setRecord)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Report missing."))
      .finally(() => setLoading(false));
  }, [id]);

  const report = record?.report;
  const mlMetrics = report?.observed_metrics.filter((item) => item.source === "ml") ?? [];
  const txnMetrics = report?.observed_metrics.filter((item) => item.source !== "ml") ?? [];
  const usedMl = report?.agent_execution_summary.some(
    (event) =>
      event.tool === "ml_risk" ||
      event.tool === "ml_regression" ||
      event.decision === "score_risk" ||
      event.decision === "score_regression",
  );
  const usedIntegrity = report?.agent_execution_summary.some(
    (event) => event.tool === "validate_integrity" || event.decision === "validate_integrity",
  );

  return (
    <>
      <h1 className="page-title">Investigation report</h1>
      <p className="page-lead">
        Structured output from the writer. Findings stay tied to evidence IDs and catalog
        metrics — not free-form model prose.
      </p>
      {loading ? <LoadingState label="Opening report…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      {!loading && !error && !report ? (
        <EmptyState title="No report body" detail="This run did not persist a structured report." />
      ) : null}
      {report ? (
        <div className="stack">
          <section className="panel">
            <div className="panel-hd">Executive summary</div>
            <div className="panel-bd">
              <h2 className="h1">{report.executive_summary}</h2>
              <span className={`chip ${severityTone(report.severity)}`}>{report.severity}</span>
            </div>
          </section>
          <section className="panel">
            <div className="panel-hd">Research question</div>
            <div className="panel-bd">
              <p>{record?.question}</p>
              <dl className="kv">
                <dt>Merchant</dt>
                <dd className="mono">{report.merchant_id ?? "—"}</dd>
                <dt>Window</dt>
                <dd>
                  {report.time_window
                    ? `${formatTime(report.time_window.start)} → ${formatTime(report.time_window.end)}`
                    : "—"}
                </dd>
                <dt>Incident</dt>
                <dd className="mono">{report.incident_id}</dd>
              </dl>
            </div>
          </section>
          <section className="panel">
            <div className="panel-hd">Key findings</div>
            <div className="panel-bd">
              {!report.findings.length ? (
                <div className="empty">Writer returned no finding lines.</div>
              ) : (
                report.findings.map((finding) => (
                  <div className="finding" key={finding}>
                    {finding}
                  </div>
                ))
              )}
              <p style={{ marginTop: 12 }}>{report.likely_cause.cause}</p>
            </div>
          </section>
          <section className="panel">
            <div className="panel-hd">Evidence</div>
            <div className="panel-bd">
              {!report.evidence.length ? (
                <div className="empty">No evidence IDs attached to this report.</div>
              ) : (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Citation</th>
                        <th>Source</th>
                        <th>Label</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.evidence.map((item) => (
                        <tr key={item.evidence_id}>
                          <td className="mono">{item.evidence_id}</td>
                          <td>{item.source}</td>
                          <td>{item.label}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>
          <section className="panel">
            <div className="panel-hd">ML analysis</div>
            <div className="panel-bd">
              {!usedMl && !mlMetrics.length ? (
                <div className="empty">
                  This run did not call the classifier or capture-latency regressor.
                </div>
              ) : (
                <MetricTable rows={mlMetrics.length ? mlMetrics : report.observed_metrics} />
              )}
            </div>
          </section>
          <section className="panel">
            <div className="panel-hd">Transaction analysis</div>
            <div className="panel-bd">
              {!usedIntegrity && !txnMetrics.length ? (
                <div className="empty">
                  No catalog metrics or integrity check on this question.
                </div>
              ) : (
                <MetricTable rows={txnMetrics.length ? txnMetrics : report.observed_metrics} />
              )}
            </div>
          </section>
          <section className="panel">
            <div className="panel-hd">Confidence</div>
            <div className="panel-bd">
              <div className="score-row">
                <div className="score">{formatPercent(report.confidence)}</div>
                <span className={`chip ${report.evidence_sufficient ? "ok" : "warn"}`}>
                  {report.evidence_sufficient ? "Evidence sufficient" : "Insufficient evidence"}
                </span>
              </div>
            </div>
          </section>
          <section className="panel">
            <div className="panel-hd">Limitations</div>
            <div className="panel-bd">
              <ul className="actions">
                <li>
                  {report.evidence_sufficient
                    ? "Evidence met the verifier bar for this question."
                    : "Evidence was insufficient for a confident root cause."}
                </li>
                {report.retrieval?.conflicting ? (
                  <li>{report.retrieval.conflict_note || "Retrieved sources conflict."}</li>
                ) : null}
                <li>Demo mode does not call an LLM. The graph is deterministic.</li>
                {report.alternative_hypotheses.length ? (
                  <li>
                    Alternatives: {report.alternative_hypotheses.map((item) => item.cause).join(" · ")}
                  </li>
                ) : null}
              </ul>
            </div>
          </section>
          <section className="panel">
            <div className="panel-hd">Sources</div>
            <div className="panel-bd">
              {!(report.sources.length || report.evidence.length) ? (
                <div className="empty">No source references persisted.</div>
              ) : (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Evidence ID</th>
                        <th>Source</th>
                        <th>Label</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(report.sources.length ? report.sources : report.evidence).map((item) => (
                        <tr key={`src-${item.evidence_id}`}>
                          <td className="mono">{item.evidence_id}</td>
                          <td>{item.source}</td>
                          <td>{item.label}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}

function MetricTable({
  rows,
}: {
  rows: NonNullable<InvestigationResponse["report"]>["observed_metrics"];
}) {
  if (!rows.length) {
    return <div className="empty">No numeric metrics attached to this section.</div>;
  }
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Metric</th>
            <th>Value</th>
            <th>Tool</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((metric) => (
            <tr key={`${metric.operation}-${metric.metric}`}>
              <td>{metric.metric}</td>
              <td className="mono">{formatMetricValue(metric)}</td>
              <td className="mono">{metric.tool}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function severityTone(severity: "low" | "medium" | "high" | "critical"): string {
  if (severity === "critical" || severity === "high") {
    return "bad";
  }
  if (severity === "medium") {
    return "warn";
  }
  return "ok";
}
