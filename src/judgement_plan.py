"""Portable judgement-planning layer for DTL Signal.

This module knows about evidence, positions and executive judgement. It does not
know about Render, Resend, subscriber APIs or HTML delivery infrastructure.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from anthropic import Anthropic

log = logging.getLogger(__name__)

MOVEMENT_TYPES = {
    "STRENGTHENS",
    "WEAKENS",
    "CONFIRMS",
    "CHALLENGES",
    "DOES_NOT_MATERIALLY_CHANGE",
}
CONFIDENCE_LEVELS = {"HIGH", "MEDIUM", "LOW"}
ACTION_TAGS = {"ACT", "WATCH", "NOTE"}
VISUAL_TYPES = {"DIRECTION_OF_TRAVEL", "TENSION_MAP", "COMPARISON", "EXPOSURE_MAP", "NONE"}


class JudgementPlanError(ValueError):
    """Raised when the planner returns an unsafe or incomplete plan."""


def _words(value: Any) -> int:
    return len(str(value).split())


def _extract_json_object(text: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text.strip()
    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            raise JudgementPlanError("Planner response did not contain a JSON object")
        candidate = candidate[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise JudgementPlanError(f"Planner returned invalid JSON: {exc}") from exc


def validate_judgement_plan(plan: dict[str, Any], available_source_ids: set[str]) -> dict[str, Any]:
    required = {
        "one_thing",
        "evidence_items",
        "interpretation",
        "dtl_view",
        "what_changed",
        "visual_signal",
        "counter_signal",
        "executive_actions",
        "executive_read",
        "memory_update",
    }
    missing = required.difference(plan)
    if missing:
        raise JudgementPlanError(f"Planner omitted required keys: {sorted(missing)}")

    one_thing = plan["one_thing"]
    if not str(one_thing.get("statement", "")).strip():
        raise JudgementPlanError("THE ONE THING is empty")
    if _words(one_thing["statement"]) > 24 or _words(one_thing.get("business_implication", "")) > 38:
        raise JudgementPlanError("THE ONE THING exceeds the executive-compression limit")
    if one_thing.get("confidence") not in CONFIDENCE_LEVELS:
        raise JudgementPlanError("THE ONE THING has an invalid confidence level")

    items = plan["evidence_items"]
    if not isinstance(items, list) or not 5 <= len(items) <= 8:
        raise JudgementPlanError("Enhanced edition must contain 5-8 evidence items")
    for item in items:
        if item.get("action_tag") not in ACTION_TAGS:
            raise JudgementPlanError("Evidence item has an invalid action tag")
        source_ids = set(item.get("source_ids") or [])
        if not source_ids or not source_ids.issubset(available_source_ids):
            raise JudgementPlanError(f"Evidence item cites unknown source IDs: {sorted(source_ids)}")
        for field in ("evidence", "headline", "category"):
            if not str(item.get(field, "")).strip():
                raise JudgementPlanError(f"Evidence item omitted {field}")
        if _words(item["headline"]) > 8:
            raise JudgementPlanError("Evidence headline exceeds eight words")
        if _words(item["evidence"]) > 28:
            raise JudgementPlanError("Evidence item exceeds 28 words")

    if not str(plan.get("interpretation", "")).strip() or _words(plan["interpretation"]) > 55:
        raise JudgementPlanError("Edition-level interpretation is missing or exceeds 55 words")
    if not str(plan.get("dtl_view", "")).strip() or _words(plan["dtl_view"]) > 45:
        raise JudgementPlanError("Edition-level DTL View is missing or exceeds 45 words")

    what_changed = plan["what_changed"]
    if what_changed.get("classification") not in MOVEMENT_TYPES:
        raise JudgementPlanError("WHAT CHANGED has an invalid classification")

    visual = plan["visual_signal"]
    if visual.get("type") not in VISUAL_TYPES:
        raise JudgementPlanError("Visual Signal has an invalid type")
    if visual.get("eligible") and visual.get("type") == "NONE":
        raise JudgementPlanError("Eligible Visual Signal cannot use type NONE")
    if visual.get("eligible") and not 2 <= len(visual.get("rows") or []) <= 5:
        raise JudgementPlanError("Eligible Visual Signal requires 2-5 rows")

    counter = plan["counter_signal"]
    if not str(counter.get("statement", "")).strip() or not str(counter.get("would_change_view_if", "")).strip():
        raise JudgementPlanError("Counter-Signal is incomplete")
    if _words(counter["statement"]) > 60 or _words(counter["would_change_view_if"]) > 45:
        raise JudgementPlanError("Counter-Signal exceeds the compression limit")

    actions = plan["executive_actions"]
    if not isinstance(actions, list) or not 1 <= len(actions) <= 3:
        raise JudgementPlanError("Edition requires 1-3 executive actions")
    if any(_words(action) > 24 for action in actions):
        raise JudgementPlanError("Executive action exceeds 24 words")

    executive_read = plan["executive_read"]
    if _words(executive_read.get("dtl_view", "")) > 75:
        raise JudgementPlanError("Executive Read exceeds 75 words")
    if any(_words(item) > 32 for item in executive_read.get("watch_items", [])):
        raise JudgementPlanError("What to Watch item exceeds 32 words")

    return plan


def generate_judgement_plan(
    evidence_items: list[dict[str, Any]],
    prior_memory: dict[str, Any],
    prompt_path: Path,
    model: str | None = None,
) -> dict[str, Any]:
    """Generate one structured editorial judgement plan from scored evidence."""
    source_ids = {str(item["source_id"]) for item in evidence_items}
    prompt = prompt_path.read_text().replace(
        "{EVIDENCE_ITEMS}", json.dumps(evidence_items, indent=2)
    ).replace(
        "{SIGNAL_MEMORY}", json.dumps(prior_memory, indent=2)
    )

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model_id = model or os.environ.get("MODEL_JUDGEMENT", "claude-sonnet-4-6")
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=model_id,
                max_tokens=8000,
                messages=[{
                    "role": "user",
                    "content": prompt + (
                        "\n\nThis is retry %d. Strictly obey every word limit; brevity is a validation requirement."
                        % (attempt + 1)
                    ),
                }],
            )
            text = "\n".join(
                block.text for block in response.content if getattr(block, "type", None) == "text"
            )
            return validate_judgement_plan(_extract_json_object(text), source_ids)
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                wait = 5 * (2**attempt)
                log.warning("Judgement planning attempt %d failed; retrying in %ds: %s", attempt + 1, wait, exc)
                time.sleep(wait)
    raise JudgementPlanError(f"Judgement planning failed after three attempts: {last_error}")


def scored_items_to_evidence(scored_items: list[Any]) -> list[dict[str, Any]]:
    """Convert ranked scored items into stable planner evidence IDs."""
    evidence: list[dict[str, Any]] = []
    for index, scored in enumerate(scored_items, 1):
        raw = scored.raw
        evidence.append(
            {
                "source_id": f"S{index:02d}",
                "title": raw.title,
                "source": raw.source,
                "url": raw.url,
                "category": raw.category,
                "score": scored.total,
                "evidence": raw.summary[:700],
                "scoring_reason": scored.reason,
            }
        )
    return evidence
