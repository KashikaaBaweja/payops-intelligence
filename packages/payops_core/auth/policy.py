from __future__ import annotations

import re
from dataclasses import dataclass

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128
NAME_MIN = 2
NAME_MAX = 80
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")


@dataclass(frozen=True)
class PasswordIssue:
    code: str
    message: str
    ok: bool


def normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def normalize_name(value: str | None) -> str:
    return " ".join((value or "").split())


def evaluate_password(password: str, min_length: int = PASSWORD_MIN_LENGTH) -> list[PasswordIssue]:
    value = password or ""
    return [
        PasswordIssue("length", f"At least {min_length} characters", len(value) >= min_length),
        PasswordIssue("upper", "One uppercase letter", any(ch.isupper() for ch in value)),
        PasswordIssue("lower", "One lowercase letter", any(ch.islower() for ch in value)),
        PasswordIssue("number", "One number", any(ch.isdigit() for ch in value)),
        PasswordIssue("special", "One special character", bool(SPECIAL_RE.search(value))),
    ]


def password_errors(password: str, min_length: int = PASSWORD_MIN_LENGTH) -> list[str]:
    if len(password or "") > PASSWORD_MAX_LENGTH:
        return ["Password is too long."]
    return [item.message for item in evaluate_password(password, min_length) if not item.ok]


def validate_signup(
    name: str,
    email: str,
    password: str,
    confirm: str,
    min_length: int = PASSWORD_MIN_LENGTH,
) -> list[str]:
    errors: list[str] = []
    clean_name = normalize_name(name)
    clean_email = normalize_email(email)
    if len(clean_name) < NAME_MIN or len(clean_name) > NAME_MAX:
        errors.append("Enter your full name.")
    if not EMAIL_RE.match(clean_email):
        errors.append("Enter a valid email address.")
    if password != confirm:
        errors.append("Passwords do not match.")
    errors.extend(password_errors(password, min_length))
    return errors
