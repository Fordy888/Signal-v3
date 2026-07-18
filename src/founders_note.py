"""Founder's Note generation stage for DTL Signal.

Generates Paul Ford's editorial voice as the opening section of each edition.
Uses the voice reference library and today's scored items to produce one sharp
commercial observation — NOT a summary of the stories below.
"""
from __future__ import annotations

import json
import logging
import os
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from anthropic import Anthropic

log = logging.getLogger(__name__)

BRISBANE = ZoneInfo("Australia/Brisbane")
MAX_RETRIES = 3

# Fallback model if primary fails
FALLBACK_MODELS = ["claude-sonnet-4-5-20250929"]


def _load_voice_reference(root: Path) -> str:
    """Load the Founder's Note voice reference document."""
    voice_path = root / "prompts" / "founders_note_voice.md"
    if not voice_path.exists():
        log.error("Voice reference not found at %s", voice_path)
        return ""
    with open(voice_path, "r") as f:
        content = f.read()
    log.info("Voice reference loaded: %d chars from %s", len(content), voice_path)
    return content


def _build_items_summary(scored_items: list) -> str:
    """Build a concise summary of today's top items for context."""
    summaries = []
    for i, item in enumerate(scored_items[:8]):  # Top 8 items max
        try:
            if hasattr(item, 'raw'):
                headline = getattr(item.raw, 'title', '') or getattr(item.raw, 'headline', '')
                source = getattr(item.raw, 'source', '')
            elif isinstance(item, dict):
                headline = item.get('title', '') or item.get('headline', '')
                source = item.get('source', '')
            else:
                headline = str(item)[:100]
                source = ''

            category = getattr(item, 'category', '') if hasattr(item, 'category') else ''
            score = getattr(item, 'score', 0) if hasattr(item, 'score') else 0

            summaries.append(f"- [{category}] {headline} (source: {source}, score: {score})")
        except Exception as e:
            log.warning("Failed to build summary for item %d: %s", i, e)
            continue

    return "\n".join(summaries) if summaries else "No items available."


def _call_anthropic(client: Anthropic, model_id: str, prompt: str) -> dict[str, Any] | None:
    """Make the API call with retries. Returns parsed dict or None."""
    resp = None
    for attempt in range(MAX_RETRIES):
        try:
            log.info("Founder's Note API call attempt %d/%d with model '%s'",
                     attempt + 1, MAX_RETRIES, model_id)
            resp = client.messages.create(
                model=model_id,
                max_tokens=1000,
                timeout=60.0,
                messages=[{"role": "user", "content": prompt}],
            )
            break
        except Exception as e:
            log.warning("Founder's Note attempt %d/%d failed: %s: %s",
                        attempt + 1, MAX_RETRIES, type(e).__name__, e)
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** attempt * 3
                log.info("Retrying in %ds...", wait)
                time.sleep(wait)
            else:
                log.error("Founder's Note generation failed after %d attempts with model '%s'",
                          MAX_RETRIES, model_id)
                return None

    if not resp:
        return None

    # Extract text from response
    text = ""
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            text += block.text

    # Parse JSON response
    text = text.strip()
    log.info("Founder's Note raw response length: %d chars", len(text))

    # Strip markdown fencing if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(line for line in lines if not line.startswith("```"))
        text = text.strip()

    try:
        result = json.loads(text)
        return result
    except json.JSONDecodeError as e:
        log.warning("Failed to parse Founder's Note JSON directly: %s", e)
        # Attempt to extract from malformed response
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(text[start:end])
                log.info("Extracted JSON from malformed response (offset %d-%d)", start, end)
                return result
        except Exception:
            pass
        log.error("Could not parse Founder's Note response. Raw (first 500): %s", text[:500])
        return None


