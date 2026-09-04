export type TraceEvent = {
  node: string;
  action: string;
  tool: string | null;
  search_query: string | null;
  evidence_ids: string[];
  decision: string | null;
  verification_status: string | null;
  timestamp: string;
};

export type EvidenceRef = {
  evidence_id: string;
  source: string;
  label: string;
};

export type EvidenceItem = {
  evidence_id: string;
  source: "doc" | "metric" | "webhook" | "health";
  doc_id: string | null;
  section: string | null;
  chunk_id: string | null;
  score: number | null;
  text_snippet: string;
  metadata: Record<string, unknown>;
};

export type Hypothesis = {
  cause: string;
  supporting_evidence_ids: string[];
  confidence: number;
  category: string;
};

export type MetricResult = {
  metric: string;
  value: number | Record<string, unknown>;
  window: { start: string; end: string } | null;
  filters: Record<string, unknown>;
  tool: string;
  source: string;
  operation: string;
  merchant_id: string | null;
  unit: string;
  notes: string | null;
  sample_size: number | null;
};

export type IncidentReport = {
  executive_summary: string;
  merchant_id: string | null;
  incident_id: string;
  time_window: { start: string; end: string } | null;
  severity: "low" | "medium" | "high" | "critical";
  observed_metrics: MetricResult[];
  findings: string[];
  evidence: EvidenceRef[];
  likely_cause: Hypothesis;
  alternative_hypotheses: Hypothesis[];
  confidence: number;
  recommended_actions: string[];
  sources: EvidenceRef[];
  agent_execution_summary: TraceEvent[];
  evidence_sufficient: boolean;
};

export type InvestigationResponse = {
  investigation_id: string;
  status: "completed" | "failed";
  question: string;
  created_at: string;
  report: IncidentReport | null;
  error: string | null;
};

export type InvestigationTraceResponse = {
  investigation_id: string;
  events: TraceEvent[];
};

export type HealthFactor = {
  name: string;
  weight: number;
  value: number;
  score: number;
  band: "healthy" | "degraded" | "critical";
  explanation: string;
};

export type HealthPenalty = {
  factor: string;
  points: number;
  reason: string;
};

export type MerchantHealthScore = {
  merchant_id: string;
  window: { start: string; end: string } | null;
  score: number;
  band: "healthy" | "degraded" | "critical";
  factors: HealthFactor[];
  factor_values: Record<string, number>;
  penalties: HealthPenalty[];
  positive_signals: string[];
  recommendations: string[];
};

export type MerchantMetricsResponse = {
  merchant_id: string;
  window: { start: string; end: string };
  metrics: MetricResult[];
};

export type ApiErrorBody = {
  error?: string;
  detail?: string | unknown[];
  status_code?: number;
  request_id?: string;
};

export class ApiError extends Error {
  status: number;
  requestId: string;
  code: string;

  constructor(message: string, status: number, requestId: string, code: string) {
    super(message);
    this.name = "ApiError";
    Object.setPrototypeOf(this, new.target.prototype);
    this.status = status;
    this.requestId = requestId;
    this.code = code;
  }
}
