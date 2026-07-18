"""Signal Strength Gauge — email-compatible gauge injection for DTL Signal.

Generates the gauge HTML block for each content item in the edition.
The gauge appears after each item's content, before the divider.

Feature flag: ENABLE_GAUGE env var
  - "off" (default): gauge not injected
  - "proof": gauge injected only in --proof mode
  - "selected": gauge injected for specific editions (comma-separated list in GAUGE_EDITIONS)
  - "production": gauge injected in all editions

The gauge uses a subscriber placeholder {{SUBSCRIBER_HASH}} that must be
replaced per-subscriber at delivery time.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import urllib.parse
from typing import Any

log = logging.getLogger(__name__)

# ─── Configuration ──────────────────────────────────────────────────────────
GAUGE_BASE_URL = os.environ.get("GAUGE_BASE_URL", "https://dtlc.ai/api/gauge")
SUBSCRIBER_PLACEHOLDER = "{{SUBSCRIBER_HASH}}"

# Score labels and colours
GAUGE_SCORES = [
    {"score": 1, "label": "Yawn", "color": "#9CA3AF"},   # grey
    {"score": 2, "label": "Noted", "color": "#3B82F6"},   # blue
    {"score": 3, "label": "Interesting", "color": "#F59E0B"},  # amber
    {"score": 4, "label": "Wow", "color": "#F97316"},     # orange
    {"score": 5, "label": "Boom", "color": "#EF4444"},    # red
]


def is_gauge_enabled(mode: str, edition_number: int) -> bool:
    """Check if the gauge should be injected based on feature flag and mode."""
    flag = os.environ.get("ENABLE_GAUGE", "off").lower().strip()

    if flag == "off":
        return False
    elif flag == "proof":
        return mode == "proof"
    elif flag == "selected":
        allowed = os.environ.get("GAUGE_EDITIONS", "")
        allowed_list = [e.strip() for e in allowed.split(",") if e.strip()]
        return str(edition_number) in allowed_list
    elif flag == "production":
        return True
    else:
        log.warning("Unknown ENABLE_GAUGE value '%s' — defaulting to off", flag)
        return False


def generate_gauge_html(
    edition_number: int,
    item_index: int,
    category: str = "",
    item_title: str = "",
    item_type: str = "",
) -> str:
    """Generate the email-safe gauge HTML for a single item.

    Args:
        edition_number: The edition number (e.g., 15)
        item_index: The 1-based index of the item in the edition
        category: The business category (e.g., "Strategy & Leadership")
        item_title: Descriptive metadata only — not used for identity
        item_type: ACT, WATCH, or NOTE

    Returns:
        HTML string for the gauge block (table-based, email-safe)
    """
    edition_padded = f"{edition_number:04d}"

    # Build the gauge cells
    cells = []
    for g in GAUGE_SCORES:
        # Build URL with all parameters (exclude subscriber hash from encoding)
        params = {
            "s": str(g["score"]),
            "e": edition_padded,
            "i": str(item_index),
        }
        if category:
            params["c"] = category
        if item_title:
            params["t"] = item_title[:80]  # Truncate title for URL safety
        if item_type:
            params["type"] = item_type

        # Append subscriber hash placeholder without URL-encoding the braces
        encoded_params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = f"{GAUGE_BASE_URL}?{encoded_params}&h={SUBSCRIBER_PLACEHOLDER}"

        # Each cell is a clickable link styled as a gauge segment
        cell = (
            f'<td align="center" style="width: 20%;">'
            f'<a href="{url}" target="_blank" '
            f'style="display: block; text-decoration: none; padding: 4px 2px;">'
            f'<span style="display: inline-block; width: 18px; height: 18px; '
            f'border-radius: 50%; background-color: {g["color"]}; '
            f'border: 1.5px solid {g["color"]}; opacity: 0.85;"></span>'
            f'<br/>'
            f'<span style="font-size: 9px; font-family: \'SF Mono\', \'Fira Code\', '
            f'\'Courier New\', monospace; color: {g["color"]}; '
            f'letter-spacing: 0.3px; line-height: 1.6;">{g["label"]}</span>'
            f'</a></td>'
        )
        cells.append(cell)

    gauge_row = "\n".join(cells)

    # Full gauge block wrapped in a table row — compact design
    gauge_html = f'''<tr><td style="padding: 6px 40px 2px 40px;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color: #fafafa; border-radius: 3px; border: 1px solid #f0f0f0;">
<tr><td style="padding: 6px 8px 0 8px;">
<p style="margin: 0; font-size: 9px; font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace; color: #bbb; letter-spacing: 0.8px; text-align: center;">HOW STRONG IS THIS SIGNAL?</p>
</td></tr>
<tr><td style="padding: 2px 6px 6px 6px;">
<table width="100%" cellpadding="0" cellspacing="0"><tr>
{gauge_row}
</tr></table>
</td></tr>
</table>
</td></tr>'''

    return gauge_html


def inject_gauge_into_html(
    html: str,
    scored_items: list,
    edition_number: int,
) -> str:
    """Inject gauge blocks after each content item in the synthesised HTML.

    The gauge is inserted after each item's content (after the Signal: line)
    and before the item divider.

    Args:
        html: The full synthesised HTML
        scored_items: List of ScoredItem objects (for category/type metadata)
        edition_number: The edition number

    Returns:
        HTML with gauge blocks injected after each item
    """
    # Strategy: Find each item block by looking for the item structure pattern.
    # Items have: ACT/WATCH/NOTE pill → category → headline → what happened → why it matters → signal
    # After the last <p> of each item (the Signal: line), inject the gauge before the divider.

    # Pattern: find the ACT|WATCH|NOTE badges to identify item starts
    item_pattern = re.compile(
        r'(<span[^>]*>(?:ACT|WATCH|NOTE)</span>)',
        re.IGNORECASE
    )

    # Find all item positions
    item_matches = list(item_pattern.finditer(html))

    if not item_matches:
        log.warning("No items found in HTML for gauge injection")
        return html

    log.info("Found %d items in HTML for gauge injection", len(item_matches))

    # Work backwards so insertion positions don't shift
    insertions = []
    for idx, match in enumerate(item_matches):
        item_index = idx + 1  # 1-based

        # Extract the item type (ACT/WATCH/NOTE) from the badge
        badge_text = re.search(r'>(ACT|WATCH|NOTE)<', match.group(0), re.IGNORECASE)
        item_type = badge_text.group(1).upper() if badge_text else ""

        # Get category from scored_items if available
        category = ""
        if idx < len(scored_items):
            item = scored_items[idx]
            if hasattr(item, 'raw') and hasattr(item.raw, 'category'):
                category = item.raw.category
            elif isinstance(item, dict):
                category = item.get('category', '')

        # Get title from scored_items
        item_title = ""
        if idx < len(scored_items):
            item = scored_items[idx]
            if hasattr(item, 'raw') and hasattr(item.raw, 'title'):
                item_title = item.raw.title
            elif isinstance(item, dict):
                item_title = item.get('title', '')

        # Find the end of this item's content block
        # Look for the next item divider (thin line) or next item start
        start_pos = match.start()

        # Find the divider after this item
        # Divider pattern: <tr><td style="padding: 8px 40px;">...<td style="border-top: 1px solid #e8e8e8;">
        divider_pattern = re.compile(
            r'<tr><td[^>]*padding:\s*8px\s+40px[^>]*>.*?border-top:\s*1px\s+solid\s+#e8e8e8.*?</tr>',
            re.DOTALL
        )

        # Search for divider after current item start
        divider_match = divider_pattern.search(html, start_pos + 100)

        if divider_match:
            # If there's a next item, make sure the divider is before it
            if idx + 1 < len(item_matches):
                next_item_pos = item_matches[idx + 1].start()
                if divider_match.start() < next_item_pos:
                    insert_pos = divider_match.start()
                else:
                    # No divider between items — insert before next item's <tr>
                    # Find the <tr> that contains the next item
                    tr_before_next = html.rfind("<tr>", start_pos, next_item_pos)
                    insert_pos = tr_before_next if tr_before_next > start_pos else next_item_pos
            else:
                # Last item — insert before the divider
                insert_pos = divider_match.start()
        else:
            # No divider found — look for EXECUTIVE READ section
            exec_read_pos = html.find("EXECUTIVE READ", start_pos)
            if exec_read_pos > 0:
                # Find the <tr> before EXECUTIVE READ
                tr_before_exec = html.rfind("<tr>", start_pos, exec_read_pos)
                insert_pos = tr_before_exec if tr_before_exec > start_pos else exec_read_pos
            else:
                # Fallback: skip this item
                log.warning("Cannot find insertion point for gauge after item %d", item_index)
                continue

        # Generate the gauge HTML
        gauge_html = generate_gauge_html(
            edition_number=edition_number,
            item_index=item_index,
            category=category,
            item_title=item_title,
            item_type=item_type,
        )

        insertions.append((insert_pos, gauge_html))

    # Apply insertions in reverse order (so positions don't shift)
    for pos, gauge in sorted(insertions, key=lambda x: x[0], reverse=True):
        html = html[:pos] + "\n" + gauge + "\n" + html[pos:]

    log.info("Gauge injected after %d items", len(insertions))
    return html


def personalise_gauge_for_subscriber(html: str, subscriber_email: str) -> str:
    """Replace the subscriber placeholder with a hashed identifier.

    Uses SHA-256 of the email to create a privacy-safe subscriber hash.
    This is called per-subscriber at delivery time.

    Args:
        html: HTML containing {{SUBSCRIBER_HASH}} placeholders
        subscriber_email: The subscriber's email address

    Returns:
        HTML with subscriber hash filled in
    """
    if SUBSCRIBER_PLACEHOLDER not in html:
        return html

    # Create a privacy-safe hash from the email
    email_normalised = subscriber_email.lower().strip()
    subscriber_hash = hashlib.sha256(email_normalised.encode()).hexdigest()[:12]

    return html.replace(SUBSCRIBER_PLACEHOLDER, subscriber_hash)
