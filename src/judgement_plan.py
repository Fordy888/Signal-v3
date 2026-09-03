"""Portable judgement-planning layer for DTL Signal.

This module knows about evidence, positions and executive judgement. It does not
know about Render, Resend, subscriber APIs or HTML delivery infrastructure.
"""
from __future__ import annotations

import copy
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
ACTION_TAGS = {"ACT", "WATCH", "OPPORTUNITY", "NOTE"}
VISUAL_TYPES = {"DIRECTION_OF_TRAVEL", "TENSION_MAP", "COMPARISON", "EXPOSURE_MAP", "NONE"}
DYNAMIC_HEADLINE_REVISION = "dynamic-headlines-v1"
FOCUS_NUMBERS_REVISION = "focus-on-the-numbers-v1"
CONTENT_MIX_TYPES = {"AI_BUSINESS", "MAJOR_BUSINESS"}
MIN_AI_BUSINESS_ITEMS = 6
SOURCE_ID_RE = re.compile(r"\bS\d{2,}\b", re.IGNORECASE)
UNEXPLAINED_READER_TERMS = {
    "CRM", "UI", "API", "LLM", "RAG", "MCP", "GPU", "ERP", "SaaS", "SoR",
    "EBIT", "ARR", "ROI", "SKU",
    "agentic", "system of record",
}


class JudgementPlanError(ValueError):
    """Raised when the planner returns an unsafe or incomplete plan."""


def _words(value: Any) -> int:
    return len(str(value).split())


def _trim_words(value: Any, limit: int) -> str:
    return " ".join(str(value).split()[:limit]).strip()


def _trim_words_preserving_digit(value: Any, limit: int) -> str:
    """Trim display copy while retaining its defining numeric token and nearby unit."""
    words = str(value).split()
    if len(words) <= limit:
        return " ".join(words).strip()
    digit_indexes = [index for index, word in enumerate(words) if re.search(r"\d", word)]
    if not digit_indexes:
        return " ".join(words[:limit]).strip()
    digit_index = digit_indexes[0]
    end = min(len(words), max(limit, digit_index + 3))
    start = max(0, end - limit)
    if digit_index < start:
        start = digit_index
        end = min(len(words), start + limit)
    return " ".join(words[start:end]).strip()


def _is_dynamic_revision(plan: dict[str, Any]) -> bool:
    return plan.get("editorial_revision") in {
        DYNAMIC_HEADLINE_REVISION,
        FOCUS_NUMBERS_REVISION,
    }


def _is_focus_numbers_revision(plan: dict[str, Any]) -> bool:
    return plan.get("editorial_revision") == FOCUS_NUMBERS_REVISION


def _reader_fields(plan: dict[str, Any]) -> list[tuple[str, str]]:
    """Return reader-facing judgement copy; source names and internal memory stay out."""
    fields: list[tuple[str, str]] = []

    def add(path: str, value: Any) -> None:
        if isinstance(value, str):
            fields.append((path, value))

    focus_numbers_revision = _is_focus_numbers_revision(plan)
    if not focus_numbers_revision:
        one = plan.get("one_thing") or {}
        add("one_thing.statement", one.get("statement"))
        add("one_thing.business_implication", one.get("business_implication"))
    for index, item in enumerate(plan.get("evidence_items") or []):
        if isinstance(item, dict):
            add(f"evidence_items[{index}].headline", item.get("headline"))
            add(f"evidence_items[{index}].evidence", item.get("evidence"))
    add("interpretation_headline", plan.get("interpretation_headline"))
    add("interpretation", plan.get("interpretation"))
    note = plan.get("founders_note") or {}
    add("founders_note.headline", note.get("headline"))
    add("founders_note.body", note.get("body"))
    if focus_numbers_revision:
        for index, item in enumerate(plan.get("focus_numbers") or []):
            if isinstance(item, dict):
                add(f"focus_numbers[{index}].entity", item.get("entity"))
                add(f"focus_numbers[{index}].number", item.get("number"))
                add(f"focus_numbers[{index}].meaning", item.get("meaning"))
    else:
        changed = plan.get("what_changed") or {}
        add("what_changed.headline", changed.get("headline"))
        add("what_changed.explanation", changed.get("explanation"))
        visual = plan.get("visual_signal") or {}
        add("visual_signal.title", visual.get("title"))
        add("visual_signal.subtitle", visual.get("subtitle"))
        for index, row in enumerate(visual.get("rows") or []):
            if isinstance(row, dict):
                add(f"visual_signal.rows[{index}].label", row.get("label"))
                add(f"visual_signal.rows[{index}].detail", row.get("detail"))
    counter = plan.get("counter_signal") or {}
    add("counter_signal.headline", counter.get("headline"))
    add("counter_signal.statement", counter.get("statement"))
    add("counter_signal.would_change_view_if", counter.get("would_change_view_if"))
    for index, action in enumerate(plan.get("executive_actions") or []):
        if isinstance(action, dict):
            add(f"executive_actions[{index}].headline", action.get("headline"))
            add(f"executive_actions[{index}].instruction", action.get("instruction"))
    executive_read = plan.get("executive_read") or {}
    add("executive_read.watch_headline", executive_read.get("watch_headline"))
    for index, item in enumerate(executive_read.get("watch_items") or []):
        add(f"executive_read.watch_items[{index}]", item)
    return fields


