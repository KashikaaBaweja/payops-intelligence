from __future__ import annotations

from dataclasses import dataclass
from logging import getLogger
from typing import Protocol

from payops_core.config import Settings

logger = getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class NoopEmailSender:
    """Used when SMTP is not configured. Does not pretend the message was delivered."""

    def send(self, message: EmailMessage) -> None:
        logger.info("email_not_sent reason=smtp_unconfigured dest_configured=false")


class SmtpEmailSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, message: EmailMessage) -> None:
        import smtplib
        from email.message import EmailMessage as MimeMessage

        payload = MimeMessage()
        payload["Subject"] = message.subject
        payload["From"] = self._settings.smtp_from or self._settings.smtp_username
        payload["To"] = message.to
        payload.set_content(message.body)
        if self._settings.smtp_use_tls:
            client: smtplib.SMTP = smtplib.SMTP(
                self._settings.smtp_host, self._settings.smtp_port, timeout=20
            )
            try:
                client.starttls()
                if self._settings.smtp_username:
                    client.login(self._settings.smtp_username, self._settings.smtp_password)
                client.send_message(payload)
            finally:
                client.quit()
            return
        with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port, timeout=20) as client:
            if self._settings.smtp_username:
                client.login(self._settings.smtp_username, self._settings.smtp_password)
            client.send_message(payload)


class CapturingEmailSender:
    """Test double. Never used in production."""

    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.messages.append(message)


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.smtp_host.strip():
        return SmtpEmailSender(settings)
    return NoopEmailSender()