def generate_founders_note(
    scored_items: list,
    edition_number: int,
    root: Path | None = None,
) -> dict[str, Any]:
    """Generate the Founder's Note using Paul Ford's voice.

    Returns:
        dict with keys: headline, body, word_count, generated_at
        Returns empty dict on failure.
    """
    if root is None:
        root = Path(__file__).resolve().parent.parent

    # Pre-flight checks with detailed logging
    log.info("=== Founder's Note Stage 3b START ===")
    log.info("Edition: %04d | Items available: %d | Root: %s",
             edition_number, len(scored_items), root)

    # Check API key
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        log.error("ANTHROPIC_API_KEY is empty or not set — cannot generate Founder's Note")
        return {}
    log.info("ANTHROPIC_API_KEY present: %d chars (starts with '%s...')",
             len(api_key), api_key[:8])

    voice_reference = _load_voice_reference(root)
    if not voice_reference:
        log.error("Cannot generate Founder's Note without voice reference")
        return {}

    items_summary = _build_items_summary(scored_items)
    log.info("Items summary built: %d lines", len(items_summary.split("\n")))

    today = datetime.now(BRISBANE).strftime("%A %d %B %Y")

    prompt = f"""You are ghostwriting the "Founder's Note" for Paul Ford's DTL Signal newsletter.

## Voice Reference

{voice_reference}

## Today's Intelligence ({today} — Edition {edition_number:04d})

These are the top stories being covered in today's edition:

{items_summary}

## Your Task

Write a Founder's Note that opens today's edition. This is Paul's commercial perspective on the BIGGEST PATTERN emerging from today's intelligence.

CRITICAL RULES:
1. Express ONE clear commercial view — do NOT summarise the stories
2. The stories underneath will support this idea — don't repeat them
3. Tell readers WHY it matters, not WHAT happened
4. Write as an experienced operator speaking to another operator
5. 80–120 words for the body (absolute maximum 120)
6. Headline: strong enough to stand alone, never clickbait, never overstates evidence
7. Headline: maximum 8 words
8. Match Paul's rhythm: short-short-short-LONG-short
9. End with a tight, memorable line
10. Do NOT start with "I think" or any hedging

Return ONLY valid JSON in this exact format:
{{"headline": "Your headline here", "body": "Your body text here"}}

No markdown fencing. No explanation. Just the JSON object."""

    client = Anthropic(api_key=api_key)
    model_id = os.environ.get("MODEL_FOUNDERS_NOTE", "claude-sonnet-4-6")
    log.info("Primary model: '%s'", model_id)

    # Try primary model
    result = _call_anthropic(client, model_id, prompt)

    # If primary fails, try fallback models
    if result is None:
        for fallback in FALLBACK_MODELS:
            log.warning("Trying fallback model: '%s'", fallback)
            result = _call_anthropic(client, fallback, prompt)
            if result is not None:
                log.info("Fallback model '%s' succeeded", fallback)
                break

    if result is None:
        log.error("=== Founder's Note Stage 3b FAILED — all models exhausted ===")
        return {}

    headline = result.get("headline", "").strip()
    body = result.get("body", "").strip()

    if not headline or not body:
        log.error("Founder's Note missing headline or body in parsed result: %s",
                  {k: v[:50] if isinstance(v, str) else v for k, v in result.items()})
        return {}

    word_count = len(body.split())

    # Quality checks
    if word_count > 150:
        log.warning("Founder's Note too long (%d words) — may need trimming", word_count)
    elif word_count > 120:
        log.warning("Founder's Note slightly over target (%d words, max 120)", word_count)

    if len(headline.split()) > 10:
        log.warning("Founder's Note headline too long (%d words)", len(headline.split()))

    # Check for anti-patterns
    anti_patterns = ["I think", "perhaps", "maybe", "in conclusion", "to summarize",
                     "today's edition", "in this edition", "let's explore"]
    for pattern in anti_patterns:
        if pattern.lower() in body.lower():
            log.warning("Founder's Note contains anti-pattern: '%s'", pattern)

    generated_at = datetime.now(BRISBANE).isoformat()

    log.info("=== Founder's Note Stage 3b SUCCESS: '%s' (%d words) ===", headline, word_count)

    return {
        "headline": headline,
        "body": body,
        "word_count": word_count,
        "generated_at": generated_at,
        "edition_number": edition_number,
    }


