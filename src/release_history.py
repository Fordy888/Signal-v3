from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ReleaseHistoryError(ValueError):
    pass


def load_cutover_history(root: Path) -> dict[str, Any]:
    path = root / "data" / "release_history_seed.json"
    if not path.exists():
        return {"source_urls": set(), "joke_ids": [], "alive_moments": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    source_urls = payload.get("production_source_urls", [])
    joke_ids = payload.get("joke_ids", [])
    moment_paths = payload.get("alive_moment_paths", [])
    if not all(isinstance(value, str) and value.startswith("https://") for value in source_urls):
        raise ReleaseHistoryError("cutover source history contains an invalid URL")
    if not all(isinstance(value, str) and value for value in joke_ids):
        raise ReleaseHistoryError("cutover joke history contains an invalid ID")
    alive_moments = []
    for relative_path in moment_paths:
        moment_path = root / str(relative_path)
        if not moment_path.is_file():
            raise ReleaseHistoryError(f"cutover image record is missing: {relative_path}")
        alive_moments.append(json.loads(moment_path.read_text(encoding="utf-8")))
    return {
        "source_urls": set(source_urls),
        "joke_ids": list(joke_ids),
        "alive_moments": alive_moments,
    }


def merge_release_histories(*histories: dict[str, Any]) -> dict[str, Any]:
    source_urls: set[str] = set()
    joke_ids: list[str] = []
    seen_jokes: set[str] = set()
    alive_moments: list[dict[str, Any]] = []
    alive_index: dict[str, int] = {}
    for history in histories:
        source_urls.update(str(url) for url in history.get("source_urls", set()) if url)
        for joke_id in history.get("joke_ids", []):
            value = str(joke_id).strip()
            if value and value not in seen_jokes:
                seen_jokes.add(value)
                joke_ids.append(value)
        for moment in history.get("alive_moments", []):
            if not isinstance(moment, dict):
                continue
            identity = str(
                moment.get("id")
                or moment.get("image_original_url")
                or moment.get("image_source_url")
                or moment.get("image_url")
                or moment.get("image_sha256")
                or ""
            ).strip()
            if not identity:
                continue
            if identity in alive_index:
                alive_moments[alive_index[identity]] = dict(moment)
            else:
                alive_index[identity] = len(alive_moments)
                alive_moments.append(dict(moment))
    return {
        "source_urls": source_urls,
        "joke_ids": joke_ids,
        "alive_moments": alive_moments,
    }
