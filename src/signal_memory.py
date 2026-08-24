"""Portable position memory for DTL Signal.

The JSON contract can later move to durable database or object storage without
changing the judgement planner or email renderer.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EMPTY_MEMORY: dict[str, Any] = {"version": 1, "positions": [], "events": []}


def load_signal_memory(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "positions": [], "events": []}
    data = json.loads(path.read_text())
    data.setdefault("version", 1)
    data.setdefault("positions", [])
    data.setdefault("events", [])
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


def save_signal_memory(path: Path, memory: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(memory, indent=2) + "\n")

