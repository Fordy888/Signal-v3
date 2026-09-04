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
AI_ADOPTION_REVISION = "ai-adoption-v1"
CONTENT_MIX_TYPES = {"AI_BUSINESS", "MAJOR_BUSINESS"}
AI_ADOPTION_MIX_TYPES = {"AI_ADOPTION", "AI_INDUSTRY_IMPACT"}
MIN_AI_BUSINESS_ITEMS = 6
REQUIRED_AI_BUSINESS_ITEMS = 6
REQUIRED_AI_BUSINESS_PER_SECTION = 3
REQUIRED_MAJOR_BUSINESS_PER_SECTION = 2
MIN_AI_ADOPTION_ITEMS = 8
MAX_AI_INDUSTRY_IMPACT_ITEMS = 2
SOURCE_ID_RE = re.compile(r"\bS\d{2,}\b", re.IGNORECASE)
UNEXPLAINED_READER_TERMS = {
    "CRM", "UI", "API", "LLM", "RAG", "MCP", "GPU", "ERP", "SaaS", "SoR",
    "EBIT", "ARR", "ROI", "SKU",
    "agentic", "system of record",
}


INCOMPLETE_HEADLINE_ENDINGS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "being", "but", "by",
    "above", "across", "against", "before", "below", "between", "beyond", "for", "from",
    "if", "in", "into", "is", "just", "moving", "not", "of", "on", "or", "over", "that",
    "the", "their", "this", "through", "to", "toward", "towards", "under", "until", "upon",
    "was", "were", "when", "while", "with", "within", "without", "your",
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


def _headline_is_complete(value: Any) -> bool:
    text = str(value).strip()
    if not text or text.endswith((",", ";", ":", "-", "—")):
        return False
    last_word = re.sub(r"[^A-Za-z']", "", text.split()[-1]).lower()
    return bool(last_word) and last_word not in INCOMPLETE_HEADLINE_ENDINGS


def _trim_complete_headline(value: Any, limit: int) -> str:
    """Shorten a headline without leaving a dangling article, preposition or clause."""
    words = str(value).split()[:limit]
    while len(words) > 1:
        candidate = " ".join(words).strip().rstrip(" ,;:-—")
        if _headline_is_complete(candidate):
            return candidate
        words.pop()
    return " ".join(words).strip().rstrip(" ,;:-—")


def _is_dynamic_revision(plan: dict[str, Any]) -> bool:
    return plan.get("editorial_revision") in {
        DYNAMIC_HEADLINE_REVISION,
        FOCUS_NUMBERS_REVISION,
        AI_ADOPTION_REVISION,
    }


def _is_focus_numbers_revision(plan: dict[str, Any]) -> bool:
    return plan.get("editorial_revision") in {FOCUS_NUMBERS_REVISION, AI_ADOPTION_REVISION}


def _is_ai_adoption_revision(plan: dict[str, Any]) -> bool:
    return plan.get("editorial_revision") == AI_ADOPTION_REVISION


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

    def cap_headline(container: dict[str, Any], key: str, limit: int, path: str) -> None:
        value = container.get(key)
        if not isinstance(value, str):
            return
        repaired = _trim_complete_headline(value, limit)
        if repaired != value.strip():
            container[key] = repaired
            repairs.append(path)

    one_thing = normalised.get("one_thing")
    if isinstance(one_thing, dict):
        cap(one_thing, "statement", 24, "one_thing.statement")
        cap(one_thing, "business_implication", 38, "one_thing.business_implication")

    items = normalised.get("evidence_items")
    if isinstance(items, list):
        for index, item in enumerate(items):
            if isinstance(item, dict):
                cap_headline(item, "headline", 8, f"evidence_items[{index}].headline")
                cap(item, "evidence", 28, f"evidence_items[{index}].evidence")
                if item.get("mix_classification") in {
                    "AI_BUSINESS", "AI_ADOPTION", "AI_INDUSTRY_IMPACT"
                }:
                    cap(
                        item,
                        "ai_business_connection",
                        28,
                        f"evidence_items[{index}].ai_business_connection",
                    )

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
                if item.get("mix_classification") in {
                    "AI_BUSINESS", "AI_ADOPTION", "AI_INDUSTRY_IMPACT"
                }:
                    cap(
                        item,
                        "ai_business_connection",
                        28,
                        f"focus_numbers[{index}].ai_business_connection",
                    )

    if isinstance(normalised.get("interpretation"), str) and _words(normalised["interpretation"]) > 55:
        normalised["interpretation"] = _trim_words(normalised["interpretation"], 55)
        repairs.append("interpretation")

    if _is_dynamic_revision(normalised):
        cap_headline(normalised, "interpretation_headline", 10, "interpretation_headline")

    founders_note = normalised.get("founders_note")
    if isinstance(founders_note, dict):
        cap_headline(founders_note, "headline", 12, "founders_note.headline")
        body = founders_note.get("body")
        body_limit = 90 if _is_focus_numbers_revision(normalised) else 180
        if isinstance(body, str) and body.endswith("— Paul") and _words(body) > body_limit:
            core = body[: -len("— Paul")].strip()
            founders_note["body"] = f"{_trim_words(core, body_limit - 2)} — Paul"
            repairs.append("founders_note.body")

    counter = normalised.get("counter_signal")
    if isinstance(counter, dict):
        if _is_dynamic_revision(normalised):
            cap_headline(counter, "headline", 10, "counter_signal.headline")
        cap(counter, "statement", 60, "counter_signal.statement")
        cap(counter, "would_change_view_if", 45, "counter_signal.would_change_view_if")

    changed = normalised.get("what_changed")
    if _is_dynamic_revision(normalised) and not _is_focus_numbers_revision(normalised) and isinstance(changed, dict):
        cap_headline(changed, "headline", 10, "what_changed.headline")

    visual = normalised.get("visual_signal")
    if _is_dynamic_revision(normalised) and isinstance(visual, dict) and visual.get("eligible"):
        cap_headline(visual, "title", 12, "visual_signal.title")

    actions = normalised.get("executive_actions")
    if isinstance(actions, list):
        if len(actions) > 3:
            normalised["executive_actions"] = actions[:3]
            actions = normalised["executive_actions"]
            repairs.append("executive_actions")
        for index, action in enumerate(actions):
            if _is_dynamic_revision(normalised) and isinstance(action, dict):
                cap_headline(action, "headline", 6, f"executive_actions[{index}].headline")
                cap(action, "instruction", 20, f"executive_actions[{index}].instruction")
            elif isinstance(action, str) and _words(action) > 24:
                actions[index] = _trim_words(action, 24)
                repairs.append(f"executive_actions[{index}]")

    executive_read = normalised.get("executive_read")
    if isinstance(executive_read, dict):
        if _is_dynamic_revision(normalised):
            cap_headline(executive_read, "watch_headline", 10, "executive_read.watch_headline")
        cap(executive_read, "dtl_view", 75, "executive_read.dtl_view")
        watch_items = executive_read.get("watch_items")
        if isinstance(watch_items, list):
            for index, item in enumerate(watch_items):
                if isinstance(item, str) and _words(item) > 32:
                    watch_items[index] = _trim_words(item, 32)
                    repairs.append(f"executive_read.watch_items[{index}]")

    return normalised, repairs


