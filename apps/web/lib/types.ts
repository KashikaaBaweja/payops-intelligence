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
  source: "doc" | "metric" | "webhook" | "health" | "ml" | "integrity";
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

export type RetrievalRound = {
  search_index: number;
  query: string;
  rewritten_from: string | null;
  rewrite_reason: string | null;
  retrieved: number;
  kept: number;
  rejected: number;
  sufficient: boolean;
  decision: "sufficient" | "rewrite" | "exhausted" | "no_results";
  latency_ms: number;
  evidence_ids: string[];
  missing_facets: string[];
};

export type SourceCitation = {
  evidence_id: string;
  document_id: string;
  section: string;
  score: number;
};

export type RetrievalSummary = {
  iterations: number;
  max_iterations: number;
  latency_ms: number;
  sufficient: boolean;
  conflicting: boolean;
  conflict_note: string | null;
  grounded_excerpt: string;
  citations: SourceCitation[];
  rounds: RetrievalRound[];
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
  retrieval: RetrievalSummary | null;
};

export type InvestigationSummary = {
  investigation_id: string;
  question: string;
  status: "completed" | "failed";
  created_at: string;
  merchant_id: string | null;
  confidence: number | null;
  evidence_sufficient: boolean | null;
};

export type InvestigationListResponse = {
  items: InvestigationSummary[];
  total: number;
};

export type ServiceStatus = {
  name: string;
  status: "ok" | "down" | "disabled" | "degraded";
  detail: string;
};

export type SystemHealthResponse = {
  status: "ok" | "degraded" | "down";
  environment: string;
  version: string;
  services: ServiceStatus[];
};

export type CorpusDocument = {
  document_id: string;
  name: string;
  kind: string;
  bytes: number;
};

export type CorpusResponse = {
  backend: string;
  documents: CorpusDocument[];
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

export type RiskContribution = {
  feature: string;
  coefficient: number;
  value: number;
  contribution: number;
  explanation: string;
};

export type ConfusionMatrix = {
  true_negative: number;
  false_positive: number;
  false_negative: number;
  true_positive: number;
};

export type ModelCard = {
  task: "classification" | "regression";
  algorithm: string;
  target: string;
  model_version: string;
  dataset_version: string;
  feature_names: string[];
  train_rows: number;
  test_rows: number;
};

export type ClassificationQuality = {
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  roc_auc: number | null;
  positive_support: number;
  test_size: number;
  confusion_matrix: ConfusionMatrix;
};

export type RegressionQuality = {
  mae: number;
  rmse: number;
  r2: number;
  test_size: number;
};

export type MerchantRiskScore = {
  merchant_id: string;
  window: { start: string; end: string } | null;
  sample_size: number;
  fail_count: number;
  prediction: string;
  risk_probability: number;
  class_probabilities: Record<string, number>;
  risk_class: "LOW" | "MEDIUM" | "HIGH";
  expected_loss_cents: number;
  currency: string;
  features: Record<string, number>;
  contributions: RiskContribution[];
  quality: ClassificationQuality;
  card: ModelCard | null;
  next_action: "monitor" | "investigate";
  notes: string;
};

export type RegressionScore = {
  merchant_id: string;
  window: { start: string; end: string } | null;
  sample_size: number;
  target: string;
  prediction: number;
  unit: string;
  features: Record<string, number>;
  contributions: RiskContribution[];
  quality: RegressionQuality;
  card: ModelCard;
  notes: string;
};

export type RiskWhatIfScore = {
  merchant_id: string;
  method_id: string;
  amount_cents: number;
  risk_probability: number;
  risk_class: "LOW" | "MEDIUM" | "HIGH";
  expected_loss_cents: number;
  currency: string;
  contributions: RiskContribution[];
  next_action: "monitor" | "investigate";
  notes: string;
};

export type LedgerAccountView = {
  account_id: string;
  merchant_id: string | null;
  kind: string;
  currency: string;
  balance_cents: number;
  version: number;
  status: string;
};

export type TransferOperation = {
  name: string;
  state: string;
  account_id: string | null;
  delta_cents: number | null;
};

export type TransferAuditEvent = {
  audit_id: string;
  event: string;
  detail: string;
  created_at: string;
};

export type TransferResult = {
  transfer_id: string;
  status: "committed" | "rolled_back";
  current_state: string;
  from_account_id: string;
  to_account_id: string;
  amount_cents: number;
  isolation_level: string;
  isolation_reason: string;
  fail_at: string | null;
  failure_point: string | null;
  before_balance: { from: number; to: number };
  after_balance: { from: number; to: number };
  operations: TransferOperation[];
  commit_or_rollback: "COMMIT" | "ROLLBACK";
  audit_events: TransferAuditEvent[];
  notes: string;
};

export type LedgerAccountsResponse = {
  isolation_level: string;
  isolation_reason: string;
  accounts: LedgerAccountView[];
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
