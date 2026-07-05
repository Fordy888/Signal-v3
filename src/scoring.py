"""Score raw items via Claude Haiku before passing to the synthesis layer."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic

from .sources import RawItem

log = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 20  # items below this composite score are dropped (lowered from 25 on 23 June 2026 to improve content density)
MAX_RETRIES = 3


@dataclass
class ScoredItem:
    raw: RawItem
    scores: dict[str, int]
    total: int
    reason: str

    def to_synthesis_payload(self) -> dict[str, Any]:
        return {
            "title": self.raw.title,
            "summary": self.raw.summary[:500],
            "source": self.raw.source,
            "category": self.raw.category,
            "url": self.raw.url,
            "score": self.total,
            "scoring_reason": self.reason,
        }


def _load_prompt(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def _extract_json_objects(text: str) -> list[dict[str, Any]]:
    """Pull JSON objects from a Claude response. Resilient to surrounding prose."""
    objects: list[dict[str, Any]] = []
    # Try fenced blocks first
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    for blob in fenced:
        try:
            objects.append(json.loads(blob))
        except json.JSONDecodeError:
            continue

    # If no fenced blocks, try greedy brace-matching at top level
    if not objects:
        depth = 0
        start: int | None = None
        for i, ch in enumerate(text):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    blob = text[start:i+1]
                    try:
                        objects.append(json.loads(blob))
                    except json.JSONDecodeError:
                        pass
                    start = None
    return objects


def score_items(
    items: list[RawItem],
    scoring_prompt_path: str,
    model: str | None = None,
    threshold: int = DEFAULT_THRESHOLD,
    batch_size: int = 10,
) -> list[ScoredItem]:
    """Score items in batches. Returns only items at/above threshold, sorted descending by total."""
    if not items:
        return []

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model_id = model or os.environ.get("MODEL_SCORING", "claude-haiku-4-5-20251001")
    system_prompt = _load_prompt(scoring_prompt_path)

    surviving: list[ScoredItem] = []

    # Build a lookup by item_id for matching scoring output back to RawItems
    by_id: dict[str, RawItem] = {it.item_id: it for it in items}

    for batch_start in range(0, len(items), batch_size):
        batch = items[batch_start : batch_start + batch_size]
        payload = [it.to_scoring_payload() for it in batch]
        user_msg = (
            "Score the following items. Return one JSON object per item, no preamble or wrapping prose.\n\n"
            f"ITEMS:\n{json.dumps(payload, indent=2)}"
        )

        # Retry with exponential backoff
        resp = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = client.messages.create(
                    model=model_id,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_msg}],
                )
                break
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt * 5  # 5s, 10s, 20s
                    log.warning("Scoring batch %d attempt %d failed, retrying in %ds: %s",
                                batch_start, attempt + 1, wait, e)
                    time.sleep(wait)
                else:
                    log.error("Scoring batch %d failed after %d attempts: %s",
                              batch_start, MAX_RETRIES, e)

        if resp is None:
            continue

        # Extract text content
        text_parts: list[str] = []
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)
        text = "\n".join(text_parts)

        objs = _extract_json_objects(text)
        log.info("Scoring batch %d-%d: %d items in, %d scored objects out",
                 batch_start, batch_start + len(batch), len(batch), len(objs))

        for obj in objs:
            item_id = obj.get("item_id")
            raw = by_id.get(item_id)
            if raw is None:
                continue
            scores = obj.get("scores", {})
            total = obj.get("total")
            if total is None:
                # Fallback: sum the components
                total = sum(int(v) for v in scores.values() if isinstance(v, (int, float)))
            reason = obj.get("one_line_reason", "")
            scored = ScoredItem(raw=raw, scores=scores, total=int(total), reason=reason)
            if scored.total >= threshold:
                surviving.append(scored)

    surviving.sort(key=lambda s: s.total, reverse=True)
    log.info("Scoring: %d items in, %d above threshold %d", len(items), len(surviving), threshold)
    return surviving
