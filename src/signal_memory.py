"""Portable position memory for DTL Signal.

The JSON contract can later move to durable database or object storage without
changing the judgement planner or email renderer.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import requests


EMPTY_MEMORY: dict[str, Any] = {"version": 1, "positions": [], "events": [], "alive_moments": []}
log = logging.getLogger(__name__)
MEMORY_COMMENT_RE = re.compile(r"<!-- dtl-signal-memory:([A-Za-z0-9+/=]+) -->")
RESEND_EMAILS_URL = "https://api.resend.com/emails"
DELIVERED_EVENTS = {"delivered", "opened", "clicked"}


def load_signal_memory(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "positions": [], "events": []}
    data = json.loads(path.read_text())
    data.setdefault("version", 1)
    data.setdefault("positions", [])
    data.setdefault("events", [])
    data.setdefault("alive_moments", [])
    return data


def memory_context(memory: dict[str, Any], max_positions: int = 12) -> dict[str, Any]:
    positions = sorted(
        memory.get("positions", []),
        key=lambda item: item.get("updated_at", item.get("first_observed", "")),
        reverse=True,
    )[:max_positions]
    return {"version": memory.get("version", 1), "positions": positions}


def apply_memory_update(
    memory: dict[str, Any],
    memory_update: dict[str, Any],
    what_changed: dict[str, Any],
    edition_number: int,
    delivered_at: str,
) -> dict[str, Any]:
    """Return updated memory. Call only after successful production delivery."""
    updated = json.loads(json.dumps(memory))
    positions = updated.setdefault("positions", [])
    position_id = memory_update["position_id"]
    existing = next((item for item in positions if item.get("position_id") == position_id), None)
    position = {
        "position_id": position_id,
        "theme": memory_update["theme"],
        "statement": memory_update["statement"],
        "confidence": memory_update["confidence"],
        "updated_at": delivered_at,
        "supporting_source_ids": memory_update.get("supporting_source_ids", []),
    }
    if existing:
        first_observed = existing.get("first_observed")
        existing.clear()
        existing.update(position)
        if first_observed:
            existing["first_observed"] = first_observed
    else:
        position["first_observed"] = delivered_at
        positions.append(position)

    updated.setdefault("events", []).append(
        {
            "edition_number": edition_number,
            "recorded_at": delivered_at,
            "position_id": position_id,
            "classification": what_changed["classification"],
            "explanation": what_changed["explanation"],
        }
    )
    return updated


def apply_alive_moment_update(
    memory: dict[str, Any],
    moment: dict[str, Any],
    *,
    edition_number: int,
    delivered_at: str,
) -> dict[str, Any]:
    """Persist delivered image identity in the same provider-backed capsule as Signal Memory."""
    updated = json.loads(json.dumps(memory))
    history = updated.setdefault("alive_moments", [])
    record = {
        "id": moment.get("id"),
        "edition_id": f"{edition_number:04d}",
        "date": moment.get("date"),
        "published_at": delivered_at,
        "location": moment.get("location"),
        "country": moment.get("country"),
        "category": moment.get("category"),
        "dominant_colour_family": moment.get("dominant_colour_family"),
        "colour_harmony_note": moment.get("colour_harmony_note"),
        "species": moment.get("species"),
        "image_url": moment.get("image_url"),
        "image_original_url": moment.get("image_original_url"),
        "image_source_url": moment.get("image_source_url"),
        "photographer": moment.get("photographer"),
    }
    identity = (
        record.get("image_original_url")
        or record.get("image_source_url")
        or record.get("image_url")
        or record.get("id")
    )
    existing = {
        item.get("image_original_url")
        or item.get("image_source_url")
        or item.get("image_url")
        or item.get("id")
        for item in history
        if isinstance(item, dict)
    }
    if identity and identity not in existing:
        history.append(record)
    updated["alive_moments"] = history[-365:]
    return updated


def alive_history_from_memory(memory: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in memory.get("alive_moments", []) if isinstance(item, dict)]


def extract_alive_moment_identity(html: str) -> dict[str, Any] | None:
    """Recover legacy delivered-image identity when the first capsules predated image history."""
    marker = (html or "").find("REMEMBER THE WORLD")
    if marker < 0:
        return None
    section = (html or "")[marker:marker + 7000]
    image = re.search(r'<img[^>]+src="([^"]+)"[^>]+alt="([^"]*)"', section, re.IGNORECASE)
    source = re.search(r'href="([^"]+)"[^>]*>image source</a>', section, re.IGNORECASE)
    if not image:
        return None
    image_url = image.group(1)
    source_url = source.group(1) if source else ""
    return {
        "id": "recovered-" + __import__("hashlib").sha256((source_url or image_url).encode()).hexdigest()[:16],
        "image_url": image_url,
        "image_source_url": source_url,
        "alt": image.group(2),
    }


def save_signal_memory(path: Path, memory: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(memory, indent=2) + "\n")


def embed_delivery_memory(html: str, memory: dict[str, Any]) -> str:
    """Append an invisible machine-readable capsule without changing layout."""
    raw = json.dumps(memory, separators=(",", ":"), ensure_ascii=True).encode()
    encoded = base64.b64encode(raw).decode("ascii")
    return html + f"<!-- dtl-signal-memory:{encoded} -->"


def extract_delivery_memory(html: str) -> dict[str, Any] | None:
    match = MEMORY_COMMENT_RE.search(html or "")
    if not match:
        return None
    try:
        memory = json.loads(base64.b64decode(match.group(1)).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(memory, dict) or not isinstance(memory.get("positions"), list):
        return None
    memory.setdefault("version", 1)
    memory.setdefault("events", [])
    return memory


def _tags_by_name(email: dict[str, Any]) -> dict[str, str]:
    return {
        str(item.get("name")): str(item.get("value"))
        for item in (email.get("tags") or [])
        if isinstance(item, dict)
    }


def recover_signal_memory_from_resend(
    api_key: str | None = None,
    *,
    list_limit: int = 100,
    candidate_limit: int = 10,
) -> dict[str, Any]:
    """Recover the latest delivered Enhanced production memory from Resend.

    Proof subjects are rejected before retrieval. Retrieved messages must carry
    explicit Enhanced/production tags and a delivered/opened/clicked event.
    Any provider failure degrades safely to empty memory rather than blocking a
    send or trusting local ephemeral state.
    """
    key = api_key or os.environ.get("RESEND_API_KEY")
    if not key:
        return json.loads(json.dumps(EMPTY_MEMORY))
    headers = {"Authorization": f"Bearer {key}"}
    try:
        response = requests.get(
            RESEND_EMAILS_URL,
            headers=headers,
            params={"limit": max(1, min(list_limit, 100))},
            timeout=15,
        )
        response.raise_for_status()
        summaries = response.json().get("data", [])
    except Exception as exc:
        log.warning("Resend memory list recovery failed: %s", exc)
        return json.loads(json.dumps(EMPTY_MEMORY))

    candidates = 0
    latest_memory: dict[str, Any] | None = None
    delivered_alive: list[dict[str, Any]] = []
    for summary in summaries:
        subject = str(summary.get("subject", ""))
        if subject.startswith("[PROOF]") or not subject.startswith("DTL Signal | Edition"):
            continue
        if str(summary.get("last_event", "")).lower() not in DELIVERED_EVENTS:
            continue
        candidates += 1
        if candidates > candidate_limit:
            break
        email_id = summary.get("id")
        if not email_id:
            continue
        try:
            response = requests.get(
                f"{RESEND_EMAILS_URL}/{email_id}",
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            email = response.json()
        except Exception as exc:
            log.warning("Resend memory retrieve failed for %s: %s", email_id, exc)
            continue
        tags = _tags_by_name(email)
        if not (
            tags.get("message_type") == "signal"
            and tags.get("format") in {"enhanced-v4", "enhanced-v4-focus-numbers"}
            and tags.get("delivery_mode") == "production"
        ):
            continue
        if str(email.get("last_event", "")).lower() not in DELIVERED_EVENTS:
            continue
        html = str(email.get("html", ""))
        memory = extract_delivery_memory(html)
        if memory is not None and latest_memory is None:
            latest_memory = memory
            log.info("Recovered Enhanced Signal Memory from Resend email %s", email_id)
        if memory is not None:
            delivered_alive.extend(alive_history_from_memory(memory))
        legacy_alive = extract_alive_moment_identity(html)
        if legacy_alive is not None:
            delivered_alive.append(legacy_alive)

    recovered = latest_memory or json.loads(json.dumps(EMPTY_MEMORY))
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in delivered_alive:
        identity = str(
            item.get("image_original_url")
            or item.get("image_source_url")
            or item.get("image_url")
            or item.get("id")
            or ""
        )
        if identity and identity not in seen:
            seen.add(identity)
            merged.append(item)
    if merged:
        recovered["alive_moments"] = merged[-365:]
        log.info("Recovered %d delivered REMEMBER THE WORLD image identities", len(merged))
    return recovered
