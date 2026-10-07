import smtplib
from email.message import EmailMessage

from app.core.config import get_settings


def send_verification_email(email: str, token: str) -> bool:
    """Send synchronously; report SMTP failure without exposing message contents."""
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = email
    message["Subject"] = "FSP Platform: verify your email"
    message.set_content(
        "Confirm your FSP Platform email address.\n\n"
        "POST /auth/verify-email with this JSON body:\n"
        f'{{"token": "{token}"}}\n'
    )
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=5) as smtp:
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError):
        return False
    return True
