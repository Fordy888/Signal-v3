"""Build the dynamic-headline v4 proof without sending or mutating runtime state."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.email_html_qa import validate_email_html
from src.alive_moment import load_alive_moment, validate_alive_moment
from src.enhanced_renderer import render_enhanced_email
from src.human_signal import load_jokes, select_joke
from src.judgement_plan import validate_judgement_plan


def main() -> None:
    plan = json.loads((ROOT / "data" / "v4-dynamic-headline-proof-plan.json").read_text())
    evidence = json.loads((ROOT / "data" / "fixtures" / "edition0042_evidence.json").read_text())
    validate_judgement_plan(plan, {str(item["source_id"]) for item in evidence})
    joke = select_joke(load_jokes(ROOT / "data" / "dad_jokes.json"), 44, recent_ids=[])
    alive_moment = load_alive_moment(ROOT / "data" / "fixtures" / "alive_moment_0044.json")
    prior_image_history = [
        {
            "id": "REMEMBER-0043-MOOREA-HUMPBACK",
            "location": "Moorea",
            "country": "French Polynesia",
            "category": "marine_life",
            "species": "Megaptera novaeangliae",
            "image_source_url": "https://commons.wikimedia.org/wiki/File:Humpback_whale_(Megaptera_novaeangliae)_with_calf_Moorea_2.jpg",
        }
    ]
    validate_alive_moment(
        alive_moment,
        prior_image_history,
        expected_edition_id="0044",
        expected_date="2026-09-01",
    )
    html = render_enhanced_email(
        plan=plan,
        sources=evidence,
        joke=joke,
        edition_number=44,
        generated_at=datetime(2026, 9, 1, 6, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
        alive_moment=alive_moment,
    )
    passed, issues = validate_email_html(html)
    if not passed:
        raise SystemExit("Email HTML QA failed: " + "; ".join(issues))
    output = ROOT / "data" / "v4-dynamic-headline-proof.html"
    output.write_text(html)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