def validate_reader_language(plan: dict[str, Any]) -> None:
    """Reject internal evidence codes and unexplained technical shorthand."""
    issues: list[str] = []
    for path, value in _reader_fields(plan):
        if SOURCE_ID_RE.search(value):
            issues.append(f"{path}: internal source ID")
        for term in UNEXPLAINED_READER_TERMS:
            if re.search(rf"\b{re.escape(term)}\b", value, re.IGNORECASE):
                issues.append(f"{path}: {term}")
    if issues:
        raise JudgementPlanError(
            "Reader-facing copy contains internal or unexplained technical language: "
            + "; ".join(sorted(set(issues)))
        )


def normalise_word_bound_fields(plan: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Deterministically cap bounded copy after LLM retries are exhausted.

    This repairs presentation-only word-limit overruns. Structural, provenance,
    confidence, action-tag and minimum-length errors remain hard failures.
    """
    normalised = copy.deepcopy(plan)
    repairs: list[str] = []

    def cap(container: dict[str, Any], key: str, limit: int, path: str) -> None:
        value = container.get(key)
        if isinstance(value, str) and _words(value) > limit:
            container[key] = _trim_words(value, limit)
            repairs.append(path)

    one_thing = normalised.get("one_thing")
    if isinstance(one_thing, dict):
        cap(one_thing, "statement", 24, "one_thing.statement")
        cap(one_thing, "business_implication", 38, "one_thing.business_implication")

    items = normalised.get("evidence_items")
    if isinstance(items, list):
        for index, item in enumerate(items):
            if isinstance(item, dict):
                cap(item, "headline", 8, f"evidence_items[{index}].headline")
                cap(item, "evidence", 28, f"evidence_items[{index}].evidence")

    focus_numbers = normalised.get("focus_numbers")
    if isinstance(focus_numbers, list):
        for index, item in enumerate(focus_numbers):
            if isinstance(item, dict):
                cap(item, "entity", 6, f"focus_numbers[{index}].entity")
                number = item.get("number")
                if isinstance(number, str) and _words(number) > 10:
                    item["number"] = _trim_words_preserving_digit(number, 10)
                    repairs.append(f"focus_numbers[{index}].number")
                cap(item, "meaning", 26, f"focus_numbers[{index}].meaning")

    if isinstance(normalised.get("interpretation"), str) and _words(normalised["interpretation"]) > 55:
        normalised["interpretation"] = _trim_words(normalised["interpretation"], 55)
        repairs.append("interpretation")

    if _is_dynamic_revision(normalised):
        if isinstance(normalised.get("interpretation_headline"), str) and _words(normalised["interpretation_headline"]) > 10:
            normalised["interpretation_headline"] = _trim_words(normalised["interpretation_headline"], 10)
            repairs.append("interpretation_headline")

    founders_note = normalised.get("founders_note")
    if isinstance(founders_note, dict):
        cap(founders_note, "headline", 12, "founders_note.headline")
        body = founders_note.get("body")
        body_limit = 90 if _is_focus_numbers_revision(normalised) else 180
        if isinstance(body, str) and body.endswith("— Paul") and _words(body) > body_limit:
            core = body[: -len("— Paul")].strip()
            founders_note["body"] = f"{_trim_words(core, body_limit - 2)} — Paul"
            repairs.append("founders_note.body")

    counter = normalised.get("counter_signal")
    if isinstance(counter, dict):
        if _is_dynamic_revision(normalised):
            cap(counter, "headline", 10, "counter_signal.headline")
        cap(counter, "statement", 60, "counter_signal.statement")
        cap(counter, "would_change_view_if", 45, "counter_signal.would_change_view_if")

    changed = normalised.get("what_changed")
    if _is_dynamic_revision(normalised) and not _is_focus_numbers_revision(normalised) and isinstance(changed, dict):
        cap(changed, "headline", 10, "what_changed.headline")

    actions = normalised.get("executive_actions")
    if isinstance(actions, list):
        for index, action in enumerate(actions):
            if _is_dynamic_revision(normalised) and isinstance(action, dict):
                cap(action, "headline", 6, f"executive_actions[{index}].headline")
                cap(action, "instruction", 20, f"executive_actions[{index}].instruction")
            elif isinstance(action, str) and _words(action) > 24:
                actions[index] = _trim_words(action, 24)
                repairs.append(f"executive_actions[{index}]")

    executive_read = normalised.get("executive_read")
    if isinstance(executive_read, dict):
        if _is_dynamic_revision(normalised):
            cap(executive_read, "watch_headline", 10, "executive_read.watch_headline")
        cap(executive_read, "dtl_view", 75, "executive_read.dtl_view")
        watch_items = executive_read.get("watch_items")
        if isinstance(watch_items, list):
            for index, item in enumerate(watch_items):
                if isinstance(item, str) and _words(item) > 32:
                    watch_items[index] = _trim_words(item, 32)
                    repairs.append(f"executive_read.watch_items[{index}]")

    return normalised, repairs


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
        "evidence_items",
        "interpretation",
        "founders_note",
        "what_changed",
        "counter_signal",
        "executive_actions",
        "executive_read",
        "memory_update",
    }
    focus_numbers_revision = _is_focus_numbers_revision(plan)
    if focus_numbers_revision:
        required.add("focus_numbers")
    else:
        required.update({"one_thing", "visual_signal"})
    missing = required.difference(plan)
    if missing:
        raise JudgementPlanError(f"Planner omitted required keys: {sorted(missing)}")
    dynamic_revision = _is_dynamic_revision(plan)
    if plan.get("editorial_revision") not in {
        None,
        DYNAMIC_HEADLINE_REVISION,
        FOCUS_NUMBERS_REVISION,
    }:
        raise JudgementPlanError("Planner returned an unsupported editorial revision")

    if not focus_numbers_revision:
        one_thing = plan["one_thing"]
        if not str(one_thing.get("statement", "")).strip():
            raise JudgementPlanError("THE ONE THING is empty")
        if _words(one_thing["statement"]) > 24 or _words(one_thing.get("business_implication", "")) > 38:
            raise JudgementPlanError("THE ONE THING exceeds the executive-compression limit")
        if one_thing.get("confidence") not in CONFIDENCE_LEVELS:
            raise JudgementPlanError("THE ONE THING has an invalid confidence level")

    items = plan["evidence_items"]
    if focus_numbers_revision:
        if not isinstance(items, list) or len(items) != 5:
            raise JudgementPlanError("DTL SIGNAL NEWSROOM requires exactly five stories")
    elif not isinstance(items, list) or not 5 <= len(items) <= 8:
        raise JudgementPlanError("Enhanced edition must contain 5-8 evidence items")
    newsroom_source_ids: set[str] = set()
    ai_business_items = 0
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
        newsroom_source_ids.update(source_ids)
        if focus_numbers_revision:
            mix_classification = str(item.get("mix_classification", "")).strip()
            if mix_classification not in CONTENT_MIX_TYPES:
                raise JudgementPlanError("Newsroom story has an invalid content-mix classification")
            if mix_classification == "AI_BUSINESS":
                connection = str(item.get("ai_business_connection", "")).strip()
                if not connection or _words(connection) > 28:
                    raise JudgementPlanError(
                        "AI-in-business Newsroom story requires a substantive connection in no more than 28 words"
                    )
                ai_business_items += 1

    if not str(plan.get("interpretation", "")).strip() or _words(plan["interpretation"]) > 55:
        raise JudgementPlanError("Edition-level interpretation is missing or exceeds 55 words")
    if dynamic_revision:
        interpretation_headline = str(plan.get("interpretation_headline", "")).strip()
        if not interpretation_headline or _words(interpretation_headline) > 10:
            raise JudgementPlanError("WHY IT MATTERS headline is missing or exceeds 10 words")

    founders_note = plan["founders_note"]
    headline = str(founders_note.get("headline", "")).strip()
    body = str(founders_note.get("body", "")).strip()
    if not headline or _words(headline) > 12:
        raise JudgementPlanError("FOUNDER'S NOTE headline is missing or exceeds 12 words")
    note_min, note_max = (45, 90) if focus_numbers_revision else (60, 180)
    if not note_min <= _words(body) <= note_max:
        raise JudgementPlanError(
            f"FOUNDER'S NOTE body must contain {note_min}-{note_max} words"
        )
    if not body.endswith("— Paul"):
        raise JudgementPlanError("FOUNDER'S NOTE must end with the inline sign-off — Paul")

    what_changed = plan["what_changed"]
    if what_changed.get("classification") not in MOVEMENT_TYPES:
        raise JudgementPlanError("Internal position movement has an invalid classification")
    if not str(what_changed.get("explanation", "")).strip():
        raise JudgementPlanError("Internal position movement requires an explanation")
    if dynamic_revision and not focus_numbers_revision:
        changed_headline = str(what_changed.get("headline", "")).strip()
        if not changed_headline or _words(changed_headline) > 10:
            raise JudgementPlanError("WHAT CHANGED headline is missing or exceeds 10 words")

    if focus_numbers_revision:
        focus_numbers = plan["focus_numbers"]
        if not isinstance(focus_numbers, list) or len(focus_numbers) != 5:
            raise JudgementPlanError("FOCUS ON THE NUMBERS requires exactly five entries")
        focus_source_ids: set[str] = set()
        for index, item in enumerate(focus_numbers):
            if not isinstance(item, dict):
                raise JudgementPlanError(f"Focus number {index + 1} is not structured")
            source_ids = set(item.get("source_ids") or [])
            if not source_ids or not source_ids.issubset(available_source_ids):
                raise JudgementPlanError(
                    f"Focus number {index + 1} cites unknown source IDs: {sorted(source_ids)}"
                )
            entity = str(item.get("entity", "")).strip()
            number = str(item.get("number", "")).strip()
            meaning = str(item.get("meaning", "")).strip()
            if not entity or _words(entity) > 6:
                raise JudgementPlanError(f"Focus number {index + 1} entity is missing or exceeds six words")
            if not number or _words(number) > 10 or not re.search(r"\d", number):
                raise JudgementPlanError(
                    f"Focus number {index + 1} must contain a defining figure in no more than 10 words"
                )
            if not meaning or _words(meaning) > 26:
                raise JudgementPlanError(
                    f"Focus number {index + 1} meaning is missing or exceeds 26 words"
                )
            mix_classification = str(item.get("mix_classification", "")).strip()
            if mix_classification not in CONTENT_MIX_TYPES:
                raise JudgementPlanError(
                    f"Focus number {index + 1} has an invalid content-mix classification"
                )
            if mix_classification == "AI_BUSINESS":
                connection = str(item.get("ai_business_connection", "")).strip()
                if not connection or _words(connection) > 28:
                    raise JudgementPlanError(
                        f"AI-in-business Focus number {index + 1} requires a substantive connection in no more than 28 words"
                    )
                ai_business_items += 1
            focus_source_ids.update(source_ids)
        overlap = newsroom_source_ids.intersection(focus_source_ids)
        if overlap:
            raise JudgementPlanError(
                "Newsroom stories and FOCUS ON THE NUMBERS must use distinct sources; "
                f"overlap: {sorted(overlap)}"
            )
        if ai_business_items < MIN_AI_BUSINESS_ITEMS:
            raise JudgementPlanError(
                "The combined Newsroom and FOCUS ON THE NUMBERS mix requires at least "
                f"{MIN_AI_BUSINESS_ITEMS} substantive AI-in-business items; received {ai_business_items}"
            )
    else:
        visual = plan["visual_signal"]
        if visual.get("type") not in VISUAL_TYPES:
            raise JudgementPlanError("Visual Signal has an invalid type")
        if visual.get("eligible") and visual.get("type") == "NONE":
            raise JudgementPlanError("Eligible Visual Signal cannot use type NONE")
        if visual.get("eligible") and not 2 <= len(visual.get("rows") or []) <= 5:
            raise JudgementPlanError("Eligible Visual Signal requires 2-5 rows")
        if dynamic_revision and visual.get("eligible"):
            if not str(visual.get("title", "")).strip() or _words(visual.get("title", "")) > 12:
                raise JudgementPlanError("THE SHIFT headline is missing or exceeds 12 words")

    counter = plan["counter_signal"]
    if not str(counter.get("statement", "")).strip() or not str(counter.get("would_change_view_if", "")).strip():
        raise JudgementPlanError("Counter-Signal is incomplete")
    if _words(counter["statement"]) > 60 or _words(counter["would_change_view_if"]) > 45:
        raise JudgementPlanError("Counter-Signal exceeds the compression limit")
    if dynamic_revision:
        counter_headline = str(counter.get("headline", "")).strip()
        if not counter_headline or _words(counter_headline) > 10:
            raise JudgementPlanError("THE OTHER SIDE headline is missing or exceeds 10 words")

    actions = plan["executive_actions"]
    if not isinstance(actions, list) or not 1 <= len(actions) <= 3:
        raise JudgementPlanError("Edition requires 1-3 executive actions")
    if dynamic_revision:
        for action in actions:
            if not isinstance(action, dict):
                raise JudgementPlanError("Dynamic executive actions must be structured")
            if action.get("action_tag") not in ACTION_TAGS:
                raise JudgementPlanError("Executive action has an invalid action tag")
            if not str(action.get("headline", "")).strip() or _words(action["headline"]) > 6:
                raise JudgementPlanError("Executive action headline is missing or exceeds six words")
            if not str(action.get("instruction", "")).strip() or _words(action["instruction"]) > 20:
                raise JudgementPlanError("Executive action instruction is missing or exceeds 20 words")
    elif any(_words(action) > 24 for action in actions):
        raise JudgementPlanError("Executive action exceeds 24 words")

    executive_read = plan["executive_read"]
    if _words(executive_read.get("dtl_view", "")) > 75:
        raise JudgementPlanError("Executive Read exceeds 75 words")
    if any(_words(item) > 32 for item in executive_read.get("watch_items", [])):
        raise JudgementPlanError("What to Watch item exceeds 32 words")

    if dynamic_revision:
        watch_headline = str(executive_read.get("watch_headline", "")).strip()
        if not watch_headline or _words(watch_headline) > 10:
            raise JudgementPlanError("WATCH FOR THIS headline is missing or exceeds 10 words")
        validate_reader_language(plan)

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
            candidate = _extract_json_object(text)
            if attempt == 2:
                candidate, repairs = normalise_word_bound_fields(candidate)
                if repairs:
                    log.warning(
                        "Judgement planning final attempt normalised bounded fields: %s",
                        ", ".join(repairs),
                    )
            return validate_judgement_plan(candidate, source_ids)
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
