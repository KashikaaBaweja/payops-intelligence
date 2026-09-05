from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)
    confirm_password: str = Field(min_length=1, max_length=128)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=254)


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    token: str = Field(min_length=8, max_length=256)
    password: str = Field(min_length=1, max_length=128)
    confirm_password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)
    confirm_password: str = Field(min_length=1, max_length=128)


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=80)


class RoleChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "admin"]


class PublicUser(BaseModel):
    user_id: str
    name: str
    email: str
    role: Literal["user", "admin"]
    status: Literal["active", "suspended"]
    created_at: datetime
    last_active_at: datetime | None = None
    last_login_at: datetime | None = None


class AuthSuccessResponse(BaseModel):
    user: PublicUser
    email_delivery: Literal["sent", "not_configured"] | None = None


class MessageResponse(BaseModel):
    message: str


class AdminUserRow(PublicUser):
    pass


class AdminUserListResponse(BaseModel):
    items: list[AdminUserRow] = Field(default_factory=list)
    total: int = 0


class AdminOverviewResponse(BaseModel):
    total_users: int | None = None
    active_users: int | None = None
    research_runs: int | None = None
    documents_indexed: int | None = None
    transactions_analyzed: int | None = None
    agent_success_rate: float | None = None
    system_health: str | None = None


class AdminAgentRow(BaseModel):
    agent: str
    status: str | None = None
    runs: int | None = None
    success_rate: float | None = None
    average_duration_ms: int | None = None
    last_run: datetime | None = None


class AdminMlModelRow(BaseModel):
    model_name: str
    task: str
    version: str | None = None
    dataset_version: str | None = None
    last_trained: datetime | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class AdminTransactionRow(BaseModel):
    transaction_id: str
    amount_cents: int | None = None
    status: str | None = None
    risk_level: str | None = None
    processing_state: str | None = None
    created_at: datetime | None = None


class AdminTransactionDetail(AdminTransactionRow):
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    risk_analysis: str | None = None
    agent_execution: list[dict[str, Any]] = Field(default_factory=list)
    validation: str | None = None
    audit_events: list[dict[str, Any]] = Field(default_factory=list)


class AuditEventRow(BaseModel):
    event_id: str
    actor_id: str | None = None
    event_type: str
    timestamp: datetime
    resource_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditListResponse(BaseModel):
    items: list[AuditEventRow] = Field(default_factory=list)
    total: int = 0
