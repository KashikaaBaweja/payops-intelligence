import type {
  ApiErrorBody,
  CorpusResponse,
  EvidenceItem,
  InvestigationListResponse,
  InvestigationResponse,
  InvestigationTraceResponse,
  MerchantHealthScore,
  MerchantMetricsResponse,
  LedgerAccountsResponse,
  MerchantRiskScore,
  RegressionScore,
  RiskWhatIfScore,
  SystemHealthResponse,
  TransferResult,
} from "./types";
import { ApiError } from "./types";

const BASE = "/backend";

function detailMessage(detail: ApiErrorBody["detail"]): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail) && detail.length) {
    return "Request failed validation.";
  }
  return "Request failed.";
}

const API_DOWN =
  "Cannot reach the PayIntel API on port 8000. From the repo root run: source .venv/bin/activate && PYTHONPATH=packages:. uvicorn apps.api.main:app --reload --port 8000";

function isJsonResponse(response: Response): boolean {
  return (response.headers.get("content-type") || "").includes("application/json");
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const requestId = crypto.randomUUID();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60_000);
  try {
    const response = await fetch(`${BASE}${path}`, {
      ...init,
      credentials: "include",
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        "X-Request-ID": requestId,
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
    const echoed = response.headers.get("X-Request-ID") || requestId;
    if (!response.ok) {
      if (!isJsonResponse(response)) {
        throw new ApiError(API_DOWN, response.status || 503, echoed, "network_error");
      }
      let body: ApiErrorBody = {};
      try {
        body = (await response.json()) as ApiErrorBody;
      } catch {
        body = {};
      }
      if (
        response.status === 401 &&
        typeof window !== "undefined" &&
        !path.startsWith("/auth/") &&
        !path.startsWith("/health")
      ) {
        const next = encodeURIComponent(`${window.location.pathname}${window.location.search}`);
        window.location.assign(`/login?next=${next}`);
      }
      throw new ApiError(
        detailMessage(body.detail) || response.statusText,
        response.status,
        body.request_id || echoed,
        body.error || "http_error",
      );
    }
    if (response.status === 204) {
      return undefined as T;
    }
    if (!isJsonResponse(response)) {
      throw new ApiError(API_DOWN, 503, echoed, "network_error");
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The API did not respond in time.", 408, requestId, "timeout");
    }
    throw new ApiError(API_DOWN, 503, requestId, "network_error");
  } finally {
    clearTimeout(timer);
  }
}

export function createInvestigation(payload: {
  query: string;
  input_method: "text" | "voice";
  language?: "auto" | "en" | "hi" | "hi-latn";
  merchant_id?: string | null;
  max_iterations?: number;
}): Promise<InvestigationResponse> {
  const body: Record<string, unknown> = {
    query: payload.query,
    input_method: payload.input_method,
    max_iterations: payload.max_iterations ?? 3,
  };
  if (payload.language && payload.language !== "auto") {
    body.language = payload.language;
  }
  if (payload.merchant_id) {
    body.merchant_id = payload.merchant_id;
  }
  return request("/investigations", { method: "POST", body: JSON.stringify(body) });
}

export function getInvestigation(id: string): Promise<InvestigationResponse> {
  return request(`/investigations/${id}`);
}

export function getTrace(id: string): Promise<InvestigationTraceResponse> {
  return request(`/investigations/${id}/trace`);
}

export function getEvidence(id: string): Promise<EvidenceItem> {
  return request(`/evidence/${encodeURIComponent(id)}`);
}

export function getMerchantHealth(merchantId: string): Promise<MerchantHealthScore> {
  return request(`/merchants/${merchantId}/health`);
}

export function getMerchantMetrics(merchantId: string): Promise<MerchantMetricsResponse> {
  return request(`/merchants/${merchantId}/metrics`);
}

export function getMerchantRisk(merchantId: string): Promise<MerchantRiskScore> {
  return request(`/merchants/${merchantId}/risk`);
}

export function getMerchantRegression(merchantId: string): Promise<RegressionScore> {
  return request(`/merchants/${merchantId}/ml/regression`);
}

export function postRiskWhatIf(
  merchantId: string,
  payload: {
    method_id: string;
    amount_cents: number;
    prior_fail_rate?: number;
  },
): Promise<RiskWhatIfScore> {
  return request(`/merchants/${merchantId}/risk/what-if`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getApiHealth(): Promise<{ status: string; environment: string; version?: string }> {
  return request("/health");
}

export function getReady(): Promise<{ status: string; database: string; environment: string }> {
  return request("/health/ready");
}

export function getSystemHealth(): Promise<SystemHealthResponse> {
  return request("/health/services");
}

export function listInvestigations(): Promise<InvestigationListResponse> {
  return request("/investigations");
}

export function deleteInvestigation(id: string): Promise<void> {
  return request(`/investigations/${id}`, { method: "DELETE" });
}

export function deleteAllInvestigations(): Promise<{ deleted: number }> {
  return request("/investigations", { method: "DELETE" });
}

export function listDocuments(): Promise<CorpusResponse> {
  return request("/documents");
}

export function listTransfers(): Promise<TransferResult[]> {
  return request("/transactions/transfers");
}

export function getLedgerAccounts(): Promise<LedgerAccountsResponse> {
  return request("/transactions/accounts");
}

export function postLedgerTransfer(payload: {
  from_account_id: string;
  to_account_id: string;
  amount_cents: number;
  fail_at?: "after_debit" | "after_credit" | "after_ledger" | "before_commit" | null;
}): Promise<TransferResult> {
  return request("/transactions/transfers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
