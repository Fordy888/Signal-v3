"""72-hour URL deduplication layer for Signal pipeline.

Stores delivered item URLs with timestamps. On each run, filters out
URLs that were delivered within the last 72 hours to prevent duplicate
articles across consecutive editions.

Storage: data/history.json (must persist between Render cron runs — 
requires Render Disk or equivalent persistent storage).
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

log = logging.getLogger(__name__)

HISTORY_FILE = "data/history.json"
DEDUP_WINDOW_HOURS = 72


def load_history(root: Path) -> set[str]:
    """Load URLs delivered within the last 72 hours.
    
    Returns a set of URL strings that should be excluded from the current run.
    """
    history_path = root / HISTORY_FILE
    if not history_path.exists():
        log.info("No history file found at %s — starting fresh", history_path)
        return set()

    try:
        with open(history_path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        log.warning("Failed to read history file: %s — starting fresh", e)
        return set()

    cutoff = time.time() - (DEDUP_WINDOW_HOURS * 3600)
    recent_urls = set()

    for entry in data.get("editions", []):
        entry_time = entry.get("timestamp", 0)
        if entry_time >= cutoff:
            recent_urls.update(entry.get("urls", []))

    log.info("Loaded %d URLs from history (within %dh window)", len(recent_urls), DEDUP_WINDOW_HOURS)
    return recent_urls


def record_edition(root: Path, urls: list[str], edition_id: str = "") -> None:
    """Record delivered URLs for the current edition.
    
    Appends to the history file and prunes entries older than 72 hours.
    """
    history_path = root / HISTORY_FILE
    history_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing history
    data = {"editions": []}
    if history_path.exists():
        try:
            with open(history_path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            data = {"editions": []}

    # Append current edition
    data["editions"].append({
        "id": edition_id,
        "timestamp": time.time(),
        "urls": urls,
    })

    # Prune old entries (older than 72 hours)
    cutoff = time.time() - (DEDUP_WINDOW_HOURS * 3600)
    data["editions"] = [e for e in data["editions"] if e.get("timestamp", 0) >= cutoff]

    # Write back
    try:
        with open(history_path, "w") as f:
            json.dump(data, f, indent=2)
        log.info("Recorded %d URLs for edition '%s' (total editions in history: %d)",
                 len(urls), edition_id, len(data["editions"]))
    except IOError as e:
        log.error("Failed to write history file: %s", e)