ELIGIBLE_FOCUS_FIGURE_RE = re.compile(
    r"(?:[$€£]\s?\d[\d,]*(?:\.\d+)?\s?(?:thousand|million|billion|trillion)?)"
    r"|(?:\b\d[\d,]*(?:\.\d+)?\s?(?:%|percent\b|basis points?\b|bps\b|"
    r"thousand\b|million\b|billion\b|trillion\b|roles\b|jobs\b|customers\b|"
    r"workers\b|employees\b|firms\b|companies\b|points\b|times\b|x\b))",
    re.IGNORECASE,
)

FOCUS_FIGURE_CONTEXT_WORDS = {
    "adoption",
    "annual",
    "arr",
    "budget",
    "cost",
    "customers",
    "earnings",
    "employment",
    "growth",
    "investment",
    "jobs",
    "layoffs",
    "loss",
    "margin",
    "price",
    "profit",
    "recurring",
    "remuneration",
    "revenue",
    "sales",
    "savings",
    "valuation",
    "workers",
}

AI_SUBJECT_RE = re.compile(
    r"\b(?:AI|artificial intelligence|generative AI|machine learning|ChatGPT|"
    r"OpenAI|Anthropic|Claude|Gemini|Copilot|large language model|LLM)\b",
    re.IGNORECASE,
)
BUSINESS_IMPACT_RE = re.compile(
    r"\b(?:business|enterprise|company|companies|customer|customers|sales|marketing|"
    r"revenue|profit|earnings|margin|cost|costs|price|pricing|investment|capital|"
    r"valuation|market|workplace|workforce|worker|workers|employee|employees|jobs?|"
    r"roles?|hiring|productivity|operations?|workflow|logistics|supply chain|service|"
    r"services|risk|regulation|governance|strategy|commercial|contract|contracts|"
    r"adoption|demand|growth|loss|losses|returns?|value)\b",
    re.IGNORECASE,
)
AI_ADOPTION_RE = re.compile(
    r"\b(?:adopt(?:s|ed|ing|ion)?|deploy(?:s|ed|ing|ment)?|implement(?:s|ed|ing|ation)?|"
    r"integrat(?:e|es|ed|ing|ion)|us(?:e|es|ed|ing)|appl(?:y|ies|ied|ying)|"
    r"automat(?:e|es|ed|ing|ion)|redesign(?:s|ed|ing)?|retrain(?:s|ed|ing)?)\b",
    re.IGNORECASE,
)
AI_ADOPTION_ACTOR_RE = re.compile(
    r"\b(?:business(?:es)?|compan(?:y|ies)|enterprise(?:s)?|firms?|organisation(?:s)?|"
    r"organization(?:s)?|bank(?:s)?|retailer(?:s)?|manufacturer(?:s)?|hospital(?:s)?|"
    r"employer(?:s)?|employee(?:s)?|worker(?:s)?|team(?:s)?|customer(?:s)?|staff|"
    r"workplace|workforce|government|agency|agencies)\b",
    re.IGNORECASE,
)
AI_NAMED_ADOPTION_ACTOR_RE = re.compile(
    r"\b[A-Z][A-Za-z0-9&.'-]+(?:\s+[A-Z][A-Za-z0-9&.'-]+){0,3}\s+"
    r"(?:has\s+|have\s+|is\s+|are\s+)?"
    + AI_ADOPTION_RE.pattern,
)
AI_ADOPTION_WORK_RE = re.compile(
    r"\b(?:workflow|process|task|work|customer service|sales|marketing|operations?|"
    r"productivity|roles?|training|cost|costs|revenue|conversion|fraud|claims|"
    r"underwriting|logistics|supply chain|manufacturing|decision|decisions|"
    r"service|services|delivery|hiring|finance|forecasting|planning)\b",
    re.IGNORECASE,
)
AI_HYPOTHETICAL_RE = re.compile(
    r"\b(?:could|might|may|should|potentially|plans? to|intends? to|considering)\b",
    re.IGNORECASE,
)
AI_INDUSTRY_DEVELOPMENT_RE = re.compile(
    r"\b(?:launch(?:es|ed)?|release(?:s|d)?|price|prices|pricing|cost|costs|funding|"
    r"investment|acquisition|regulation|regulator|rules?|law|ban|security|access|"
    r"availability|infrastructure|capacity|capability|contract|partnership)\b",
    re.IGNORECASE,
)
PRACTICAL_CONSEQUENCE_RE = re.compile(
    r"\b(?:chang(?:e|es|ed|ing)|reduc(?:e|es|ed|ing)|cut(?:s|ting)?|rais(?:e|es|ed|ing)|"
    r"lower(?:s|ed|ing)?|limit(?:s|ed|ing)?|requir(?:e|es|ed|ing)|allow(?:s|ed|ing)?|"
    r"enabl(?:e|es|ed|ing)|affect(?:s|ed|ing)?|expos(?:e|es|ed|ing)|increase(?:s|d|ing)?|"
    r"decrease(?:s|d|ing)?|improv(?:e|es|ed|ing)|worsen(?:s|ed|ing)?)\b",
    re.IGNORECASE,
)


