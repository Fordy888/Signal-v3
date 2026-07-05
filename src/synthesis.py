"""Synthesise the final DTL Signal brief from scored items via Claude Sonnet."""
from __future__ import annotations

import json
import logging
import os
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

    prompt = (
        template
        .replace("{CONTEXT_MODEL}", context_yaml)
        .replace("{SCORED_ITEMS}", json.dumps(items_payload, indent=2))
        .replace("{DATE}", today)
        .replace("{TIMESTAMP}", timestamp)
        .replace("{ONE_LINE_HEADLINE}", "")  # the model fills this in
    )

    # If no items survived scoring, produce a graceful "quiet day" brief
    if not items_payload:
        log.warning("No items survived scoring — producing minimal quiet-day brief")
        prompt += "\n\nNOTE: No items survived the scoring filter today. Produce a minimal 'Quiet today across all sections' brief, with Section 9 (DTLc.ai's Take) still attempting one strategic interpretation from the Context Model alone."

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

    # --- Section 9 (DTLc.ai's Take) completeness check with retry ---
    has_section_9_content = ("KEY INSIGHT" in html and "STRATEGIC IMPLICATION" in html and "WATCH FOR" in html)
    if not has_section_9_content:
        log.warning("Section 9 incomplete on first attempt — retrying synthesis with explicit instruction...")
        retry_prompt = prompt + "\n\nCRITICAL: Your previous output was missing Section 9 content. You MUST include the full DTLc.ai's TAKE section with KEY INSIGHT, STRATEGIC IMPLICATION, and WATCH FOR. Do not truncate."
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
            if "KEY INSIGHT" in retry_html and "STRATEGIC IMPLICATION" in retry_html:
                log.info("Section 9 retry successful — using retried output.")
                html = retry_html
                stop_reason = getattr(retry_resp, "stop_reason", None)
            else:
                log.warning("Section 9 retry also incomplete — using original output.")
        except Exception as e:
            log.warning("Section 9 retry failed: %s — using original output.", e)

    # Defensive: if model wrapped in markdown fence, strip it
    if html.startswith("```"):
        lines = html.split("\n")
        # Drop opening and closing fence lines
        html = "\n".join(line for line in lines if not line.startswith("```"))

    # Validate completeness — check for Section 9 and proper HTML closure
    has_section_9 = "DTLc.ai" in html and ("KEY INSIGHT" in html or "STRATEGIC INTERPRETATION" in html)
    has_closing = "</table>" in html[-200:] if len(html) > 200 else "</table>" in html

    if not has_section_9:
        log.warning("Section 9 (DTLc.ai's Take) is MISSING from output — likely truncated.")

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

    log.info("Synthesis: produced %d chars of HTML (stop_reason=%s, has_section_9=%s)", len(html), stop_reason, has_section_9)
    return html
