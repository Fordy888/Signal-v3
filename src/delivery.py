"""Email the brief via Resend API with rate-limit-safe retry/backoff."""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import resend

log = logging.getLogger(__name__)
BRISBANE = ZoneInfo("Australia/Brisbane")

# Retry configuration for Resend 429 (rate limit) responses
MAX_RETRIES = 4          # Total attempts = 1 initial + 4 retries
INITIAL_BACKOFF_S = 1.5  # First retry waits 1.5s, then doubles each time
INTER_SEND_DELAY_S = 0.8 # Minimum delay between consecutive sends (pre-emptive throttle)


class DeliveryRejectedError(RuntimeError):
    """The provider definitively rejected the request before accepting an email."""


class DeliveryUncertainError(RuntimeError):
    """The provider outcome is ambiguous and must be retried with the same key."""


def send_brief(
    html_body: str,
    recipient_email: str | None = None,
    subject_override: str | None = None,
    edition_number: int | None = None,
    tags: list[dict[str, str]] | None = None,
    idempotency_key: str | None = None,
    require_message_id: bool = False,
    raise_on_failure: bool = False,
) -> bool | str | None:
    """Send the brief via Resend. Returns True on success, False on failure.

    Implements exponential backoff on 429 (rate limit) responses.
    Will retry up to MAX_RETRIES times before giving up.

    Args:
        html_body: The HTML content of the brief (already fully styled).
        recipient_email: Override recipient. Falls back to RECIPIENT_EMAIL env var.
        subject_override: Full subject line override (e.g. "[PROOF] Signal — Mon 07 Jul").
                          If not set, uses "Signal | Edition XXXX | Day DD Mon".
        edition_number: The edition number to include in the subject line.
        tags: Optional Resend metadata for delivery traceability and recovery.
    """
    api_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("RESEND_FROM_EMAIL", "signal@signal.dtlc.ai")
    recipient = recipient_email or os.environ.get("RECIPIENT_EMAIL")

    if not (api_key and recipient):
        log.error("Email config missing — set RESEND_API_KEY and RECIPIENT_EMAIL")
        if raise_on_failure:
            raise DeliveryRejectedError("email configuration is missing")
        return None

    resend.api_key = api_key

    if subject_override:
        subject = subject_override
    elif edition_number:
        subject = f"DTL Signal | Edition {edition_number:04d} | {datetime.now(BRISBANE).strftime('%A %d %B %Y')}"
    else:
        subject = f"DTL Signal — {datetime.now(BRISBANE).strftime('%a %d %b')}"

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

    payload = {
        "from": f"DTL Signal <{from_email}>",
        "to": [recipient],
        "reply_to": "paul.ford@gmail.com",
        "subject": subject,
        "html": full_html,
    }
    if tags:
        payload["tags"] = tags

    # Retry loop with exponential backoff for rate limiting
    backoff = INITIAL_BACKOFF_S
    for attempt in range(1, MAX_RETRIES + 2):  # +2 because range is exclusive and we start at 1
        try:
            if idempotency_key:
                try:
                    r = resend.Emails.send(payload, {"idempotency_key": idempotency_key})
                except TypeError:
                    r = resend.Emails.send(payload, idempotency_key=idempotency_key)
            else:
                r = resend.Emails.send(payload)
            email_id = r.get("id") if isinstance(r, dict) else getattr(r, "id", None)
            if require_message_id and not email_id:
                raise DeliveryUncertainError("provider response omitted the message ID")
            log.info("Brief sent via Resend (id=%s) to %s", email_id, recipient)
            return email_id or True
        except Exception as e:
            error_msg = str(e).lower()
            is_rate_limit = "too many requests" in error_msg or "429" in error_msg or "rate" in error_msg

            if is_rate_limit and attempt <= MAX_RETRIES:
                log.warning(
                    "Resend rate limited (attempt %d/%d) for %s — backing off %.1fs",
                    attempt, MAX_RETRIES + 1, recipient, backoff
                )
                time.sleep(backoff)
                backoff *= 2  # Exponential backoff: 1.5s → 3s → 6s → 12s
            else:
                # Non-rate-limit error, or exhausted retries
                if is_rate_limit:
                    log.error(
                        "Resend rate limit exhausted after %d attempts for %s: %s",
                        attempt, recipient, e
                    )
                else:
                    log.error("Resend delivery failed for %s: %s", recipient, e)
                if raise_on_failure:
                    if isinstance(e, DeliveryUncertainError):
                        raise
                    try:
                        from resend.exceptions import ResendError

                        code = int(getattr(e, "code", 0) or 0)
                        is_known_rejection = isinstance(e, ResendError) and 400 <= code < 500
                    except (ImportError, TypeError, ValueError):
                        is_known_rejection = False
                    if is_known_rejection:
                        raise DeliveryRejectedError(str(e)) from e
                    raise DeliveryUncertainError(str(e)) from e
                return None

    # Should not reach here, but safety net
    log.error("Resend delivery failed for %s: exhausted all retry attempts", recipient)
    if raise_on_failure:
        raise DeliveryUncertainError("Resend retries exhausted without a confirmed outcome")
    return None
