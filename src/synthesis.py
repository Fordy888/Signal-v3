"""Synthesise the final DTL Signal brief from scored items via Claude Sonnet."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from anthropic import Anthropic

from .scoring import ScoredItem

log = logging.getLogger(__name__)

BRISBANE = ZoneInfo("Australia/Brisbane")
MAX_RETRIES = 3


def _load_context_yaml(path: str) -> str:
    """Return the context YAML as a string for prompt injection."""
    with open(path, "r") as f:
        # Validate it parses cleanly, then return raw YAML text — the model reads YAML fine
        yaml.safe_load(f)
    with open(path, "r") as f:
        return f.read()


def _load_synthesis_prompt(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def synthesise(
    scored_items: list[ScoredItem],
    context_path: str,
    synthesis_prompt_path: str,
    model: str | None = None,
    edition_number: int = 1,
    edition_type: str = "daily",
) -> str:
    """Produce the HTML brief. Returns the HTML string."""
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model_id = model or os.environ.get("MODEL_SYNTHESIS", "claude-sonnet-4-6")

    context_yaml = _load_context_yaml(context_path)
    template = _load_synthesis_prompt(synthesis_prompt_path)

    items_payload = [s.to_synthesis_payload() for s in scored_items]

    # Inject context and items into the template — Brisbane time
    now = datetime.now(BRISBANE)
    today = now.strftime("%A %d %B %Y")
    timestamp = now.strftime("%Y-%m-%d %H:%M AEST")
    day_name = now.strftime("%A")
    date_formatted = now.strftime("%d %B %Y")
    date_compact = now.strftime("%d.%m.%Y")
    time_str = now.strftime("%H:%M")
    edition_padded = f"{edition_number:04d}"
    edition_stamp = f"PF::SIGNAL-{edition_number:03d} // {date_compact} // {time_str} AEST"

    prompt = (
        template
        .replace("{CONTEXT_MODEL}", context_yaml)
        .replace("{SCORED_ITEMS}", json.dumps(items_payload, indent=2))
        .replace("{DATE}", today)
        .replace("{TIMESTAMP}", timestamp)
        .replace("{ONE_LINE_HEADLINE}", "")  # deprecated, kept for compat
        .replace("{EDITION_NUMBER}", edition_padded)
        .replace("{EDITION_STAMP}", edition_stamp)
        .replace("{DAY_NAME}", day_name)
        .replace("{DATE_FORMATTED}", date_formatted)
        .replace("{DATE_COMPACT}", date_compact)
        .replace("{TIME}", time_str)
    )

    # If no items survived scoring, produce a graceful quiet-day brief
    if not items_payload:
        log.warning("No items survived scoring — producing minimal quiet-day brief")
        prompt += "\n\nNOTE: No items survived the scoring filter today. Produce a minimal edition with Today's Signal thesis noting a quiet day, no Top Signals items, and the Executive Read section providing one strategic interpretation from the Context Model alone."

    # Retry with exponential backoff
    resp = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.messages.create(
                model=model_id,
                max_tokens=16000,  # Raised from 8192 on 27 June 2026 — 8 sections × 2-3 items with structured format needs ~12-14k tokens
                messages=[{"role": "user", "content": prompt}],
            )
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** attempt * 5  # 5s, 10s, 20s
                log.warning("Synthesis attempt %d failed, retrying in %ds: %s", attempt + 1, wait, e)
                time.sleep(wait)
            else:
                log.error("Synthesis failed after %d attempts: %s", MAX_RETRIES, e)
                raise

    # Check stop reason — detect truncation
    stop_reason = getattr(resp, "stop_reason", None)
    if stop_reason == "max_tokens":
        log.warning("Synthesis output was TRUNCATED (hit max_tokens). Email may be incomplete.")

    text_parts: list[str] = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(block.text)
    html = "\n".join(text_parts).strip()

    # --- Key section completeness check with retry ---
    if edition_type == "weekly_wrap":
        has_key_section = ("THE PATTERN" in html and "EXECUTIVE TAKEAWAY" in html)
        section_label = "THE PATTERN + EXECUTIVE TAKEAWAY"
        retry_instruction = "\n\nCRITICAL: Your previous output was missing THE PATTERN BEHIND THE HEADLINES and/or EXECUTIVE TAKEAWAY sections. You MUST include both. Do not truncate."
    else:
        has_key_section = ("EXECUTIVE READ" in html and "What to Watch" in html)
        section_label = "EXECUTIVE READ + What to Watch"
        retry_instruction = "\n\nCRITICAL: Your previous output was missing the EXECUTIVE READ section. You MUST include the full Executive Read box with STRATEGIC INTERPRETATION paragraph and 'What to Watch' bullets. Do not truncate."

    if not has_key_section:
        log.warning("%s incomplete on first attempt — retrying synthesis...", section_label)
        retry_prompt = prompt + retry_instruction
        try:
            retry_resp = client.messages.create(
                model=model_id,
                max_tokens=16000,
                messages=[{"role": "user", "content": retry_prompt}],
            )
            retry_parts: list[str] = []
            for block in retry_resp.content:
                if getattr(block, "type", None) == "text":
                    retry_parts.append(block.text)
            retry_html = "\n".join(retry_parts).strip()
            if edition_type == "weekly_wrap":
                retry_has_key = ("THE PATTERN" in retry_html and "EXECUTIVE TAKEAWAY" in retry_html)
            else:
                retry_has_key = ("EXECUTIVE READ" in retry_html and "What to Watch" in retry_html)
            if retry_has_key:
                log.info("%s retry successful — using retried output.", section_label)
                html = retry_html
                stop_reason = getattr(retry_resp, "stop_reason", None)
            else:
                log.warning("%s retry also incomplete — using original output.", section_label)
        except Exception as e:
            log.warning("%s retry failed: %s — using original output.", section_label, e)

    # Defensive: if model wrapped in markdown fence, strip it
    if html.startswith("```"):
        lines = html.split("\n")
        # Drop opening and closing fence lines
        html = "\n".join(line for line in lines if not line.startswith("```"))

    # Validate completeness — check for key sections and proper HTML closure
    if edition_type == "weekly_wrap":
        has_executive_read_final = "THE PATTERN" in html and "EXECUTIVE TAKEAWAY" in html
    else:
        has_executive_read_final = "EXECUTIVE READ" in html and "What to Watch" in html
    has_closing = "</table>" in html[-200:] if len(html) > 200 else "</table>" in html

    if not has_executive_read_final:
        log.warning("%s is MISSING from output — likely truncated.", section_label)

    # Auto-repair: if HTML is truncated mid-tag, close it cleanly
    if stop_reason == "max_tokens" or not has_closing:
        log.warning("Attempting HTML auto-repair for truncated output.")
        # Remove any partial/broken tag at the end
        # Find the last complete tag closure
        last_close = html.rfind("</td></tr>")
        if last_close > 0:
            html = html[:last_close + len("</td></tr>")]
        # Only append footer if it doesn't already exist (prevents double-footer bug)
        if "Signal learns" not in html:
            html += '''
<tr><td style="padding: 28px 40px 8px 40px;">
<p style="margin: 0 0 12px 0; font-size: 11px; font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace; color: #999; line-height: 1.6;">Signal learns. Every open, every click, every skip trains the next edition.</p>
</td></tr>
<tr><td style="padding: 0 40px 28px 40px;">
<table width="100%" cellpadding="0" cellspacing="0"><tr>
<td><p style="margin: 0; font-size: 9px; font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace; color: #bbb; letter-spacing: 1px;"></p></td>
<td align="right"><p style="margin: 0; font-size: 9px; font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace; color: #bbb; letter-spacing: 1px;">dtlc.ai</p></td>
</tr></table>
</td></tr>'''
        # Always ensure proper HTML closure
        if not html.rstrip().endswith("</table>"):
            html += '''
<tr><td style="height: 4px; background: linear-gradient(90deg, #4ECDC4 0%, #4ECDC4 50%, #E8533A 50%, #E8533A 100%);"></td></tr>
</table>'''
        log.info("HTML auto-repair applied — structure closed cleanly.")

    # Strip any hallucinated "// reply to refine" text
    html = html.replace("// reply to refine", "")

    # ─── POST-SYNTHESIS DATE CORRECTION ─────────────────────────────────
    # The LLM sometimes hallucates the wrong day-of-week in the header date line.
    # Force-correct it to match the computed values from pipeline runtime.
    # Pattern matches any weekday name followed by the date in the header line
    # e.g., "Thursday 10 July 2026 | 06:00 AEST" → "Friday 10 July 2026 | 06:00 AEST"
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    wrong_day_pattern = "|".join(w for w in weekdays if w != day_name)
    # Fix the header date line: any wrong weekday + our date → correct weekday + date
    date_line_pattern = rf'({"|".join(weekdays)})\s+{re.escape(date_formatted)}'
    html = re.sub(date_line_pattern, f'{day_name} {date_formatted}', html)
    log.info("Post-synthesis date correction applied: %s %s", day_name, date_formatted)

    # ─── EDITION COUNTER VERIFICATION ──────────────────────────────────
    # Ensure the edition number appears in the HTML header.
    # The template has "Edition {EDITION_NUMBER}" but the LLM might drop it.
    if f"Edition {edition_padded}" not in html:
        log.warning("Edition counter missing from HTML output — injecting it.")
        # Try to inject after "DTL SIGNAL" text
        dtl_signal_pos = html.find("DTL SIGNAL")
        if dtl_signal_pos > 0:
            # Find the next </td> after DTL SIGNAL and inject edition counter
            next_td = html.find("</td>", dtl_signal_pos)
            if next_td > 0:
                inject_html = f'<td align="right"><p style="margin: 0; font-size: 11px; font-family: \'SF Mono\', \'Fira Code\', \'Courier New\', monospace; color: #999; letter-spacing: 1px;">Edition {edition_padded}</p></td>'
                # Check if there's already a right-aligned td for edition
                if "align=\"right\"" not in html[dtl_signal_pos:dtl_signal_pos+500]:
                    html = html[:next_td + 5] + inject_html + html[next_td + 5:]
                    log.info("Edition counter injected into header.")

    log.info("Synthesis: produced %d chars of HTML (stop_reason=%s, has_executive_read=%s)", len(html), stop_reason, has_executive_read_final)
    return html