def inject_founders_note(html: str, note: dict[str, Any]) -> str:
    """Inject the Founder's Note HTML block into the newsletter.

    Inserts after the thesis (italic headline) and before the main content.
    Supports both daily ("Today's Signal") and weekly wrap ("The Week in One Signal")
    HTML structures.

    Args:
        html: The synthesised newsletter HTML.
        note: Dict with 'headline' and 'body' keys.

    Returns:
        Modified HTML with Founder's Note injected.
    """
    headline = note.get("headline", "")
    body = note.get("body", "")
    if not headline or not body:
        log.warning("inject_founders_note called with empty headline or body — skipping")
        return html

    # Build the Founder's Note HTML block
    founders_html = (
        '<tr><td style="padding: 0 40px;"><table width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td style="border-top: 1px solid #e8e8e8;"></td></tr></table></td></tr>\n'
        '<tr><td style="padding: 20px 40px 8px 40px;">\n'
        '<p style="margin: 0 0 4px 0; font-size: 11px; font-family: \'SF Mono\', \'Fira Code\', '
        '\'Courier New\', monospace; color: #E8533A; letter-spacing: 2px; font-weight: 700; '
        'text-transform: uppercase;">FOUNDER\'S NOTE</p>\n'
        f'<p style="margin: 0 0 12px 0; font-size: 18px; font-family: -apple-system, '
        f'BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif; font-weight: 700; '
        f'color: #1a1a1a; line-height: 1.3;">{headline}</p>\n'
        f'<p style="margin: 0; font-size: 15px; font-family: -apple-system, BlinkMacSystemFont, '
        f'\'Segoe UI\', Roboto, sans-serif; line-height: 1.7; color: #333;">{body}</p>\n'
        '</td></tr>\n'
    )

    # Strategy 1: Inject after the thesis (italic paragraph)
    # Works for both daily ("Today's Signal") and weekly wrap ("The Week in One Signal")
    thesis_marker = "font-style: italic;"
    thesis_pos = html.find(thesis_marker)
    if thesis_pos > 0:
        # Find the closing </td></tr> after the thesis paragraph
        close_td = html.find("</td></tr>", thesis_pos)
        if close_td > 0:
            insert_pos = close_td + len("</td></tr>")
            html = html[:insert_pos] + "\n" + founders_html + html[insert_pos:]
            log.info("Founder's Note injected after thesis (Strategy 1: italic marker)")
            return html

    # Strategy 2: Weekly wrap specific — after "The Week in One Signal" section
    week_marker = "The Week in One Signal"
    week_pos = html.find(week_marker)
    if week_pos > 0:
        # Find the next </td></tr> pair after the thesis content
        # Skip past the heading row, then find the thesis content row
        next_close = html.find("</td></tr>", week_pos)
        if next_close > 0:
            # Skip past the heading row to find the actual thesis content row
            second_close = html.find("</td></tr>", next_close + 10)
            if second_close > 0:
                insert_pos = second_close + len("</td></tr>")
                html = html[:insert_pos] + "\n" + founders_html + html[insert_pos:]
                log.info("Founder's Note injected after weekly thesis (Strategy 2: Week in One Signal)")
                return html

    # Strategy 3: Inject after the teal divider (border-top: 2px solid #4ECDC4)
    teal_marker = "border-top: 2px solid #4ECDC4"
    teal_pos = html.find(teal_marker)
    if teal_pos > 0:
        close_tr = html.find("</td></tr>", teal_pos)
        if close_tr > 0:
            insert_pos = close_tr + len("</td></tr>")
            html = html[:insert_pos] + "\n" + founders_html + html[insert_pos:]
            log.info("Founder's Note injected after teal divider (Strategy 3)")
            return html

    # Strategy 4: Weekly wrap — after amber divider (border-top: 2px solid #E6A817)
    amber_marker = "border-top: 2px solid #E6A817"
    amber_pos = html.find(amber_marker)
    if amber_pos > 0:
        close_tr = html.find("</td></tr>", amber_pos)
        if close_tr > 0:
            insert_pos = close_tr + len("</td></tr>")
            html = html[:insert_pos] + "\n" + founders_html + html[insert_pos:]
            log.info("Founder's Note injected after amber divider (Strategy 4: weekly wrap)")
            return html

    # Strategy 5: Inject after "Executive Business Intelligence" text
    ebi_marker = "Executive Business Intelligence"
    ebi_pos = html.find(ebi_marker)
    if ebi_pos > 0:
        close_tr = html.find("</td></tr>", ebi_pos)
        if close_tr > 0:
            insert_pos = close_tr + len("</td></tr>")
            html = html[:insert_pos] + "\n" + founders_html + html[insert_pos:]
            log.info("Founder's Note injected after EBI header (Strategy 5)")
            return html

    log.warning("Could not find injection point for Founder's Note — appending after header")
    # Last resort: inject after first <tr> block
    first_tr_close = html.find("</td></tr>")
    if first_tr_close > 0:
        insert_pos = first_tr_close + len("</td></tr>")
        html = html[:insert_pos] + "\n" + founders_html + html[insert_pos:]

    return html
