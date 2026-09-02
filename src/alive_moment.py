"""Governed WE ARE ALIVE moment validation, rotation and rendering.

Portable editorial IP: no delivery, database or provider dependencies.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Any


ALLOWED_LICENCES = {"CC0", "CC BY 4.0", "CC BY-SA 4.0", "PUBLIC DOMAIN"}
ALLOWED_CATEGORIES = {
    "animals", "birds", "marine_life", "flowers", "forests", "landscapes",
    "weather", "seasons", "new_life", "migration", "water", "sky",
    "human_craft", "culture", "architecture",
}
ALLOWED_DOMINANT_COLOUR_FAMILIES = {"coral", "amber", "aqua", "deep_teal", "neutral"}
COLOUR_GOVERNANCE_START = date(2026, 9, 1)
PROHIBITED_TERMS = {
    "disaster", "catastrophe", "death", "dead", "killed", "campaign",
    "sponsored", "book now", "click", "learn more", "why it matters",
}


class AliveMomentError(ValueError):
    """Raised when a proposed moment does not clear the governed threshold."""


def load_alive_moment(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_alive_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    return payload if isinstance(payload, list) else []


def _parse_mmdd(value: str, year: int) -> date:
    month, day = (int(part) for part in value.split("-"))
    return date(year, month, day)


def is_seasonally_current(moment: dict[str, Any]) -> bool:
    edition_date = date.fromisoformat(moment["date"])
    start = _parse_mmdd(moment["season_start"], edition_date.year)
    end = _parse_mmdd(moment["season_end"], edition_date.year)
    if start <= end:
        return start <= edition_date <= end
    return edition_date >= start or edition_date <= end


def _normalise(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def validate_alive_moment(
    moment: dict[str, Any],
    history: list[dict[str, Any]] | None = None,
    *,
    recent_window: int = 21,
    expected_edition_id: str | None = None,
    expected_date: str | None = None,
) -> dict[str, Any]:
    required = {
        "id", "edition_id", "date", "location", "country", "region",
        "phenomenon", "category", "season", "season_start", "season_end",
        "caption", "verification_source", "verification_status",
        "image_source", "image_url", "image_source_url", "image_location",
        "photographer", "licence_type", "licence_url", "attribution_required",
        "attribution_text", "image_authenticity", "is_ai_generated",
        "editorial_status", "selected_at",
    }
    missing = sorted(required - set(moment))
    if missing:
        raise AliveMomentError(f"Missing alive_moment fields: {', '.join(missing)}")
    if moment["verification_status"] != "VERIFIED":
        raise AliveMomentError("Moment is not verified")
    if moment["editorial_status"] not in {"APPROVED_FOR_PROOF", "APPROVED"}:
        raise AliveMomentError("Moment lacks human editorial approval")
    if expected_edition_id and str(moment.get("edition_id")) != expected_edition_id:
        raise AliveMomentError("Moment is not approved for this edition")
    if expected_date and str(moment.get("date")) != expected_date:
        raise AliveMomentError("Moment is not approved for this issue date")
    if moment["category"] not in ALLOWED_CATEGORIES:
        raise AliveMomentError("Category is outside the grounding editorial palette")
    if date.fromisoformat(moment["date"]) >= COLOUR_GOVERNANCE_START:
        if moment.get("dominant_colour_family") not in ALLOWED_DOMINANT_COLOUR_FAMILIES:
            raise AliveMomentError("Photograph has an unsupported natural colour family")
        if not str(moment.get("colour_harmony_note", "")).strip():
            raise AliveMomentError("Photograph colour-harmony assessment is missing")
    if moment["licence_type"] not in ALLOWED_LICENCES:
        raise AliveMomentError("Image licence is not approved for commercial reuse")
    if moment["is_ai_generated"] or moment["image_authenticity"] != "REAL_PHOTOGRAPH":
        raise AliveMomentError("WE ARE ALIVE requires a real photograph")
    if not all(str(moment[field]).startswith("https://") for field in ("verification_source", "image_url", "image_source_url", "licence_url")):
        raise AliveMomentError("All verification, image and licence URLs must use HTTPS")
    if moment["attribution_required"] and not str(moment["attribution_text"]).strip():
        raise AliveMomentError("Required image attribution is missing")
    if _normalise(moment["image_location"]) != _normalise(f'{moment["location"]}, {moment["country"]}'):
        raise AliveMomentError("Photograph location does not match the stated moment")
    if not is_seasonally_current(moment):
        raise AliveMomentError("Moment is not current on the edition date")
    combined = _normalise(f'{moment["caption"]} {moment["phenomenon"]}')
    if any(term in combined for term in PROHIBITED_TERMS):
        raise AliveMomentError("Moment contains excluded editorial framing")

    recent = (history or [])[-recent_window:]
    location = _normalise(moment["location"])
    category = _normalise(moment["category"])
    species = _normalise(moment.get("species"))
    candidate_identities = {
        _normalise(moment.get("id")),
        _normalise(moment.get("image_url")),
        _normalise(moment.get("image_original_url")),
        _normalise(moment.get("image_source_url")),
    } - {""}
    for used in recent:
        used_identities = {
            _normalise(used.get("id")),
            _normalise(used.get("image_url")),
            _normalise(used.get("image_original_url")),
            _normalise(used.get("image_source_url")),
        } - {""}
        if candidate_identities & used_identities:
            raise AliveMomentError("Image identity was used too recently")
        if _normalise(used.get("location")) == location:
            raise AliveMomentError("Location was used too recently")
        if species and _normalise(used.get("species")) == species:
            raise AliveMomentError("Species was used too recently")
    if recent and sum(_normalise(item.get("category")) == category for item in recent[-7:]) >= 2:
        raise AliveMomentError("Category has appeared too frequently")
    return moment


def record_alive_moment(path: Path, moment: dict[str, Any], published_at: str) -> None:
    history = load_alive_history(path)
    history.append(
        {
            "id": moment["id"],
            "edition_id": moment["edition_id"],
            "date": moment["date"],
            "location": moment["location"],
            "country": moment["country"],
            "category": moment["category"],
            "dominant_colour_family": moment.get("dominant_colour_family"),
            "colour_harmony_note": moment.get("colour_harmony_note"),
            "species": moment.get("species"),
            "phenomenon": moment["phenomenon"],
            "image_url": moment.get("image_url"),
            "image_original_url": moment.get("image_original_url"),
            "image_source_url": moment.get("image_source_url"),
            "photographer": moment.get("photographer"),
            "published_at": published_at,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history[-365:], indent=2) + "\n")


def render_alive_moment(moment: dict[str, Any]) -> str:
    photographer = escape(str(moment["photographer"]))
    image_source = escape(str(moment["image_source"]))
    licence_type = escape(str(moment["licence_type"]))
    licence_url = escape(str(moment["licence_url"]), quote=True)
    source_url = escape(str(moment["image_source_url"]), quote=True)
    return (
        '<tr><td style="padding:32px 40px 18px 40px;">'
        '<p style="margin:0 0 14px 0;font:800 11px monospace;color:#17A398;letter-spacing:1.8px;">REMEMBER THE WORLD</p>'
        f'<p style="margin:0 0 5px 0;font-size:18px;font-weight:800;color:#1a1a1a;">{escape(moment["location"])}, {escape(moment["country"])}</p>'
        f'<p style="margin:0 0 22px 0;font-size:14px;line-height:1.6;color:#555;">{escape(moment["caption"])}</p>'
        '<table width="100%" cellpadding="0" cellspacing="0" style="width:100%;margin:0;">'
        '<tr><td align="left">'
        f'<img src="{escape(moment["image_url"], quote=True)}" width="820" alt="{escape(moment["phenomenon"], quote=True)}" style="display:block;width:100%;max-width:820px;height:auto;border:0;border-radius:2px;" />'
        f'<p style="margin:8px 0 0 0;font-size:8px;line-height:1.4;color:#6B7280;text-align:left;"><a href="{source_url}" style="color:#6B7280;text-decoration:none;">Photo: {photographer} · {image_source}</a> · <a href="{licence_url}" style="color:#6B7280;text-decoration:underline;">{licence_type}</a></p>'
        '</td></tr></table>'
        '</td></tr>'
    )
