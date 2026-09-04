import type {
  ApiErrorBody,
  EvidenceItem,
  InvestigationResponse,
  InvestigationTraceResponse,
  MerchantHealthScore,
  MerchantMetricsResponse,
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
  "Cannot reach the PayOps API on port 8000. From the repo root run: source .venv/bin/activate && PYTHONPATH=packages:. uvicorn apps.api.main:app --reload --port 8000";

function isJsonResponse(response: Response): boolean {
  return (response.headers.get("content-type") || "").includes("application/json");
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const requestId = crypto.randomUUID();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60_000);
  try {
    const response = await fetch(`${BASE}${path}`, {
      ...init,
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
      throw new ApiError(
        detailMessage(body.detail) || response.statusText,
        response.status,
        body.request_id || echoed,
        body.error || "http_error",
      );
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
  question: string;
  merchant_id?: string | null;
}): Promise<InvestigationResponse> {
  const body: Record<string, unknown> = { question: payload.question, max_iterations: 3 };
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

export function getApiHealth(): Promise<{ status: string; environment: string }> {
  return request("/health");
}
