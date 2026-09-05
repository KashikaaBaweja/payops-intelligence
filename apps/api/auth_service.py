from __future__ import annotations

from datetime import datetime, timedelta, timezone
from logging import getLogger

from payops_core.auth.audit import (
    EVENT_LOGIN,
    EVENT_LOGOUT,
    EVENT_PASSWORD_RESET,
    EVENT_PASSWORD_RESET_REQUEST,
    EVENT_SIGNUP,
    record_audit,
)
from payops_core.auth.emailer import EmailMessage, EmailSender
from payops_core.auth.passwords import hash_password, verify_password
from payops_core.auth.policy import normalize_email, normalize_name
from payops_core.auth.tokens import hash_token, new_token
from payops_core.config import Settings
from payops_core.data.models import AuthSession, AuthUser, PasswordResetToken
from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = getLogger(__name__)

_DUMMY_HASH = hash_password("payintel-dummy-password-not-used")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_user_by_email(session: Session, email: str) -> AuthUser | None:
    return session.scalar(select(AuthUser).where(AuthUser.email == normalize_email(email)))


def get_user(session: Session, user_id: str) -> AuthUser | None:
    return session.get(AuthUser, user_id)


def count_active_admins(session: Session, exclude_user_id: str | None = None) -> int:
    stmt = (
        select(func.count())
        .select_from(AuthUser)
        .where(
            AuthUser.role == "admin",
            AuthUser.status == "active",
        )
    )
    if exclude_user_id:
        stmt = stmt.where(AuthUser.user_id != exclude_user_id)
    return int(session.scalar(stmt) or 0)


def create_user(
    session: Session,
    *,
    name: str,
    email: str,
    password: str,
    role: str = "user",
    actor_id: str | None = None,
) -> AuthUser:
    user = AuthUser(
        user_id=new_token()[:32],
        name=normalize_name(name),
        email=normalize_email(email),
        password_hash=hash_password(password),
        role="admin" if role == "admin" else "user",
        status="active",
        created_at=_utcnow(),
    )
    session.add(user)
    session.flush()
    record_audit(
        session,
        EVENT_SIGNUP,
        actor_id=actor_id or user.user_id,
        resource_id=user.user_id,
        metadata={"email": user.email, "role": user.role},
    )
    return user


def issue_session(
    session: Session,
    user: AuthUser,
    settings: Settings,
    user_agent: str | None = None,
) -> str:
    raw = new_token()
    now = _utcnow()
    row = AuthSession(
        session_id=new_token()[:32],
        user_id=user.user_id,
        token_hash=hash_token(raw),
        expires_at=now + timedelta(hours=settings.session_ttl_hours),
        created_at=now,
        last_seen_at=now,
        user_agent=(user_agent or "")[:240] or None,
    )
    session.add(row)
    user.last_login_at = now
    user.last_active_at = now
    return raw


def authenticate(
    session: Session,
    email: str,
    password: str,
    settings: Settings,
    user_agent: str | None = None,
) -> tuple[AuthUser, str] | tuple[None, str]:
    user = get_user_by_email(session, email)
    stored = user.password_hash if user is not None else _DUMMY_HASH
    valid = verify_password(password, stored)
    if user is None or not valid:
        return None, "invalid"
    if user.status != "active":
        return None, "suspended"
    token = issue_session(session, user, settings, user_agent)
    record_audit(
        session,
        EVENT_LOGIN,
        actor_id=user.user_id,
        resource_id=user.user_id,
        metadata={"email": user.email},
    )
    return user, token


def resolve_session(
    session: Session,
    token: str | None,
) -> tuple[AuthUser | None, str]:
    if not token:
        return None, "missing"
    row = session.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    if row is None or row.revoked_at is not None:
        return None, "invalid"
    now = _utcnow()
    if row.expires_at <= now:
        return None, "expired"
    user = session.get(AuthUser, row.user_id)
    if user is None or user.status != "active":
        return None, "invalid"
    if not user.last_active_at or (now - user.last_active_at).total_seconds() > 300:
        user.last_active_at = now
        row.last_seen_at = now
    return user, "ok"


def revoke_session(session: Session, token: str | None, actor_id: str | None) -> None:
    if not token:
        return
    row = session.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    if row is None or row.revoked_at is not None:
        return
    row.revoked_at = _utcnow()
    record_audit(session, EVENT_LOGOUT, actor_id=actor_id or row.user_id, resource_id=row.user_id)


def revoke_user_sessions(session: Session, user_id: str) -> None:
    now = _utcnow()
    rows = session.scalars(
        select(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
    )
    for row in rows:
        row.revoked_at = now


def request_password_reset(
    session: Session,
    email: str,
    settings: Settings,
    sender: EmailSender,
) -> None:
    user = get_user_by_email(session, email)
    record_audit(
        session,
        EVENT_PASSWORD_RESET_REQUEST,
        metadata={"requested": True},
    )
    if user is None or user.status != "active":
        return
    raw = new_token()
    now = _utcnow()
    session.add(
        PasswordResetToken(
            token_id=new_token()[:32],
            user_id=user.user_id,
            token_hash=hash_token(raw),
            expires_at=now + timedelta(minutes=settings.reset_token_ttl_minutes),
            created_at=now,
        )
    )
    link = f"{settings.public_app_url.rstrip('/')}/reset-password?token={raw}"
    sender.send(
        EmailMessage(
            to=user.email,
            subject="Reset your PayIntel AI password",
            body=(
                "Use this link to reset your PayIntel AI password. "
                f"It expires in {settings.reset_token_ttl_minutes} minutes.\n\n{link}\n"
            ),
        )
    )


def reset_password(session: Session, token: str, password: str) -> bool:
    row = session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token))
    )
    now = _utcnow()
    if row is None or row.used_at is not None or row.expires_at <= now:
        return False
    user = session.get(AuthUser, row.user_id)
    if user is None or user.status != "active":
        return False
    user.password_hash = hash_password(password)
    row.used_at = now
    revoke_user_sessions(session, user.user_id)
    record_audit(
        session,
        EVENT_PASSWORD_RESET,
        actor_id=user.user_id,
        resource_id=user.user_id,
        metadata={"reset": True},
    )
    return True


def change_password(session: Session, user: AuthUser, current: str, new_password: str) -> bool:
    if not verify_password(current, user.password_hash):
        return False
    user.password_hash = hash_password(new_password)
    revoke_user_sessions(session, user.user_id)
    return True


def bootstrap_admin(session: Session, settings: Settings) -> None:
    email = normalize_email(settings.bootstrap_admin_email)
    password = settings.bootstrap_admin_password
    if not email or not password:
        return
    existing = session.scalar(
        select(func.count()).select_from(AuthUser).where(AuthUser.role == "admin")
    )
    if existing:
        return
    if get_user_by_email(session, email) is not None:
        return
    create_user(
        session,
        name=settings.bootstrap_admin_name or "PayIntel Admin",
        email=email,
        password=password,
        role="admin",
    )
    logger.info("bootstrap_admin_created")
