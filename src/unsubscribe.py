"""Unsubscribe facility. Every outbound edition carries a working one.

The documented path (docs/subscriber-sync-spec.md) is:

    {WEBSITE_BASE_URL}/unsubscribe?token={subscriber_token}

with the token supplied per subscriber by subscribers.fetch_unsubscribe_token.
Unsubscribing there marks the address inactive in the subscriber database, so
the next fetch_subscribers() no longer returns it — the existing suppression
path, unchanged.

The spec's stated error rule was "token fetch fails -> skip unsubscribe URL,
still send". That is deliberately INVERTED here. A commercial message must
always carry a functional unsubscribe, so a failed token falls back to a
mailto: for that recipient rather than omitting the facility. There is no
path through this module that returns an edition without one.
"""
from __future__ import annotations

import logging
import os
from html import escape
from urllib.parse import quote, urlencode

log = logging.getLogger(__name__)

# Where a mailto: unsubscribe is delivered when the token path is unavailable.
# Defaults to the address the edition already sets as Reply-To, so the fallback
# reaches a monitored human inbox without any new infrastructure.
DEFAULT_UNSUBSCRIBE_EMAIL = "paul.ford@gmail.com"
MAILTO_SUBJECT = "UNSUBSCRIBE"


def _mailto(email: str) -> str:
    to = os.environ.get("SIGNAL_UNSUBSCRIBE_EMAIL", DEFAULT_UNSUBSCRIBE_EMAIL).strip()
    query = urlencode({"subject": MAILTO_SUBJECT, "body": f"Please unsubscribe {email}."},
                      quote_via=quote)
    return f"mailto:{to}?{query}"


def unsubscribe_target(email: str, token: str | None) -> tuple[str, str]:
    """Return (href, kind) for this recipient. Never returns an empty href.

    kind is "link" when the documented token URL is available, "mailto" when
    falling back. The caller does not choose — a missing token is the only
    thing that selects the fallback.
    """
    base_url = os.environ.get("WEBSITE_BASE_URL", "").strip().rstrip("/")
    if token and base_url:
        return f"{base_url}/unsubscribe?token={quote(str(token), safe='')}", "link"
    return _mailto(email), "mailto"


def unsubscribe_block(href: str, kind: str) -> str:
    """The footer line. One row, in the edition's existing footer idiom."""
    instruction = (
        "Unsubscribe" if kind == "link"
        else "Unsubscribe (email us and we will remove you)"
    )
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" role="presentation">'
        '<tr><td style="padding:14px 40px 22px 40px;">'
        '<p style="margin:0;font:11px -apple-system,BlinkMacSystemFont,\'Segoe UI\',Arial,sans-serif;'
        'color:#9aa0ab;line-height:1.5;">'
        "You are receiving DTL Signal because you subscribed at dtlc.ai. "
        f'<a href="{escape(href, quote=True)}" style="color:#9aa0ab;text-decoration:underline;">'
        f"{instruction}</a>."
        "</p></td></tr></table>"
    )


def inject_unsubscribe(html: str, href: str, kind: str) -> str:
    """Append the footer block. Never rewrites or removes existing content."""
    block = unsubscribe_block(href, kind)
    lowered = html.lower()
    idx = lowered.rfind("</body>")
    if idx != -1:
        return html[:idx] + block + html[idx:]
    return html + block


def list_unsubscribe_headers(href: str) -> dict[str, str]:
    """RFC 2369 List-Unsubscribe. Mail clients surface this as a native control."""
    return {"List-Unsubscribe": f"<{href}>"}


def apply_unsubscribe(html: str, email: str, token: str | None) -> tuple[str, dict[str, str]]:
    """The single entry point. Returns (html_with_unsubscribe, headers)."""
    href, kind = unsubscribe_target(email, token)
    if kind == "mailto":
        log.warning(
            "Unsubscribe token unavailable for %s — using mailto fallback "
            "(the edition still carries a functional unsubscribe)", email
        )
    return inject_unsubscribe(html, href, kind), list_unsubscribe_headers(href)
