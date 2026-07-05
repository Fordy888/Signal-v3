"""Email the brief via Resend API."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import resend

log = logging.getLogger(__name__)
BRISBANE = ZoneInfo("Australia/Brisbane")


def send_brief(
    html_body: str,
    recipient_email: str | None = None,
    subject_override: str | None = None,
) -> bool:
    """Send the brief via Resend. Returns True on success, False on failure.

    Args:
        html_body: The HTML content of the brief (already fully styled).
        recipient_email: Override recipient. Falls back to RECIPIENT_EMAIL env var.
        subject_override: Full subject line override (e.g. "[PROOF] Signal — Mon 07 Jul").
                          If not set, uses "Signal — {date}".
    """
    api_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("RESEND_FROM_EMAIL", "signal@signal.dtlc.ai")
    recipient = recipient_email or os.environ.get("RECIPIENT_EMAIL")

    if not (api_key and recipient):
        log.error("Email config missing — set RESEND_API_KEY and RECIPIENT_EMAIL")
        return False

    resend.api_key = api_key

    subject = subject_override or f"Signal — {datetime.now(BRISBANE).strftime('%a %d %b')}"

    # The synthesis prompt produces fully-styled HTML including DOCTYPE,
    # head, and body. If the html_body already contains <!DOCTYPE or <html,
    # send it as-is. Otherwise wrap it in a basic shell.
    if "<!DOCTYPE" in html_body or "<html" in html_body:
        full_html = html_body
    else:
        full_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body>
{html_body}
</body></html>"""

    try:
        r = resend.Emails.send({
            "from": f"Signal <{from_email}>",
            "to": [recipient],
            "subject": subject,
            "html": full_html,
        })
        email_id = r.get("id") if isinstance(r, dict) else getattr(r, "id", None)
        log.info("Brief sent via Resend (id=%s) to %s", email_id, recipient)
        return True
    except Exception as e:
        log.error("Resend delivery failed: %s", e)
        return False