def _has_ai_adoption_evidence(text: str) -> bool:
    """Require explicit AI application by a real business actor to work or outcomes."""
    has_actor = bool(
        AI_ADOPTION_ACTOR_RE.search(text) or AI_NAMED_ADOPTION_ACTOR_RE.search(text)
    )
    if AI_HYPOTHETICAL_RE.search(text) or not (
        AI_SUBJECT_RE.search(text)
        and BUSINESS_IMPACT_RE.search(text)
        and AI_ADOPTION_RE.search(text)
        and has_actor
        and AI_ADOPTION_WORK_RE.search(text)
    ):
        return False
    patterns = (
        rf"{AI_ADOPTION_ACTOR_RE.pattern}.{{0,120}}{AI_ADOPTION_RE.pattern}.{{0,80}}{AI_SUBJECT_RE.pattern}",
        rf"{AI_ADOPTION_ACTOR_RE.pattern}.{{0,120}}{AI_SUBJECT_RE.pattern}.{{0,80}}{AI_ADOPTION_RE.pattern}",
        rf"{AI_SUBJECT_RE.pattern}.{{0,80}}{AI_ADOPTION_RE.pattern}.{{0,120}}{AI_ADOPTION_WORK_RE.pattern}",
        rf"{AI_ADOPTION_RE.pattern}.{{0,80}}{AI_SUBJECT_RE.pattern}.{{0,120}}{AI_ADOPTION_WORK_RE.pattern}",
        rf"{AI_NAMED_ADOPTION_ACTOR_RE.pattern}.{{0,120}}{AI_SUBJECT_RE.pattern}",
    )
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _has_ai_industry_impact_evidence(text: str) -> bool:
    """Require an AI-industry development and a stated practical consequence."""
    return bool(
        not AI_HYPOTHETICAL_RE.search(text)
        and AI_SUBJECT_RE.search(text)
        and BUSINESS_IMPACT_RE.search(text)
        and AI_INDUSTRY_DEVELOPMENT_RE.search(text)
        and PRACTICAL_CONSEQUENCE_RE.search(text)
    )


MAJOR_BUSINESS_RE = re.compile(
    r"\b(?:acquisition|merger|regulation|tariff|tariffs|oil|rates?|inflation|GDP|"
    r"economy|economic|business|company|companies|commercial|strategy|factory|factories|supply chain|revenue|profit|earnings|margin|"
    r"loss|losses|growth|investment|capital|valuation|market|share price|pricing|sales|"
    r"customers|jobs?|workers?|employees?|wages|costs?|demand)\b",
    re.IGNORECASE,
)


def _source_bound_focus_figure(source: dict[str, Any], focus_item: dict[str, Any]) -> str | None:
    """Extract one compact figure from a selected source without inventing copy."""
    focus_terms = {
        term.lower()
        for term in re.findall(
            r"[A-Za-z]{3,}",
            " ".join(
                str(focus_item.get(field, ""))
                for field in ("entity", "meaning", "ai_business_connection")
            ),
        )
    }
    candidates: list[tuple[int, int, str]] = []
    for field_priority, field in enumerate(
        ("evidence", "source_evidence", "title", "scoring_reason")
    ):
        text = str(source.get(field, "")).strip()
        if not text:
            continue
        for match in ELIGIBLE_FOCUS_FIGURE_RE.finditer(text):
            sentence_start = max(text.rfind(".", 0, match.start()), text.rfind(";", 0, match.start())) + 1
            sentence_end_candidates = [
                boundary for boundary in (text.find(".", match.end()), text.find(";", match.end()))
                if boundary >= 0
            ]
            sentence_end = min(sentence_end_candidates) if sentence_end_candidates else len(text)
            sentence = text[sentence_start:sentence_end].strip()
            local_start = match.start() - sentence_start
            word_spans = list(re.finditer(r"\S+", sentence))
            start_index = next(
                (index for index, word in enumerate(word_spans) if word.start() <= local_start < word.end()),
                0,
            )
            compact = " ".join(
                word.group(0) for word in word_spans[start_index : start_index + 8]
            ).strip(" ,;:")
            compact = _trim_words_preserving_digit(compact, 10)
            if not compact or not re.search(r"\d", compact):
                continue

            sentence_terms = {term.lower() for term in re.findall(r"[A-Za-z]{3,}", sentence)}
            context_score = len(focus_terms.intersection(sentence_terms))
            business_score = len(FOCUS_FIGURE_CONTEXT_WORDS.intersection(sentence_terms))
            unit_score = 3 if re.search(r"[$€£]|%|percent|million|billion|trillion", match.group(0), re.I) else 1
            score = (context_score * 4) + (business_score * 2) + unit_score - field_priority
            candidates.append((score, -match.start(), compact))

    if not candidates:
        return None
    return max(candidates, key=lambda candidate: (candidate[0], candidate[1]))[2]


def prepare_focus_number_evidence(
    evidence_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[str]]:
    """Annotate source evidence with deterministic Focus-number eligibility.

    The planner may only cite eligible source IDs for Focus on the Numbers. The
    compact candidate is copied verbatim from the same source evidence and is a
    planning aid, not permission to invent or transfer figures between sources.
    """
    prepared = copy.deepcopy(evidence_items)
    eligible_source_ids: set[str] = set()
    for source in prepared:
        source_id = str(source.get("source_id", "")).strip()
        candidate = _source_bound_focus_figure(source, {}) if source_id else None
        source["focus_number_eligible"] = candidate is not None
        if candidate is not None:
            source["focus_number_candidate"] = candidate
            eligible_source_ids.add(source_id)
    return prepared, eligible_source_ids


