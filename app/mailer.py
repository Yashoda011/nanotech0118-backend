"""Outbound email via SMTP (verification + reset codes).

If SMTP_HOST is empty (local demo default), sending is skipped and callers
fall back to the dev-mailbox code flow. Returns True only when an SMTP
server actually accepted the message.
"""

import smtplib
import ssl
from email.message import EmailMessage

from .config import settings


def send_code(to_email: str, code: str, purpose: str = "verification") -> bool:
    if not settings.SMTP_HOST:
        return False
    msg = EmailMessage()
    msg["Subject"] = f"NanoSphere {purpose} code: {code}"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg.set_content(
        f"Hello,\n\nYour NanoSphere {purpose} code is:\n\n    {code}\n\n"
        "It expires in 15 minutes. If you did not request this, ignore this email.\n\n"
        "- NanoSphere"
    )
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=12) as s:
            s.starttls(context=ssl.create_default_context())
            if settings.SMTP_USER:
                s.login(settings.SMTP_USER, settings.SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception:
        return False
