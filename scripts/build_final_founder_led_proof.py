from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.alive_moment import load_alive_moment, validate_alive_moment
from src.email_html_qa import validate_email_html
from src.enhanced_renderer import render_enhanced_email
from src.human_signal import load_jokes, select_joke
from src.judgement_plan import validate_judgement_plan


def main() -> None:
    plan = json.loads((ROOT / "data" / "final-founder-led-proof-plan.json").read_text())
    evidence = json.loads((ROOT / "data" / "final-founder-led-proof-evidence.json").read_text())
    validate_judgement_plan(plan, {str(item["source_id"]) for item in evidence})

    joke = select_joke(load_jokes(ROOT / "data" / "dad_jokes.json"), 46, recent_ids=[])
    alive_moment = load_alive_moment(ROOT / "data" / "fixtures" / "alive_moment_0046.json")
    prior_image_history = [
        {
            "id": "REMEMBER-0045-MOOREA-HUMPBACK",
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
        expected_edition_id="0046",
        expected_date="2026-09-03",
    )

    html = render_enhanced_email(
        plan=plan,
        sources=evidence,
        joke=joke,
        edition_number=46,
        generated_at=datetime(2026, 9, 3, 6, 0, tzinfo=ZoneInfo("Australia/Brisbane")),
        alive_moment=alive_moment,
    )
    required = (
        "FOUNDER'S NOTE",
        "DTL SIGNAL NEWSROOM — READ THIS",
        "YOUR SIGNAL AT A GLANCE",
        "FOCUS ON THE NUMBERS",
        "WHY IT MATTERS",
        "WHAT TO DO NOW",
        "THE OTHER SIDE",
        "WATCH FOR THIS",
        "REMEMBER THE WORLD",
        "DAD JOKE OF THE DAY",
    )
    removed = ("THE EVIDENCE", "THE ONE THING", "THE SHIFT", "WHAT CHANGED")
    missing = [label for label in required if label not in html]
    leaked = [label for label in removed if label in html]
    if missing or leaked:
        raise SystemExit(f"Reader contract failed; missing={missing}; leaked={leaked}")
    if html.count("Source:") != 5:
        raise SystemExit("FOCUS ON THE NUMBERS must render exactly five source lines")
    for source in evidence:
        if html.count(str(source["url"])) != 1:
            raise SystemExit(
                f"Source link must appear exactly once: {source['source_id']}"
            )

    passed, issues = validate_email_html(html)
    if not passed:
        raise SystemExit("Email HTML QA failed: " + "; ".join(issues))

    output = ROOT / "data" / "final-founder-led-proof.html"
    output.write_text(html)
    digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
    manifest = {
        "release_id": "focus-numbers-60-40-v1",
        "edition": "0046",
        "issue_date": "2026-09-03",
        "renderer_id": "enhanced-v4-focus-numbers",
        "html_sha256": digest,
        "proof_recipient": "paul.ford@gmail.com",
        "subscriber_send": False,
        "image_id": alive_moment["id"],
        "image_colour_family": alive_moment["dominant_colour_family"],
    }
    (ROOT / "data" / "final-founder-led-proof-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(f"Wrote {output}")
    print(f"SHA-256 {digest}")


if __name__ == "__main__":
    main()
