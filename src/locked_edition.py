"""Deterministic rendering for a human-approved production edition."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .alive_moment import load_alive_history, load_alive_moment, validate_alive_moment
from .edition_counter import edition_for_date
from .enhanced_renderer import render_enhanced_email
from .human_signal import load_joke_history, load_jokes, select_joke
from .judgement_plan import (
    prepare_ai_adoption_evidence,
    prepare_focus_number_evidence,
    validate_judgement_plan,
)


class LockedEditionError(ValueError):
    """Raised when an approved edition no longer matches its release manifest."""


def _resolve(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if root.resolve() not in path.parents:
        raise LockedEditionError(f"Locked path escapes project root: {relative}")
    if not path.exists():
        raise LockedEditionError(f"Locked file missing: {relative}")
    return path


def render_locked_edition(
    root: Path,
    edition_number: int,
) -> tuple[str, dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any] | None]:
    manifest_path = root / "data" / "locked_editions" / f"{edition_number:04d}.json"
    if not manifest_path.exists():
        raise LockedEditionError(f"No approved manifest for Edition {edition_number:04d}")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("edition_number") != edition_number:
        raise LockedEditionError("Manifest edition number mismatch")

    issue_date = date.fromisoformat(str(manifest["issue_date"]))
    if edition_for_date(issue_date) != edition_number:
        raise LockedEditionError("Manifest date does not resolve to its edition number")

    generated_at = datetime.fromisoformat(str(manifest["generated_at"]))
    if generated_at.date() != issue_date:
        raise LockedEditionError("Manifest timestamp does not match issue date")

    evidence = json.loads(_resolve(root, str(manifest["evidence_path"])).read_text())
    plan_data = json.loads(_resolve(root, str(manifest["plan_path"])).read_text())
    if plan_data.get("editorial_revision") == "ai-adoption-v1":
        evidence, focus_ids = prepare_focus_number_evidence(evidence)
        evidence, verified_mix = prepare_ai_adoption_evidence(evidence)
        allocation = {
            "newsroom": [
                str(item["source_ids"][0]) for item in plan_data.get("evidence_items", [])
            ],
            "focus_numbers": [
                str(item["source_ids"][0]) for item in plan_data.get("focus_numbers", [])
            ],
        }
        plan = validate_judgement_plan(
            plan_data,
            {str(item["source_id"]) for item in evidence},
            focus_ids,
            verified_mix,
            allocation,
        )
    else:
        plan = validate_judgement_plan(
            plan_data,
            {str(item["source_id"]) for item in evidence},
        )
    manifest_joke = manifest.get("joke")
    if isinstance(manifest_joke, dict):
        joke = {
            "setup": str(manifest_joke.get("setup", "")).strip(),
            "punchline": str(manifest_joke.get("punchline", "")).strip(),
        }
        if not joke["setup"] or not joke["punchline"]:
            raise LockedEditionError("Locked Dad Joke is incomplete")
    else:
        joke = select_joke(
            load_jokes(root / "data" / "dad_jokes.json"),
            edition_number=edition_number,
            recent_ids=load_joke_history(root / "data" / "joke_history.json"),
        )
    moment = None
    if manifest.get("include_alive_moment"):
        moment = validate_alive_moment(
            load_alive_moment(_resolve(root, str(manifest["alive_moment_path"]))),
            load_alive_history(root / "data" / "alive_moment_history.json"),
            expected_edition_id=f"{edition_number:04d}",
            expected_date=issue_date.isoformat(),
        )

    html = render_enhanced_email(
        plan=plan,
        sources=evidence,
        joke=joke,
        edition_number=edition_number,
        generated_at=generated_at,
        alive_moment=moment,
    )
    digest = hashlib.sha256(html.encode()).hexdigest()
    if digest != manifest.get("expected_html_sha256"):
        raise LockedEditionError(
            f"Edition {edition_number:04d} HTML checksum mismatch: {digest}"
        )
    return html, plan, evidence, joke, moment
