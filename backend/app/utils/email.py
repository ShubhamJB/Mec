"""
Email sending utility.

Uses aiosmtplib when SMTP credentials are configured.
Falls back to console logging in development (SMTP_HOST not set).
"""
from __future__ import annotations

import logging

from app.core.config import settings

log = logging.getLogger(__name__)


async def send_email(
    *,
    to: str,
    subject: str,
    html_body: str,
) -> None:
    """Send an email. Stubs to console log when SMTP is not configured."""
    if not settings.SMTP_HOST or settings.SMTP_HOST == "smtp.example.com":
        # Dev / stub mode — log to console
        log.info(
            "📧 [STUB EMAIL] To: %s | Subject: %s\n%s",
            to,
            subject,
            html_body,
        )
        return

    try:
        import aiosmtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html"))

        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
            start_tls=True,
        )
    except Exception as exc:
        log.error("Failed to send email to %s: %s", to, exc)
        # Don't raise — email failures should not crash the request


async def send_verification_email(to: str, token: str, full_name: str) -> None:
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    html = f"""
    <p>Hi {full_name},</p>
    <p>Please verify your email address by clicking the link below:</p>
    <p><a href="{verify_url}">Verify Email</a></p>
    <p>This link expires in 24 hours. If you did not create an account, you can safely ignore this email.</p>
    <p>— Find Your Mechanic Team</p>
    """
    await send_email(to=to, subject="Verify your email — Find Your Mechanic", html_body=html)


async def send_password_changed_email(to: str, full_name: str) -> None:
    html = f"""
    <p>Hi {full_name},</p>
    <p>Your password was successfully changed. All existing sessions have been signed out.</p>
    <p>If you did not make this change, please contact support immediately.</p>
    <p>— Find Your Mechanic Team</p>
    """
    await send_email(to=to, subject="Your password was changed — Find Your Mechanic", html_body=html)

