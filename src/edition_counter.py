"""Deterministic Brisbane weekday edition numbering.

Edition 0017 is anchored to Friday 24 July 2026. Weekdays advance the edition;
Saturday and Sunday retain Friday's number. No ephemeral filesystem state is
required, so proofs, dry-runs and Render rebuilds cannot consume a number.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


log = logging.getLogger(__name__)

BRISBANE = ZoneInfo("Australia/Brisbane")
ANCHOR_DATE = date(2026, 7, 24)
ANCHOR_EDITION = 17


def _weekdays_between(start: date, end: date) -> int:
    if end < start:
        return -_weekdays_between(end, start)
    count = 0
    current = start
    while current < end:
        current += timedelta(days=1)
        if current.weekday() < 5:
            count += 1
    return count


def edition_for_date(target: date) -> int:
    effective = target
    while effective.weekday() >= 5:
        effective -= timedelta(days=1)
    return ANCHOR_EDITION + _weekdays_between(ANCHOR_DATE, effective)


def get_next_edition(root: Path | None = None) -> int:
    today = datetime.now(BRISBANE).date()
    edition = edition_for_date(today)
    log.info(
        "Edition number derived from calendar: %04d (Brisbane %s)",
        edition,
        today.isoformat(),
    )
    return edition


def increment_edition(root: Path | None = None) -> int:
    edition = get_next_edition(root)
    log.info("Edition counter is date-derived — nothing to increment (today = %04d)", edition)
    return edition
