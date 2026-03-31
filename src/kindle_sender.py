"""
Send an EPUB file to a Kindle email address via Gmail SMTP.

Amazon's Send-to-Kindle service accepts EPUB files sent to
<name>@kindle.com. The sender address must be pre-approved in
the Amazon account's "Personal Document Settings".

Setup:
  1. Enable 2-Step Verification on your Google account.
  2. Create an App Password at https://myaccount.google.com/apppasswords
     (category: Mail, device: Other).
  3. Add your Gmail address to the approved senders list at:
     Amazon → Manage Your Content and Devices → Preferences →
     Personal Document Settings → Approved Personal Document E-mail List.
"""

import logging
import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587


def send_to_kindle(
    epub_path: str,
    title: str,
    gmail_user: str,
    gmail_app_password: str,
    kindle_email: str,
) -> None:
    """
    Email an EPUB file to the Kindle email address.

    Args:
        epub_path:          Local path to the .epub file.
        title:              Article title — used as email subject and attachment name.
        gmail_user:         Gmail address (e.g. you@gmail.com).
        gmail_app_password: Google App Password (not the regular Gmail password).
        kindle_email:       Kindle email address (e.g. you@kindle.com).

    Raises:
        smtplib.SMTPException: On any SMTP-level error.
        FileNotFoundError:     If epub_path does not exist.
    """
    if not os.path.isfile(epub_path):
        raise FileNotFoundError(f"EPUB not found: {epub_path}")

    msg = MIMEMultipart()
    msg["From"] = gmail_user
    msg["To"] = kindle_email
    # Amazon uses the Subject as the document title in some cases; keep it clean.
    msg["Subject"] = title

    # A short body is fine; Amazon ignores it.
    msg.attach(MIMEText("Sent via Notion-to-Kindle sync.", "plain"))

    # Attach the EPUB
    safe_filename = _safe_filename(title) + ".epub"
    with open(epub_path, "rb") as f:
        part = MIMEBase("application", "epub+zip")
        part.set_payload(f.read())

    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment", filename=safe_filename)
    msg.attach(part)

    logger.info(
        "Sending '%s' → %s via %s", title, kindle_email, gmail_user
    )

    with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(gmail_user, gmail_app_password)
        server.sendmail(gmail_user, kindle_email, msg.as_string())

    logger.info("Sent '%s' successfully", title)


def _safe_filename(title: str) -> str:
    """Strip characters that are invalid in filenames, limit length."""
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    return safe.strip()[:100] or "article"
