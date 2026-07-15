from __future__ import annotations

import re
import smtplib
from email.message import EmailMessage

import requests
from flask import Flask, current_app

PLACEHOLDER_MAIL_HOSTS = {
    "smtp.example.com",
    "example.com",
    "localhost",
    "127.0.0.1",
}

RESEND_API_URL = "https://api.resend.com/emails"
EMAIL_ONLY_RE = re.compile(r"^[^<>\s@]+@[^<>\s@]+\.[^<>\s@]+$")
NAMED_EMAIL_RE = re.compile(r"^[^<>]+<[^<>\s@]+@[^<>\s@]+\.[^<>\s@]+>$")


def _resend_api_key(app: Flask) -> str:
    return (app.config.get("RESEND_API_KEY") or "").strip()


def _mail_sender(app: Flask) -> str:
    return normalize_mail_sender(
        app.config.get("MAIL_DEFAULT_SENDER") or "",
        app.config.get("APP_NAME", "CheerSteps"),
    )


def normalize_mail_sender(raw: str, app_name: str = "CheerSteps") -> str:
    sender = (raw or "").strip()
    if not sender:
        raise ValueError("MAIL_DEFAULT_SENDER is not set.")

    if (
        (sender.startswith('"') and sender.endswith('"'))
        or (sender.startswith("'") and sender.endswith("'"))
    ):
        sender = sender[1:-1].strip()

    if EMAIL_ONLY_RE.match(sender) or NAMED_EMAIL_RE.match(sender):
        return sender

    if "@" in sender and "<" not in sender:
        local, domain = sender.rsplit("@", 1)
        local = local.strip()
        domain = domain.strip()
        if local and domain:
            return f"{local}@{domain}"

    raise ValueError(
        "MAIL_DEFAULT_SENDER must look like onboarding@resend.dev "
        f'or {app_name} <onboarding@resend.dev>.'
    )


def _mail_server(app: Flask) -> str:
    return (app.config.get("MAIL_SERVER") or "").strip().lower()


def resend_configured(app: Flask | None = None) -> bool:
    app = app or current_app
    if not _resend_api_key(app):
        return False
    try:
        normalize_mail_sender(
            app.config.get("MAIL_DEFAULT_SENDER") or "",
            app.config.get("APP_NAME", "CheerSteps"),
        )
        return True
    except ValueError:
        return False


def smtp_configured(app: Flask | None = None) -> bool:
    app = app or current_app
    server = _mail_server(app)
    username = (app.config.get("MAIL_USERNAME") or "").strip()
    password = (app.config.get("MAIL_PASSWORD") or "").strip()

    if not server or not username or not password:
        return False
    if server in PLACEHOLDER_MAIL_HOSTS or server.endswith(".example.com"):
        return False
    try:
        normalize_mail_sender(
            app.config.get("MAIL_DEFAULT_SENDER") or "",
            app.config.get("APP_NAME", "CheerSteps"),
        )
    except ValueError:
        return False
    return True


def mail_configured(app: Flask | None = None) -> bool:
    app = app or current_app
    return resend_configured(app) or smtp_configured(app)


def send_via_resend(
    to: str, subject: str, body_text: str, body_html: str | None = None
) -> None:
    app = current_app
    payload = {
        "from": _mail_sender(app),
        "to": [to],
        "subject": subject,
        "text": body_text,
    }
    if body_html:
        payload["html"] = body_html

    response = requests.post(
        RESEND_API_URL,
        headers={
            "Authorization": f"Bearer {_resend_api_key(app)}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=int(app.config.get("MAIL_TIMEOUT", 10)),
    )
    if not response.ok:
        detail = response.text[:300]
        if response.status_code == 422 and "from" in detail.lower():
            raise RuntimeError(
                "Resend rejected the sender address. Set MAIL_DEFAULT_SENDER to "
                "onboarding@resend.dev or CheerSteps <onboarding@resend.dev> "
                "without quotes in Render."
            )
        if response.status_code == 403 and "verify a domain" in detail.lower():
            raise RuntimeError(
                "Resend test mode only allows sending to your own Resend account email. "
                "Verify cheersteps.com at resend.com/domains, add the DNS records in "
                "Cloudflare, then set MAIL_DEFAULT_SENDER to "
                "CheerSteps <noreply@cheersteps.com>."
            )
        raise RuntimeError(f"Resend API error ({response.status_code}): {detail}")


def send_via_smtp(
    to: str, subject: str, body_text: str, body_html: str | None = None
) -> None:
    app = current_app
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = _mail_sender(app)
    message["To"] = to
    message.set_content(body_text)
    if body_html:
        message.add_alternative(body_html, subtype="html")

    username = app.config.get("MAIL_USERNAME") or None
    password = app.config.get("MAIL_PASSWORD") or None
    use_tls = app.config.get("MAIL_USE_TLS", True)
    port = int(app.config.get("MAIL_PORT", 587))
    server_host = app.config["MAIL_SERVER"]
    timeout = int(app.config.get("MAIL_TIMEOUT", 10))

    if port == 465:
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(server_host, port, timeout=timeout)
    else:
        smtp = smtplib.SMTP(server_host, port, timeout=timeout)
        if use_tls:
            smtp.starttls()

    with smtp:
        if username and password:
            smtp.login(username, password)
        smtp.send_message(message)


def send_email(to: str, subject: str, body_text: str, body_html: str | None = None) -> None:
    app = current_app
    if not mail_configured(app):
        raise RuntimeError("Email is not configured.")

    if resend_configured(app):
        send_via_resend(to, subject, body_text, body_html)
        return

    send_via_smtp(to, subject, body_text, body_html)


def send_password_reset_email(to: str, reset_url: str) -> None:
    app_name = current_app.config.get("APP_NAME", "CheerSteps")
    subject = f"Reset your {app_name} password"
    body_text = (
        f"You asked to reset your {app_name} password.\n\n"
        f"Open this link within 1 hour:\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )
    body_html = (
        f"<p>You asked to reset your <strong>{app_name}</strong> password.</p>"
        f'<p><a href="{reset_url}">Reset your password</a></p>'
        "<p>This link expires in 1 hour. If you did not request this, you can ignore this email.</p>"
    )
    send_email(to, subject, body_text, body_html)
