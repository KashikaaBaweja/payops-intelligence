"use client";

import { CSSProperties, FormEvent, useMemo, useState } from "react";

type TraceEvent = {
  step: string;
  agent: string;
  tool: string | null;
  input_summary: string;
  output_summary: string;
  timestamp: string;
};

type Report = {
  executive_summary: string;
  merchant_id: string | null;
  incident_id: string;
  severity: string;
  findings: string[];
  recommended_actions: string[];
  confidence: number;
  evidence_sufficient: boolean;
  likely_cause: { cause: string; confidence: number };
};

const EXAMPLES = [
  {
    label: "UPI timeout spike",
    question:
      "Why did Merchant M102's payment success rate decrease between 10 AM and 12 PM on 15 Jun 2024, what caused it, and what should ops do?",
    merchant_id: "M102",
    start: "2024-06-15T10:00:00",
    end: "2024-06-15T12:00:00",
  },
  {
    label: "Webhook delay storm",
    question: "Merchant M201 reports failed payments from 14:00-16:00 on 18 Jun 2024. Did payments actually fail?",
    merchant_id: "M201",
    start: "2024-06-18T14:00:00",
    end: "2024-06-18T16:00:00",
  },
  {
    label: "Sparse evidence",
    question: "Something is wrong with M305. Find the root cause.",
    merchant_id: "M305",
    start: "2024-05-01T00:00:00",
    end: "2024-05-02T00:00:00",
  },
];

export default function Page() {
  const [question, setQuestion] = useState(EXAMPLES[0].question);
  const [merchantId, setMerchantId] = useState(EXAMPLES[0].merchant_id);
  const [start, setStart] = useState(EXAMPLES[0].start);
  const [end, setEnd] = useState(EXAMPLES[0].end);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [trace, setTrace] = useState<TraceEvent[]>([]);

  const severityColor = useMemo(() => {
    const map: Record<string, string> = {
      low: "#7dd3a0",
      medium: "#f6c453",
      high: "#f08a5d",
      critical: "#ff6b6b",
    };
    return map[report?.severity || "low"];
  }, [report]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/backend/investigations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          merchant_id: merchantId || null,
          start,
          end,
        }),
      });
      if (!response.ok) {
        throw new Error(`API ${response.status}`);
      }
      const payload = await response.json();
      setReport(payload.report);
      setTrace(payload.trace || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 20px 64px" }}>
      <header style={{ marginBottom: 28 }}>
        <p style={{ letterSpacing: 2, color: "#8ea2c9", fontSize: 12, textTransform: "uppercase" }}>
          Payment operations
        </p>
        <h1 style={{ margin: "6px 0 8px", fontSize: 32 }}>PayOps Intelligence</h1>
        <p style={{ color: "#b7c4de", maxWidth: 720 }}>
          Multi-agent investigation for merchant incidents. Every claim is grounded in docs, metrics, or webhooks.
        </p>
      </header>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {EXAMPLES.map((example) => (
          <button
            key={example.label}
            type="button"
            onClick={() => {
              setQuestion(example.question);
              setMerchantId(example.merchant_id);
              setStart(example.start);
              setEnd(example.end);
            }}
            style={chipStyle}
          >
            {example.label}
          </button>
        ))}
      </div>

      <form onSubmit={onSubmit} style={cardStyle}>
        <label style={labelStyle}>Question</label>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={4}
          style={inputStyle}
        />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
          <Field label="Merchant" value={merchantId} onChange={setMerchantId} />
          <Field label="Window start" value={start} onChange={setStart} />
          <Field label="Window end" value={end} onChange={setEnd} />
        </div>
        <button type="submit" disabled={loading} style={buttonStyle}>
          {loading ? "Investigating…" : "Run investigation"}
        </button>
        {error ? <p style={{ color: "#ff8a8a" }}>{error}</p> : null}
      </form>

      {report ? (
        <section style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: 16, marginTop: 20 }}>
          <article style={cardStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ margin: 0 }}>Incident report</h2>
              <span style={{ color: severityColor, fontWeight: 700 }}>{report.severity.toUpperCase()}</span>
            </div>
            <p>{report.executive_summary}</p>
            <p>
              <strong>Cause:</strong> {report.likely_cause.cause}
            </p>
            <p>
              <strong>Confidence:</strong> {(report.confidence * 100).toFixed(0)}% · evidence{" "}
              {report.evidence_sufficient ? "sufficient" : "insufficient"}
            </p>
            <h3>Findings</h3>
            <ul>
              {report.findings.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <h3>Recommended actions</h3>
            <ul>
              {report.recommended_actions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
          <aside style={cardStyle}>
            <h2 style={{ marginTop: 0 }}>Execution trace</h2>
            <ol style={{ paddingLeft: 18 }}>
              {trace.map((event) => (
                <li key={`${event.step}-${event.timestamp}`} style={{ marginBottom: 12 }}>
                  <div style={{ fontWeight: 700 }}>{event.step}</div>
                  <div style={{ color: "#8ea2c9", fontSize: 13 }}>{event.agent}</div>
                  <div style={{ fontSize: 13 }}>{event.output_summary}</div>
                </li>
              ))}
            </ol>
          </aside>
        </section>
      ) : null}
    </main>
  );
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      <input value={value} onChange={(e) => onChange(e.target.value)} style={inputStyle} />
    </div>
  );
}

const cardStyle: CSSProperties = {
  background: "#121a2b",
  border: "1px solid #24324d",
  borderRadius: 16,
  padding: 20,
};

const inputStyle: CSSProperties = {
  width: "100%",
  margin: "6px 0 14px",
  padding: "10px 12px",
  borderRadius: 10,
  border: "1px solid #31415f",
  background: "#0b1220",
  color: "#e8eefc",
};

const labelStyle: CSSProperties = { fontSize: 12, color: "#8ea2c9" };

const buttonStyle: CSSProperties = {
  background: "#4c7dff",
  color: "white",
  border: 0,
  borderRadius: 10,
  padding: "10px 16px",
  fontWeight: 700,
  cursor: "pointer",
};

const chipStyle: CSSProperties = {
  background: "#182338",
  color: "#d5e2ff",
  border: "1px solid #31415f",
  borderRadius: 999,
  padding: "6px 12px",
  cursor: "pointer",
};
