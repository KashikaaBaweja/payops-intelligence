import { request } from "./api";

export type UserRole = "user" | "admin";
export type UserStatus = "active" | "suspended";

export type AuthUser = {
  user_id: string;
  name: string;
  email: string;
  role: UserRole;
  status: UserStatus;
  created_at: string;
  last_active_at: string | null;
  last_login_at: string | null;
};

export type AuthSuccess = { user: AuthUser };

export function signup(payload: {
  name: string;
  email: string;
  password: string;
  confirm_password: string;
}): Promise<AuthSuccess> {
  return request("/auth/signup", { method: "POST", body: JSON.stringify(payload) });
}

export function login(payload: { email: string; password: string }): Promise<AuthSuccess> {
  return request("/auth/login", { method: "POST", body: JSON.stringify(payload) });
}

export function logout(): Promise<{ message: string }> {
  return request("/auth/logout", { method: "POST" });
}

export function getMe(): Promise<AuthUser> {
  return request("/auth/me");
}

export function updateProfile(name: string): Promise<AuthUser> {
  return request("/auth/me", { method: "PATCH", body: JSON.stringify({ name }) });
}

export function forgotPassword(email: string): Promise<{ message: string }> {
  return request("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) });
}

export function resetPassword(payload: {
  token: string;
  password: string;
  confirm_password: string;
}): Promise<{ message: string }> {
  return request("/auth/reset-password", { method: "POST", body: JSON.stringify(payload) });
}

export function changePassword(payload: {
  current_password: string;
  password: string;
  confirm_password: string;
}): Promise<{ message: string }> {
  return request("/auth/change-password", { method: "POST", body: JSON.stringify(payload) });
}

export function getAdminOverview(): Promise<{
  total_users: number | null;
  active_users: number | null;
  research_runs: number | null;
  documents_indexed: number | null;
  transactions_analyzed: number | null;
  agent_success_rate: number | null;
  system_health: string | null;
}> {
  return request("/admin/overview");
}

export function getAdminUsers(): Promise<{ items: AuthUser[]; total: number }> {
  return request("/admin/users");
}

export function suspendUser(id: string): Promise<AuthUser> {
  return request(`/admin/users/${id}/suspend`, { method: "POST" });
}

export function activateUser(id: string): Promise<AuthUser> {
  return request(`/admin/users/${id}/activate`, { method: "POST" });
}

export function changeUserRole(id: string, role: UserRole): Promise<AuthUser> {
  return request(`/admin/users/${id}/role`, { method: "POST", body: JSON.stringify({ role }) });
}

export function getAdminAudit(): Promise<{
  items: Array<{
    event_id: string;
    actor_id: string | null;
    event_type: string;
    timestamp: string;
    resource_id: string | null;
    metadata: Record<string, unknown>;
  }>;
  total: number;
}> {
  return request("/admin/audit");
}

export function getAdminResearch(): Promise<{
  total: number;
  items: Array<{
    investigation_id: string;
    question: string;
    status: string;
    created_at: string;
    duration_ms: number | null;
    input_method: string;
  }>;
}> {
  return request("/admin/research");
}

export function getAdminDocuments(): Promise<{
  backend: string;
  documents: Array<{ document_id: string; name: string; bytes: number }>;
}> {
  return request("/admin/documents");
}

export function getAdminAgents(): Promise<
  Array<{
    agent: string;
    status: string | null;
    runs: number | null;
    success_rate: number | null;
    average_duration_ms: number | null;
    last_run: string | null;
  }>
> {
  return request("/admin/agents");
}

export function getAdminMl(): Promise<
  Array<{
    model_name: string;
    task: string;
    version: string | null;
    dataset_version: string | null;
    last_trained: string | null;
    metrics: Record<string, unknown>;
    notes: string | null;
  }>
> {
  return request("/admin/ml");
}

export function getAdminTransactions(): Promise<
  Array<{
    transaction_id: string;
    amount_cents: number | null;
    status: string | null;
    risk_level: string | null;
    processing_state: string | null;
    created_at: string | null;
  }>
> {
  return request("/admin/transactions");
}

export function getAdminTransaction(id: string): Promise<{
  transaction_id: string;
  amount_cents: number | null;
  status: string | null;
  risk_level: string | null;
  processing_state: string | null;
  created_at: string | null;
  timeline: Array<Record<string, unknown>>;
  risk_analysis: string | null;
  validation: string | null;
  audit_events: Array<Record<string, unknown>>;
}> {
  return request(`/admin/transactions/${id}`);
}

export function getAdminHealth(): Promise<{
  status: string;
  environment: string;
  services: Array<{ name: string; status: string; detail: string }>;
}> {
  return request("/admin/health");
}

export function getAdminSettings(): Promise<{
  environment: string;
  vector_backend: string;
  llm_provider: string;
  session_ttl_hours: number;
  smtp_configured: boolean;
  public_app_url: string;
}> {
  return request("/admin/settings");
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) {
    return "PI";
  }
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase() ?? "").join("");
}
