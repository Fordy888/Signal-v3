"""Graceful section omission for Signal editions.

This replaces the all-or-nothing quota gates that used to fail a whole edition
whenever one section could not be filled.

The rule, in one line: **an optional section that cannot meet its evidence bar
is omitted and the reason is recorded — the bar is never lowered, and the
edition is never failed for it.**

Two classes of section:

MANDATORY — without these there is no edition worth sending, so the run halts:
    * Today's Signal thesis   (``interpretation_headline`` + ``interpretation``)
    * Top Signals, >= 3 items (``evidence_items``)
    * Founder's Note          (``founders_note.headline`` + ``.body``)
    * Executive Read          (the rendered read; see ``_read_bar`` for why this
                               is layout-aware)

OPTIONAL — omitted and logged, never fatal:
    * FOCUS ON THE NUMBERS        (``focus_numbers``)
    * THE OTHER SIDE              (``counter_signal.headline`` + ``.statement``)
    * WHAT WOULD CHANGE OUR VIEW  (``counter_signal.would_change_view_if``)
    * WATCH FOR THIS              (``executive_read.watch_headline`` + ``.watch_items``)
    * Remember the World          (the alive moment)
    * Dad Joke                    (the human signal)

Omissions are returned so the orchestrator can put them in the run receipt.
Nothing here rewrites editorial content: a section either qualifies as the
planner produced it, or it does not appear.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

# Layouts that render FOCUS ON THE NUMBERS instead of THE ONE THING. Kept in
# step with enhanced_renderer.focus_numbers_revision.
FOCUS_LAYOUTS = {"focus-on-the-numbers-v1", "ai-adoption-v1"}

# FOCUS ON THE NUMBERS is a five-figure panel. Four figures is not a smaller
# panel, it is a different section — so the bar is exact, and short means omit.
FOCUS_NUMBERS_REQUIRED = 5

# The planner is contracted for "two or three observable developments".
WATCH_ITEMS_REQUIRED = 2

MIN_TOP_SIGNALS = 3


class EditionHalt(RuntimeError):
    """A mandatory section could not be built — there is no edition to send."""


@dataclass(frozen=True)
class Omission:
    """One optional section that did not make the edition."""

    section: str
    reason: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.section}: {self.reason}"


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _filled(container: Any, key: str) -> bool:
    return isinstance(container, dict) and bool(_text(container.get(key)))


def _is_focus_layout(plan: dict[str, Any]) -> bool:
    return plan.get("editorial_revision") in FOCUS_LAYOUTS


# ─────────────────────────────── mandatory ────────────────────────────────


def _read_bar(plan: dict[str, Any]) -> str | None:
    """Return a failure reason for the Executive Read, or None if it qualifies.

    Layout-aware on purpose. In the ai-adoption / focus layouts the reader-facing
    read is the WHY IT MATTERS block, which is driven by ``interpretation``;
    ``executive_read.dtl_view`` is planner-internal there and never rendered, so
    requiring it would halt an edition that renders perfectly. In the older
    layout the EXECUTIVE READ block is rendered from ``interpretation`` as well,
    so the bar is the same — but we still require the ``executive_read`` object
    to exist, because WATCH FOR THIS is evaluated from it.
    """
    if not isinstance(plan.get("executive_read"), dict):
        return "planner returned no executive_read object"
    if not _text(plan.get("interpretation")):
        return "no interpretation text to carry the read"
    return None


def check_mandatory(plan: dict[str, Any]) -> None:
    """Raise EditionHalt if any mandatory section cannot be built.

    All failures are collected so one halt reports everything that is wrong,
    rather than making the operator fix them one run at a time.
    """
    failures: list[str] = []

    if not _text(plan.get("interpretation_headline")) or not _text(plan.get("interpretation")):
        failures.append("Today's Signal thesis: interpretation_headline/interpretation missing")

    items = plan.get("evidence_items")
    count = len(items) if isinstance(items, list) else 0
    if count < MIN_TOP_SIGNALS:
        failures.append(f"Top Signals: {count} item(s), needs >= {MIN_TOP_SIGNALS}")

    note = plan.get("founders_note")
    if not _filled(note, "headline") or not _filled(note, "body"):
        failures.append("Founder's Note: headline/body missing")

    read_failure = _read_bar(plan)
    if read_failure:
        failures.append(f"Executive Read: {read_failure}")

    if failures:
        raise EditionHalt(
            "Mandatory section(s) could not be built: " + "; ".join(failures)
        )


# ─────────────────────────────── optional ─────────────────────────────────


def _focus_numbers_omission(plan: dict[str, Any]) -> str | None:
    if not _is_focus_layout(plan):
        return None  # not part of this layout at all — not an omission
    entries = plan.get("focus_numbers")
    if not isinstance(entries, list) or len(entries) != FOCUS_NUMBERS_REQUIRED:
        found = len(entries) if isinstance(entries, list) else 0
        return (
            f"needs exactly {FOCUS_NUMBERS_REQUIRED} source-bound figures, "
            f"planner supplied {found}"
        )
    for position, entry in enumerate(entries, 1):
        for field in ("entity", "number", "meaning"):
            if not _filled(entry, field):
                return f"figure {position} has no {field}"
        if not entry.get("source_ids"):
            return f"figure {position} is not bound to a source"
    return None


def apply_section_policy(
    plan: dict[str, Any],
    *,
    alive_moment: dict[str, Any] | None = None,
    joke: dict[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, str] | None, list[Omission]]:
    """Enforce mandatory sections, drop optional ones that miss their bar.

    Returns ``(plan, alive_moment, joke, omissions)``. The plan is mutated only
    by *removing* sections that did not qualify, so the renderer's existing
    guards skip them. Content is never rewritten or padded.
    """
    check_mandatory(plan)

    omissions: list[Omission] = []

    def omit(section: str, reason: str) -> None:
        omissions.append(Omission(section, reason))
        log.info("Section omitted — %s: %s", section, reason)

    # FOCUS ON THE NUMBERS
    reason = _focus_numbers_omission(plan)
    if reason:
        plan.pop("focus_numbers", None)
        omit("FOCUS ON THE NUMBERS", reason)

    # THE OTHER SIDE / WHAT WOULD CHANGE OUR VIEW — the panel is the parent, so
    # losing the panel implicitly loses the line inside it.
    counter = plan.get("counter_signal")
    if not _filled(counter, "headline") or not _filled(counter, "statement"):
        plan.pop("counter_signal", None)
        omit("THE OTHER SIDE", "no counter-signal headline/statement from the planner")
    elif not _filled(counter, "would_change_view_if"):
        counter.pop("would_change_view_if", None)
        omit(
            "WHAT WOULD CHANGE OUR VIEW",
            "counter-signal carried no falsifying evidence condition",
        )

    # WATCH FOR THIS
    read = plan.get("executive_read")
    watch_items = read.get("watch_items") if isinstance(read, dict) else None
    valid_items = [w for w in watch_items if _text(w)] if isinstance(watch_items, list) else []
    if not _filled(read, "watch_headline") or len(valid_items) < WATCH_ITEMS_REQUIRED:
        if isinstance(read, dict):
            read.pop("watch_headline", None)
            read.pop("watch_items", None)
        omit(
            "WATCH FOR THIS",
            f"needs a headline and >= {WATCH_ITEMS_REQUIRED} observable items, "
            f"got {len(valid_items)}",
        )
    elif len(valid_items) != len(watch_items):
        read["watch_items"] = valid_items

    # Remember the World (alive moment)
    if not isinstance(alive_moment, dict) or not alive_moment:
        alive_moment = None
        omit("Remember the World", "no alive moment available for today")

    # Dad Joke (human signal)
    if not _filled(joke, "setup") or not _filled(joke, "punchline"):
        joke = None
        omit("Dad Joke", "no approved joke with a setup and punchline was selected")

    return plan, alive_moment, joke, omissions


def format_omissions(omissions: list[Omission]) -> str:
    """One plain-English line for the run receipt."""
    if not omissions:
        return "Sections omitted: none — every optional section met its evidence bar."
    return "Sections omitted: " + "; ".join(str(o) for o in omissions)
