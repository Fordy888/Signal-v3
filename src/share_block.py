"""Email-safe share and subscription block with privacy-safe attribution."""
from __future__ import annotations

import logging
import os
import urllib.parse


log = logging.getLogger(__name__)

SUBSCRIBE_URL = os.environ.get("SIGNAL_SUBSCRIBE_URL", "https://dtlc.ai/signal")
SUBSCRIBER_PLACEHOLDER = "{{SUBSCRIBER_HASH}}"
SUBSCRIBER_PLACEHOLDER_ENC = urllib.parse.quote(SUBSCRIBER_PLACEHOLDER, safe="")
FOOTER_SENTINEL = "Signal learns"
SHARE_MARKER = "<!-- signal-share-block -->"


def _tracked_url(edition_padded: str, channel: str) -> str:
    params = {
        "utm_source": "signal",
        "utm_medium": "email",
        "utm_campaign": f"edition_{edition_padded}",
        "utm_content": channel,
    }
    return f"{SUBSCRIBE_URL}?{urllib.parse.urlencode(params)}&r={SUBSCRIBER_PLACEHOLDER}"


def build_share_block(edition_number: int) -> str:
    edition_padded = f"{edition_number:04d}"
    email_url = _tracked_url(edition_padded, "share_email")
    linkedin_target = _tracked_url(edition_padded, "share_linkedin")
    forwarded_url = _tracked_url(edition_padded, "forwarded_subscribe")

    subject = "Thought you might value DTL Signal"
    body = (
        "Hi,\n\n"
        "I receive DTL Signal, a concise executive intelligence briefing covering "
        "the business implications behind developments in AI, strategy, operations, "
        "people, risk and commercial performance.\n\n"
        "I thought it might be useful to you.\n\n"
        f"You can take a look and subscribe here:\n\n{email_url}\n"
    )
    mailto = (
        "mailto:?subject="
        + urllib.parse.quote(subject)
        + "&body="
        + urllib.parse.quote(body)
    )
    linkedin = (
        "https://www.linkedin.com/sharing/share-offsite/?url="
        + urllib.parse.quote(linkedin_target, safe="")
    )

    return f'''{SHARE_MARKER}
<tr><td style="padding:24px 40px 4px 40px;">
<table width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #e8e8e8;"><tr><td style="padding-top:20px;">
<p style="margin:0 0 6px 0;font-size:14px;font-weight:600;color:#1a1a1a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;">Know one executive who would value this?</p>
<p style="margin:0 0 14px 0;font-size:13px;color:#555;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;">
<a href="{mailto}" style="color:#E8533A;text-decoration:none;font-weight:600;">Share DTL Signal by email &rarr;</a>
&nbsp;&nbsp;·&nbsp;&nbsp;
<a href="{linkedin}" target="_blank" style="color:#E8533A;text-decoration:none;font-weight:600;">Share on LinkedIn &rarr;</a>
</p>
<p style="margin:0;font-size:12px;color:#6B7280;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;">Forwarded this edition?
<a href="{forwarded_url}" target="_blank" style="color:#E8533A;text-decoration:underline;font-weight:600;">Subscribe here &rarr;</a></p>
</td></tr></table>
</td></tr>
'''


def inject_share_block(html: str, edition_number: int) -> str:
    """Insert once before the legacy system footer, or the outer closing table."""
    if SHARE_MARKER in html:
        return html
    block = build_share_block(edition_number)
    sentinel_pos = html.find(FOOTER_SENTINEL)
    if sentinel_pos != -1:
        row_pos = html.rfind("<tr>", 0, sentinel_pos)
        if row_pos != -1:
            return html[:row_pos] + block + html[row_pos:]
    close_pos = html.rfind("</table>")
    if close_pos != -1:
        return html[:close_pos] + block + html[close_pos:]
    log.warning("Share block NOT injected — no safe insertion point found")
    return html


def personalise_share_for_subscriber(html: str, subscriber_hash: str) -> str:
    """Replace raw and URL-encoded placeholders with a precomputed opaque hash."""
    return html.replace(SUBSCRIBER_PLACEHOLDER, subscriber_hash).replace(
        SUBSCRIBER_PLACEHOLDER_ENC, subscriber_hash
    )
