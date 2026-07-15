from __future__ import annotations

import smtplib
from email.message import EmailMessage

from flask import Flask, current_app


def mail_configured(app: Flask | None = None) -> bool:
    app = app or current_app
    return bool(
        app.config.get("MAIL_SERVER")
        and app.config.get("MAIL_DEFAULT_SENDER")
    )


def send_email(to: str, subject: str, body_text: str, body_html: str | None = None) -> None:
    app = current_app
    if not mail_configured(app):
        raise RuntimeError("Email is not configured.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = app.config["MAIL_DEFAULT_SENDER"]
    message["To"] = to
    message.set_content(body_text)
    if body_html:
        message.add_alternative(body_html, subtype="html")

    username = app.config.get("MAIL_USERNAME") or None
    password = app.config.get("MAIL_PASSWORD") or None
    use_tls = app.config.get("MAIL_USE_TLS", True)

    with smtplib.SMTP(app.config["MAIL_SERVER"], app.config.get("MAIL_PORT", 587)) as smtp:
        if use_tls:
            smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(message)


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
