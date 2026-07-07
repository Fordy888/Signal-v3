"""Edition counter for Signal pipeline.
Tracks the current edition number in data/edition_counter.json.
Increments only on successful send (not proof).
"""
from __future__ import annotations
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

COUNTER_FILE = "data/edition_counter.json"
DEFAULT_START = 12  # ~12 editions sent before this counter was introduced


def get_next_edition(root: Path) -> int:
    """Get the next edition number (current + 1) without incrementing."""
    counter_path = root / COUNTER_FILE
    counter_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not counter_path.exists():
        log.info("No edition counter found — starting at %d", DEFAULT_START + 1)
        return DEFAULT_START + 1
    
    try:
        with open(counter_path, "r") as f:
            data = json.load(f)
        return data.get("current", DEFAULT_START) + 1
    except (json.JSONDecodeError, IOError) as e:
        log.warning("Failed to read edition counter: %s — using default", e)
        return DEFAULT_START + 1


def increment_edition(root: Path) -> int:
    """Increment the edition counter after successful send. Returns the new current value."""
    counter_path = root / COUNTER_FILE
    counter_path.parent.mkdir(parents=True, exist_ok=True)
    
    current = DEFAULT_START
    if counter_path.exists():
        try:
            with open(counter_path, "r") as f:
                data = json.load(f)
            current = data.get("current", DEFAULT_START)
        except (json.JSONDecodeError, IOError):
            pass
    
    new_current = current + 1
    try:
        with open(counter_path, "w") as f:
            json.dump({"current": new_current, "last_incremented_by": "send"}, f, indent=2)
        log.info("Edition counter incremented: %d -> %d", current, new_current)
    except IOError as e:
        log.error("Failed to write edition counter: %s", e)
    
    return new_current
