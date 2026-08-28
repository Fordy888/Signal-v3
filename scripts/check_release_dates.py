#!/usr/bin/env python3
"""Print deterministic edition numbers for the confirmed release dates."""

from datetime import date
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.edition_counter import edition_for_date


def main() -> None:
    dates = (
        ("Saturday", date(2026, 8, 29)),
        ("Monday", date(2026, 8, 31)),
    )
    for label, target in dates:
        print(f"{label} {target.isoformat()}: Edition {edition_for_date(target):04d}")


if __name__ == "__main__":
    main()