def prepare_content_mix_evidence(
    evidence_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Classify source substance before planning; generated labels are not authoritative."""
    prepared = copy.deepcopy(evidence_items)
    verified_mix_by_source: dict[str, str] = {}
    for source in prepared:
        source_id = str(source.get("source_id", "")).strip()
        if not source_id:
            continue
        text = " ".join(
            str(source.get(field, "")).strip()
            for field in ("title", "evidence", "scoring_reason")
        )
        if AI_SUBJECT_RE.search(text) and BUSINESS_IMPACT_RE.search(text):
            classification = "AI_BUSINESS"
        elif not AI_SUBJECT_RE.search(text) and MAJOR_BUSINESS_RE.search(text):
            classification = "MAJOR_BUSINESS"
        else:
            source["verified_mix_eligible"] = False
            continue
        source["verified_mix_eligible"] = True
        source["verified_mix_classification"] = classification
        verified_mix_by_source[source_id] = classification
    return prepared, verified_mix_by_source


def prepare_ai_adoption_evidence(
    evidence_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Classify eligible sources as applied AI adoption or practical industry impact.

    General business evidence is excluded. Adoption requires explicit AI, a concrete
    business consequence and evidence that an organisation is applying AI to work.
    Remaining AI evidence qualifies only as industry impact, never as general news.
    """
    prepared = copy.deepcopy(evidence_items)
    verified_mix_by_source: dict[str, str] = {}
    for source in prepared:
        source_id = str(source.get("source_id", "")).strip()
        if not source_id:
            continue
        text = " ".join(
            str(source.get(field, "")).strip()
            for field in ("title", "evidence", "source_evidence", "scoring_reason")
        )
        if not (AI_SUBJECT_RE.search(text) and BUSINESS_IMPACT_RE.search(text)):
            source["verified_mix_eligible"] = False
            continue
        if _has_ai_adoption_evidence(text):
            classification = "AI_ADOPTION"
        elif _has_ai_industry_impact_evidence(text):
            classification = "AI_INDUSTRY_IMPACT"
        else:
            source["verified_mix_eligible"] = False
            continue
        source["verified_mix_eligible"] = True
        source["verified_mix_classification"] = classification
        verified_mix_by_source[source_id] = classification
    return prepared, verified_mix_by_source


def allocate_ai_adoption_content(
    evidence_items: list[dict[str, Any]],
    focus_eligible_source_ids: set[str],
    verified_mix_by_source: dict[str, str],
) -> dict[str, list[str]]:
    """Allocate ten all-AI sources with adoption dominant and industry capped at two."""
    ordered_source_ids = [
        str(item.get("source_id", "")).strip()
        for item in evidence_items
        if str(item.get("source_id", "")).strip()
    ]

    def select(
        classification: str,
        count: int,
        *,
        focus_only: bool = False,
        excluded: set[str] | None = None,
    ) -> list[str]:
        excluded = excluded or set()
        return [
            source_id
            for source_id in ordered_source_ids
            if source_id not in excluded
            and verified_mix_by_source.get(source_id) == classification
            and (not focus_only or source_id in focus_eligible_source_ids)
        ][:count]

    focus_adoption = select("AI_ADOPTION", 4, focus_only=True)
    if len(focus_adoption) < 4:
        raise JudgementPlanError(
            "FOCUS ON THE NUMBERS requires at least 4 verified AI_ADOPTION sources "
            f"with numeric evidence; received {len(focus_adoption)}"
        )
    focus_industry = select(
        "AI_INDUSTRY_IMPACT", 1, focus_only=True, excluded=set(focus_adoption)
    )
    if focus_industry:
        focus_source_ids = focus_adoption + focus_industry
    else:
        focus_source_ids = select("AI_ADOPTION", 5, focus_only=True)
        if len(focus_source_ids) < 5:
            raise JudgementPlanError(
                "FOCUS ON THE NUMBERS requires five all-AI numeric sources when no "
                "AI_INDUSTRY_IMPACT numeric source qualifies"
            )

    focus_set = set(focus_source_ids)
    newsroom_adoption = select("AI_ADOPTION", 4, excluded=focus_set)
    if len(newsroom_adoption) < 4:
        raise JudgementPlanError(
            "DTL SIGNAL NEWSROOM requires at least 4 remaining AI_ADOPTION sources; "
            f"received {len(newsroom_adoption)}"
        )
    newsroom_industry = select(
        "AI_INDUSTRY_IMPACT", 1, excluded=focus_set | set(newsroom_adoption)
    )
    if newsroom_industry:
        newsroom_source_ids = newsroom_adoption + newsroom_industry
    else:
        newsroom_source_ids = select("AI_ADOPTION", 5, excluded=focus_set)
        if len(newsroom_source_ids) < 5:
            raise JudgementPlanError(
                "DTL SIGNAL NEWSROOM requires five all-AI sources when no remaining "
                "AI_INDUSTRY_IMPACT source qualifies"
            )

    selected = newsroom_source_ids + focus_source_ids
    selected_adoption = sum(
        verified_mix_by_source.get(source_id) == "AI_ADOPTION" for source_id in selected
    )
    selected_industry = len(selected) - selected_adoption
    if selected_adoption < MIN_AI_ADOPTION_ITEMS or selected_industry > MAX_AI_INDUSTRY_IMPACT_ITEMS:
        raise JudgementPlanError(
            "All-AI allocation requires at least 8 AI_ADOPTION items and at most 2 "
            "AI_INDUSTRY_IMPACT items"
        )
    return {"newsroom": newsroom_source_ids, "focus_numbers": focus_source_ids}


def allocate_focus_numbers_content_mix(
    evidence_items: list[dict[str, Any]],
    focus_eligible_source_ids: set[str],
    verified_mix_by_source: dict[str, str],
) -> dict[str, list[str]]:
    """Allocate the exact 3/2 section mix before the planner writes copy.

    The planner must not decide which section receives a verified source. Focus
    receives its required numeric evidence first; Newsroom receives the next
    ranked, distinct sources from each verified class. Evidence arrives in
    scored rank order, so this is deterministic and retains editorial priority.
    """
    ordered_source_ids = [
        str(item.get("source_id", "")).strip()
        for item in evidence_items
        if str(item.get("source_id", "")).strip()
    ]

    def select(
        classification: str,
        count: int,
        *,
        focus_only: bool = False,
        excluded: set[str] | None = None,
    ) -> list[str]:
        excluded = excluded or set()
        return [
            source_id
            for source_id in ordered_source_ids
            if source_id not in excluded
            and verified_mix_by_source.get(source_id) == classification
            and (not focus_only or source_id in focus_eligible_source_ids)
        ][:count]

    focus_ai = select("AI_BUSINESS", REQUIRED_AI_BUSINESS_PER_SECTION, focus_only=True)
    focus_major = select("MAJOR_BUSINESS", REQUIRED_MAJOR_BUSINESS_PER_SECTION, focus_only=True)
    if len(focus_ai) != REQUIRED_AI_BUSINESS_PER_SECTION:
        raise JudgementPlanError(
            "FOCUS ON THE NUMBERS allocation requires at least 3 independently verified "
            "AI_BUSINESS source records with pre-verified numeric evidence; received "
            f"{len(focus_ai)}"
        )
    if len(focus_major) != REQUIRED_MAJOR_BUSINESS_PER_SECTION:
        raise JudgementPlanError(
            "FOCUS ON THE NUMBERS allocation requires at least 2 independently verified "
            "MAJOR_BUSINESS source records with pre-verified numeric evidence; received "
            f"{len(focus_major)}"
        )

    focus_source_ids = focus_ai + focus_major
    focus_set = set(focus_source_ids)
    newsroom_ai = select(
        "AI_BUSINESS",
        REQUIRED_AI_BUSINESS_PER_SECTION,
        excluded=focus_set,
    )
    newsroom_major = select(
        "MAJOR_BUSINESS",
        REQUIRED_MAJOR_BUSINESS_PER_SECTION,
        excluded=focus_set,
    )
    if len(newsroom_ai) != REQUIRED_AI_BUSINESS_PER_SECTION:
        raise JudgementPlanError(
            "DTL SIGNAL NEWSROOM allocation requires 3 remaining independently verified "
            "AI_BUSINESS source records after Focus allocation; received "
            f"{len(newsroom_ai)}"
        )
    if len(newsroom_major) != REQUIRED_MAJOR_BUSINESS_PER_SECTION:
        raise JudgementPlanError(
            "DTL SIGNAL NEWSROOM allocation requires 2 remaining independently verified "
            "MAJOR_BUSINESS source records after Focus allocation; received "
            f"{len(newsroom_major)}"
        )

    return {
        "newsroom": newsroom_ai + newsroom_major,
        "focus_numbers": focus_source_ids,
    }


def _validate_reader_visible_mix_copy(
    item: dict[str, Any],
    classification: str,
    *,
    section: str,
) -> None:
    """Make the verified 6/4 mix true in the copy subscribers actually read."""
    fields = (
        ("entity", "number", "meaning")
        if section == "Focus"
        else ("headline", "evidence")
    )
    reader_text = " ".join(str(item.get(field, "")).strip() for field in fields)
    has_ai_subject = bool(AI_SUBJECT_RE.search(reader_text))
    has_business_impact = bool(BUSINESS_IMPACT_RE.search(reader_text))
    if classification in {"AI_BUSINESS", "AI_ADOPTION", "AI_INDUSTRY_IMPACT"} and not (
        has_ai_subject and has_business_impact
    ):
        raise JudgementPlanError(
            f"{section} {classification} reader copy must state an explicit AI subject "
            "and concrete business consequence"
        )
    if classification == "AI_ADOPTION" and not _has_ai_adoption_evidence(reader_text):
        raise JudgementPlanError(
            f"{section} AI_ADOPTION reader copy must state the real-world use, process "
            "or operating change"
        )
    if classification == "MAJOR_BUSINESS" and has_ai_subject:
        raise JudgementPlanError(
            f"{section} MAJOR_BUSINESS reader copy must not introduce an AI-led angle"
        )


def recover_missing_focus_figures(
    plan: dict[str, Any],
    evidence_items: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    """Recover a missing Focus figure only from its one cited source record.

    No source ID or classification is changed. If the cited source has no explicit
    eligible figure, validation remains responsible for holding the edition.
    """
    repaired = copy.deepcopy(plan)
    if not _is_focus_numbers_revision(repaired):
        return repaired, []

    evidence_by_id: dict[str, dict[str, Any]] = {}
    duplicate_ids: set[str] = set()
    for source in evidence_items:
        source_id = str(source.get("source_id", "")).strip()
        if not source_id:
            continue
        if source_id in evidence_by_id:
            duplicate_ids.add(source_id)
        evidence_by_id[source_id] = source

    repairs: list[str] = []
    focus_numbers = repaired.get("focus_numbers")
    if not isinstance(focus_numbers, list):
        return repaired, repairs
    for index, item in enumerate(focus_numbers):
        if not isinstance(item, dict):
            continue
        number = str(item.get("number", "")).strip()
        if re.search(r"\d", number):
            continue
        source_ids = [str(source_id) for source_id in item.get("source_ids") or []]
        if len(source_ids) != 1 or source_ids[0] in duplicate_ids:
            continue
        source = evidence_by_id.get(source_ids[0])
        if source is None:
            continue
        recovered = _source_bound_focus_figure(source, item)
        if recovered is None:
            continue
        item["number"] = recovered
        item["number_recovered_from_source"] = source_ids[0]
        repairs.append(f"focus_numbers[{index}].number")
    return repaired, repairs


def complete_ai_focus_reader_copy(
    plan: dict[str, Any],
    evidence_items: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    """Complete missing AI-business wording from the item's one selected source.

    The repair is deliberately narrow and final-attempt only. It may replace the
    reader-facing meaning with one concise sentence copied from the same source
    when that sentence explicitly contains both an AI subject and a business
    consequence. It never changes source IDs, figures, classifications or
    MAJOR_BUSINESS copy, and it never borrows language from another source.
    """
    repaired = copy.deepcopy(plan)
    if not _is_focus_numbers_revision(repaired):
        return repaired, []

    evidence_by_id: dict[str, dict[str, Any]] = {}
    duplicate_ids: set[str] = set()
    for source in evidence_items:
        source_id = str(source.get("source_id", "")).strip()
        if not source_id:
            continue
        if source_id in evidence_by_id:
            duplicate_ids.add(source_id)
        evidence_by_id[source_id] = source

    repairs: list[str] = []
    focus_numbers = repaired.get("focus_numbers")
    if not isinstance(focus_numbers, list):
        return repaired, repairs

    for index, item in enumerate(focus_numbers):
        if not isinstance(item, dict) or item.get("mix_classification") not in {
            "AI_BUSINESS", "AI_ADOPTION", "AI_INDUSTRY_IMPACT"
        }:
            continue
        reader_text = " ".join(
            str(item.get(field, "")).strip() for field in ("entity", "number", "meaning")
        )
        classification = str(item.get("mix_classification"))
        adoption_ok = classification != "AI_ADOPTION" or _has_ai_adoption_evidence(reader_text)
        if AI_SUBJECT_RE.search(reader_text) and BUSINESS_IMPACT_RE.search(reader_text) and adoption_ok:
            continue

        source_ids = [str(source_id) for source_id in item.get("source_ids") or []]
        if len(source_ids) != 1 or source_ids[0] in duplicate_ids:
            continue
        source = evidence_by_id.get(source_ids[0])
        if source is None:
            continue

        source_text = " ".join(
            str(source.get(field, "")).strip()
            for field in ("title", "evidence", "source_evidence", "scoring_reason")
            if str(source.get(field, "")).strip()
        )
        if not (AI_SUBJECT_RE.search(source_text) and BUSINESS_IMPACT_RE.search(source_text)):
            continue

        candidate: str | None = None
        for field in ("evidence", "source_evidence", "title", "scoring_reason"):
            field_text = str(source.get(field, "")).strip()
            for sentence in re.split(r"(?<=[.!?])\s+|\s*;\s*", field_text):
                sentence = " ".join(sentence.split()).strip(" ,;:-—")
                if not sentence or SOURCE_ID_RE.search(sentence):
                    continue
                sentence_adoption_ok = (
                    classification != "AI_ADOPTION" or _has_ai_adoption_evidence(sentence)
                )
                if (
                    AI_SUBJECT_RE.search(sentence)
                    and BUSINESS_IMPACT_RE.search(sentence)
                    and sentence_adoption_ok
                ):
                    bounded = _trim_words(sentence, 26).strip(" ,;:-—")
                    bounded_adoption_ok = (
                        classification != "AI_ADOPTION" or _has_ai_adoption_evidence(bounded)
                    )
                    if (
                        AI_SUBJECT_RE.search(bounded)
                        and BUSINESS_IMPACT_RE.search(bounded)
                        and bounded_adoption_ok
                    ):
                        candidate = bounded.rstrip(".!?") + "."
                        break
            if candidate is not None:
                break
        if candidate is None:
            continue

        item["meaning"] = candidate
        item["reader_copy_completed_from_source"] = source_ids[0]
        repairs.append(f"focus_numbers[{index}].meaning")
    return repaired, repairs


def add_final_attempt_action_fallback(plan: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Add one source-bound action only when a dynamic final attempt returns none.

    The fallback is deliberately conservative: it uses a selected Newsroom item's
    source IDs and action posture, adds no factual claim, and leaves every valid
    planner-supplied action untouched.
    """
    repaired = copy.deepcopy(plan)
    actions = repaired.get("executive_actions")
    if not _is_dynamic_revision(repaired) or not isinstance(actions, list) or actions:
        return repaired, []

    evidence_items = repaired.get("evidence_items")
    if not isinstance(evidence_items, list):
        return repaired, []
    source_item = next(
        (
            item
            for item in evidence_items
            if isinstance(item, dict)
            and item.get("action_tag") == "ACT"
            and item.get("source_ids")
        ),
        None,
    )
    if source_item is None:
        source_item = next(
            (
                item
                for item in evidence_items
                if isinstance(item, dict) and item.get("source_ids")
            ),
            None,
        )
    if source_item is None:
        return repaired, []

    source_ids = [str(source_id) for source_id in source_item.get("source_ids") or []]
    source_posture = str(source_item.get("action_tag", "WATCH"))
    action_tag = source_posture if source_posture in {"ACT", "OPPORTUNITY"} else "WATCH"
    headline = {
        "ACT": "Decide what changes now",
        "OPPORTUNITY": "Test the business opening",
        "WATCH": "Watch the business consequence",
    }[action_tag]
    actions.append({
        "action_tag": action_tag,
        "headline": headline,
        "instruction": "Review the selected evidence and decide whether it changes one current business priority this week.",
        "source_ids": source_ids,
        "evidence_basis": str(source_item.get("headline", "")).strip(),
        "fallback_generated": True,
    })
    return repaired, ["executive_actions[0]"]


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


def validate_judgement_plan(
    plan: dict[str, Any],
    available_source_ids: set[str],
    focus_eligible_source_ids: set[str] | None = None,
    verified_mix_by_source: dict[str, str] | None = None,
    allocated_source_ids: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
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
        AI_ADOPTION_REVISION,
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
    newsroom_ai_business_items = 0
    newsroom_ai_adoption_items = 0
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
        if focus_numbers_revision and not _headline_is_complete(item["headline"]):
            raise JudgementPlanError("Newsroom headline must end as a complete phrase")
        if _words(item["evidence"]) > 28:
            raise JudgementPlanError("Evidence item exceeds 28 words")
        newsroom_source_ids.update(source_ids)
        if focus_numbers_revision:
            mix_classification = str(item.get("mix_classification", "")).strip()
            allowed_mix_types = (
                AI_ADOPTION_MIX_TYPES if _is_ai_adoption_revision(plan) else CONTENT_MIX_TYPES
            )
            if mix_classification not in allowed_mix_types:
                raise JudgementPlanError("Newsroom story has an invalid content-mix classification")
            if verified_mix_by_source is not None:
                if len(source_ids) != 1:
                    raise JudgementPlanError(
                        "Newsroom mix verification requires exactly one independently classified source"
                    )
                source_id = next(iter(source_ids))
                verified_classification = verified_mix_by_source.get(source_id)
                if verified_classification is None:
                    raise JudgementPlanError(
                        f"Newsroom source {source_id} is not eligible for the verified content mix"
                    )
                if mix_classification != verified_classification:
                    raise JudgementPlanError(
                        f"Newsroom source {source_id} is verified as {verified_classification}, "
                        f"not {mix_classification}"
                    )
            if mix_classification in {"AI_BUSINESS", "AI_ADOPTION", "AI_INDUSTRY_IMPACT"}:
                connection = str(item.get("ai_business_connection", "")).strip()
                if not connection or _words(connection) > 28:
                    raise JudgementPlanError(
                        "AI Newsroom story requires a substantive connection in no more than 28 words"
                    )
                newsroom_ai_business_items += 1
                if mix_classification == "AI_ADOPTION":
                    newsroom_ai_adoption_items += 1
            _validate_reader_visible_mix_copy(
                item,
                mix_classification,
                section="Newsroom",
            )

    if not str(plan.get("interpretation", "")).strip() or _words(plan["interpretation"]) > 55:
        raise JudgementPlanError("Edition-level interpretation is missing or exceeds 55 words")
    if dynamic_revision:
        interpretation_headline = str(plan.get("interpretation_headline", "")).strip()
        if (
            not interpretation_headline
            or _words(interpretation_headline) > 10
            or not _headline_is_complete(interpretation_headline)
        ):
            raise JudgementPlanError("WHY IT MATTERS headline is missing, incomplete or exceeds 10 words")

    founders_note = plan["founders_note"]
    headline = str(founders_note.get("headline", "")).strip()
    body = str(founders_note.get("body", "")).strip()
    if (
        not headline
        or _words(headline) > 12
        or (dynamic_revision and not _headline_is_complete(headline))
    ):
        raise JudgementPlanError("FOUNDER'S NOTE headline is missing, incomplete or exceeds 12 words")
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
        focus_ai_business_items = 0
        focus_ai_adoption_items = 0
        for index, item in enumerate(focus_numbers):
            if not isinstance(item, dict):
                raise JudgementPlanError(f"Focus number {index + 1} is not structured")
            source_ids = set(item.get("source_ids") or [])
            if not source_ids or not source_ids.issubset(available_source_ids):
                raise JudgementPlanError(
                    f"Focus number {index + 1} cites unknown source IDs: {sorted(source_ids)}"
                )
            if (
                focus_eligible_source_ids is not None
                and not source_ids.issubset(focus_eligible_source_ids)
            ):
                raise JudgementPlanError(
                    f"Focus number {index + 1} cites source IDs without pre-verified "
                    f"numeric evidence: {sorted(source_ids.difference(focus_eligible_source_ids))}"
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
            allowed_mix_types = (
                AI_ADOPTION_MIX_TYPES if _is_ai_adoption_revision(plan) else CONTENT_MIX_TYPES
            )
            if mix_classification not in allowed_mix_types:
                raise JudgementPlanError(
                    f"Focus number {index + 1} has an invalid content-mix classification"
                )
            if verified_mix_by_source is not None:
                if len(source_ids) != 1:
                    raise JudgementPlanError(
                        f"Focus number {index + 1} mix verification requires exactly one independently classified source"
                    )
                source_id = next(iter(source_ids))
                verified_classification = verified_mix_by_source.get(source_id)
                if verified_classification is None:
                    raise JudgementPlanError(
                        f"Focus number {index + 1} source {source_id} is not eligible for the verified content mix"
                    )
                if mix_classification != verified_classification:
                    raise JudgementPlanError(
                        f"Focus number {index + 1} source {source_id} is verified as "
                        f"{verified_classification}, not {mix_classification}"
                    )
            if mix_classification in {"AI_BUSINESS", "AI_ADOPTION", "AI_INDUSTRY_IMPACT"}:
                connection = str(item.get("ai_business_connection", "")).strip()
                if not connection or _words(connection) > 28:
                    raise JudgementPlanError(
                        f"AI Focus number {index + 1} requires a substantive connection in no more than 28 words"
                    )
                focus_ai_business_items += 1
                if mix_classification == "AI_ADOPTION":
                    focus_ai_adoption_items += 1
            _validate_reader_visible_mix_copy(
                item,
                mix_classification,
                section="Focus",
            )
            focus_source_ids.update(source_ids)
        overlap = newsroom_source_ids.intersection(focus_source_ids)
        if overlap:
            raise JudgementPlanError(
                "Newsroom stories and FOCUS ON THE NUMBERS must use distinct sources; "
                f"overlap: {sorted(overlap)}"
            )
        if allocated_source_ids is not None:
            expected_newsroom = set(allocated_source_ids.get("newsroom") or [])
            expected_focus = set(allocated_source_ids.get("focus_numbers") or [])
            if newsroom_source_ids != expected_newsroom or focus_source_ids != expected_focus:
                raise JudgementPlanError(
                    "Planner source selection does not match the preallocated section contract"
                )
        if _is_ai_adoption_revision(plan):
            adoption_items = newsroom_ai_adoption_items + focus_ai_adoption_items
            industry_items = 10 - adoption_items
            if adoption_items < MIN_AI_ADOPTION_ITEMS or industry_items > MAX_AI_INDUSTRY_IMPACT_ITEMS:
                raise JudgementPlanError(
                    "The all-AI adoption-first mix requires at least 8 AI_ADOPTION and at most "
                    f"2 AI_INDUSTRY_IMPACT items; received {adoption_items}/{industry_items}"
                )
        else:
            ai_business_items = newsroom_ai_business_items + focus_ai_business_items
            if (
                newsroom_ai_business_items != REQUIRED_AI_BUSINESS_PER_SECTION
                or focus_ai_business_items != REQUIRED_AI_BUSINESS_PER_SECTION
                or ai_business_items != REQUIRED_AI_BUSINESS_ITEMS
            ):
                raise JudgementPlanError(
                    "The approved content mix requires exactly 3 AI_BUSINESS and 2 MAJOR_BUSINESS "
                    "items in each section (6/4 overall); received "
                    f"Newsroom {newsroom_ai_business_items}/{5 - newsroom_ai_business_items}, "
                    f"Focus {focus_ai_business_items}/{5 - focus_ai_business_items}"
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
        if not counter_headline or _words(counter_headline) > 10 or not _headline_is_complete(counter_headline):
            raise JudgementPlanError("THE OTHER SIDE headline is missing, incomplete or exceeds 10 words")

    actions = plan["executive_actions"]
    if not isinstance(actions, list) or not 1 <= len(actions) <= 3:
        raise JudgementPlanError("Edition requires 1-3 executive actions")
    if dynamic_revision:
        for action in actions:
            if not isinstance(action, dict):
                raise JudgementPlanError("Dynamic executive actions must be structured")
            if action.get("action_tag") not in ACTION_TAGS:
                raise JudgementPlanError("Executive action has an invalid action tag")
            if (
                not str(action.get("headline", "")).strip()
                or _words(action["headline"]) > 6
                or not _headline_is_complete(action["headline"])
            ):
                raise JudgementPlanError("Executive action headline is missing, incomplete or exceeds six words")
            if not str(action.get("instruction", "")).strip() or _words(action["instruction"]) > 20:
                raise JudgementPlanError("Executive action instruction is missing or exceeds 20 words")
            action_source_ids = action.get("source_ids")
            if action_source_ids is not None:
                source_ids = set(action_source_ids)
                if not source_ids or not source_ids.issubset(available_source_ids):
                    raise JudgementPlanError(
                        f"Executive action cites unknown source IDs: {sorted(source_ids)}"
                    )
    elif any(_words(action) > 24 for action in actions):
        raise JudgementPlanError("Executive action exceeds 24 words")

    executive_read = plan["executive_read"]
    if _words(executive_read.get("dtl_view", "")) > 75:
        raise JudgementPlanError("Executive Read exceeds 75 words")
    if any(_words(item) > 32 for item in executive_read.get("watch_items", [])):
        raise JudgementPlanError("What to Watch item exceeds 32 words")

    if dynamic_revision:
        watch_headline = str(executive_read.get("watch_headline", "")).strip()
        if not watch_headline or _words(watch_headline) > 10 or not _headline_is_complete(watch_headline):
            raise JudgementPlanError("WATCH FOR THIS headline is missing, incomplete or exceeds 10 words")
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
    prompt_template = prompt_path.read_text()
    planner_evidence, focus_eligible_source_ids = prepare_focus_number_evidence(evidence_items)
    verified_mix_by_source: dict[str, str] | None = None
    verified_ai_source_ids: list[str] = []
    verified_major_source_ids: list[str] = []
    verified_adoption_source_ids: list[str] = []
    verified_industry_source_ids: list[str] = []
    allocated_source_ids: dict[str, list[str]] | None = None
    if (
        (FOCUS_NUMBERS_REVISION in prompt_template or AI_ADOPTION_REVISION in prompt_template)
        and len(focus_eligible_source_ids) < 5
    ):
        raise JudgementPlanError(
            "FOCUS ON THE NUMBERS requires at least five distinct source records "
            "with pre-verified numeric evidence; received "
            f"{len(focus_eligible_source_ids)}"
        )
    if AI_ADOPTION_REVISION in prompt_template:
        planner_evidence, verified_mix_by_source = prepare_ai_adoption_evidence(planner_evidence)
        verified_adoption_source_ids = sorted(
            source_id for source_id, classification in verified_mix_by_source.items()
            if classification == "AI_ADOPTION"
        )
        verified_industry_source_ids = sorted(
            source_id for source_id, classification in verified_mix_by_source.items()
            if classification == "AI_INDUSTRY_IMPACT"
        )
        if len(verified_adoption_source_ids) < MIN_AI_ADOPTION_ITEMS or (
            len(verified_adoption_source_ids) + len(verified_industry_source_ids) < 10
        ):
            raise JudgementPlanError(
                "The all-AI adoption-first edition requires at least eight verified AI adoption "
                "sources and ten AI sources overall; received "
                f"{len(verified_adoption_source_ids)} and "
                f"{len(verified_adoption_source_ids) + len(verified_industry_source_ids)}"
            )
        allocated_source_ids = allocate_ai_adoption_content(
            planner_evidence,
            focus_eligible_source_ids,
            verified_mix_by_source,
        )
    elif FOCUS_NUMBERS_REVISION in prompt_template:
        planner_evidence, verified_mix_by_source = prepare_content_mix_evidence(planner_evidence)
        verified_ai_source_ids = sorted(
            source_id
            for source_id, classification in verified_mix_by_source.items()
            if classification == "AI_BUSINESS"
        )
        verified_major_source_ids = sorted(
            source_id
            for source_id, classification in verified_mix_by_source.items()
            if classification == "MAJOR_BUSINESS"
        )
        if len(verified_ai_source_ids) < 6 or len(verified_major_source_ids) < 4:
            raise JudgementPlanError(
                "The approved 60/40 edition requires at least six independently verified "
                "AI-business sources and four independently verified major-business sources; "
                f"received {len(verified_ai_source_ids)} and {len(verified_major_source_ids)}"
            )
        allocated_source_ids = allocate_focus_numbers_content_mix(
            planner_evidence,
            focus_eligible_source_ids,
            verified_mix_by_source,
        )
    prompt_evidence = planner_evidence
    if allocated_source_ids:
        selected_source_ids = set(
            allocated_source_ids["newsroom"] + allocated_source_ids["focus_numbers"]
        )
        prompt_evidence = [
            item
            for item in planner_evidence
            if str(item.get("source_id", "")) in selected_source_ids
        ]
    prompt = prompt_template.replace(
        "{EVIDENCE_ITEMS}", json.dumps(prompt_evidence, indent=2)
    ).replace(
        "{SIGNAL_MEMORY}", json.dumps(prior_memory, indent=2)
    ).replace(
        "{FOCUS_NUMBER_ELIGIBLE_SOURCE_IDS}", json.dumps(sorted(focus_eligible_source_ids))
    ).replace(
        "{AI_BUSINESS_SOURCE_IDS}", json.dumps(verified_ai_source_ids)
    ).replace(
        "{MAJOR_BUSINESS_SOURCE_IDS}", json.dumps(verified_major_source_ids)
    ).replace(
        "{AI_ADOPTION_SOURCE_IDS}", json.dumps(verified_adoption_source_ids)
    ).replace(
        "{AI_INDUSTRY_IMPACT_SOURCE_IDS}", json.dumps(verified_industry_source_ids)
    ).replace(
        "{NEWSROOM_SOURCE_IDS}", json.dumps(allocated_source_ids["newsroom"] if allocated_source_ids else [])
    ).replace(
        "{FOCUS_NUMBER_SOURCE_IDS}", json.dumps(allocated_source_ids["focus_numbers"] if allocated_source_ids else [])
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
                candidate, figure_repairs = recover_missing_focus_figures(candidate, planner_evidence)
                repairs.extend(figure_repairs)
                candidate, reader_copy_repairs = complete_ai_focus_reader_copy(
                    candidate,
                    planner_evidence,
                )
                repairs.extend(reader_copy_repairs)
                candidate, action_repairs = add_final_attempt_action_fallback(candidate)
                repairs.extend(action_repairs)
                if repairs:
                    log.warning(
                        "Judgement planning final attempt normalised bounded fields: %s",
                        ", ".join(repairs),
                    )
            return validate_judgement_plan(
                candidate,
                source_ids,
                focus_eligible_source_ids if _is_focus_numbers_revision(candidate) else None,
                verified_mix_by_source if _is_focus_numbers_revision(candidate) else None,
                allocated_source_ids if _is_focus_numbers_revision(candidate) else None,
            )
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
                "source_evidence": getattr(raw, "source_evidence", "")[:2500],
                "scoring_reason": scored.reason,
            }
        )
    return evidence
