"""Async SMTP email service used for OTP delivery.

This service is intentionally decoupled from the auth flow so it can be
swapped (Mailgun, SendGrid, SES) without touching `AuthService`.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings

logger = logging.getLogger(__name__)


_TEMPLATES_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    enable_async=False,
)


def mask_email(email: str) -> str:
    """Return a partially-masked email for safe display (e.g. ``j***@gmail.com``)."""
    try:
        local, domain = email.split("@", 1)
    except ValueError:
        return "***"
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + ("*" * (len(local) - 2)) + local[-1]
    # Also mask the domain second-level partially: gmail.com -> g****.com
    domain_parts = domain.split(".")
    if domain_parts:
        head = domain_parts[0]
        masked_head = head[0] + ("*" * max(len(head) - 1, 1)) if head else "*"
        domain_parts[0] = masked_head
    return f"{masked_local}@{'.'.join(domain_parts)}"


class EmailServiceError(RuntimeError):
    """Raised when email delivery fails."""


class EmailService:
    """Async email sender backed by aiosmtplib."""

    def __init__(self) -> None:
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.username = settings.SMTP_USERNAME
        self.password = settings.SMTP_PASSWORD
        self.from_addr = settings.SMTP_FROM
        self.from_name = settings.SMTP_FROM_NAME
        self.use_tls = settings.SMTP_USE_TLS
        self.use_ssl = settings.SMTP_USE_SSL
        self.timeout = settings.SMTP_TIMEOUT

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_otp_email(
        self,
        *,
        to_email: str,
        otp: str,
        expire_minutes: int,
        ip_address: Optional[str] = None,
    ) -> None:
        """Render and send the OTP email.

        In ``OTP_EMAIL_DEBUG`` mode the email is logged instead of being sent
        — useful for local development without an SMTP server.
        """
        subject = f"Your {self.from_name} verification code: {otp}"
        context = {
            "app_name": self.from_name,
            "subject": subject,
            "otp": otp,
            "expire_minutes": expire_minutes,
            "requested_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "ip_address": ip_address or "",
            "year": datetime.utcnow().year,
        }
        html_body = _jinja_env.get_template("otp_email.html").render(**context)
        text_body = self._render_plaintext(otp, expire_minutes)

        if settings.OTP_EMAIL_DEBUG or not self.host:
            logger.warning(
                "[OTP_EMAIL_DEBUG] To=%s Subject=%s Code=%s (expires in %d min)",
                to_email,
                subject,
                otp,
                expire_minutes,
            )
            return

        await self._send_message(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _render_plaintext(otp: str, expire_minutes: int) -> str:
        return (
            "Your verification code\n"
            "----------------------\n"
            f"Code: {otp}\n"
            f"This code expires in {expire_minutes} minutes and can only be used once.\n\n"
            "If you didn't request this code, you can safely ignore this email.\n"
        )

    def _build_message(
        self, *, to_email: str, subject: str, html_body: str, text_body: str
    ) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = formataddr((self.from_name, self.from_addr))
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")
        return msg

    async def _send_message(
        self, *, to_email: str, subject: str, html_body: str, text_body: str
    ) -> None:
        # Local import keeps aiosmtplib optional at import-time so the server
        # can boot in OTP_EMAIL_DEBUG mode without the dependency installed.
        try:
            import aiosmtplib  # type: ignore
        except ImportError as exc:  # pragma: no cover - defensive
            raise EmailServiceError(
                "aiosmtplib is required for SMTP delivery. "
                "Install it (`pip install aiosmtplib`) or enable OTP_EMAIL_DEBUG."
            ) from exc

        msg = self._build_message(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

        # Sanity-check the recipient before opening a socket
        if not _RECIPIENT_RE.match(to_email):
            raise EmailServiceError(f"Invalid recipient address: {to_email!r}")

        try:
            await aiosmtplib.send(
                msg,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=self.use_tls and not self.use_ssl,
                use_tls=self.use_ssl,
                timeout=self.timeout,
            )
        except Exception as exc:  # noqa: BLE001 - normalize to EmailServiceError
            logger.exception("Failed to deliver OTP email to %s", to_email)
            raise EmailServiceError(
                "Could not send verification email. Please try again."
            ) from exc


_RECIPIENT_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
