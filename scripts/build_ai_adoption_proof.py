from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.enhanced_renderer import render_enhanced_email
from src.alive_moment import load_alive_moment, validate_alive_moment
from src.judgement_plan import (
    _has_ai_adoption_evidence,
    prepare_ai_adoption_evidence,
    prepare_focus_number_evidence,
    validate_judgement_plan,
)

PROOF_CONFIG = {
    "0047": {
        "date": "2026-09-04",
        "joke": {
            "setup": "Why did the workflow bring a ruler to the meeting?",
            "punchline": "It wanted to measure the impact before scaling.",
        },
    },
    "0048": {
        "date": "2026-09-07",
        "joke": {
            "setup": "Why did the robot take a welding class?",
            "punchline": "It wanted to make stronger connections.",
        },
    },
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", choices=sorted(PROOF_CONFIG), default="0047")
    args = parser.parse_args()
    edition_id = args.edition
    edition_number = int(edition_id)
    config = PROOF_CONFIG[edition_id]
    proof_date = datetime.strptime(config["date"], "%Y-%m-%d").replace(
        hour=6, tzinfo=ZoneInfo("Australia/Brisbane")
    )
    plan_path = ROOT / "data" / f"ai-adoption-proof-plan-{edition_id}.json"
    evidence_path = ROOT / "data" / f"ai-adoption-proof-evidence-{edition_id}.json"
    output_path = ROOT / "data" / f"ai-adoption-proof-{edition_id}.html"
    alive_path = ROOT / "data" / "fixtures" / f"alive_moment_{edition_id}.json"
    plan = json.loads(plan_path.read_text())
    evidence = json.loads(evidence_path.read_text())
    prepared, focus_eligible = prepare_focus_number_evidence(evidence)
    prepared, verified_mix = prepare_ai_adoption_evidence(prepared)
    allocated = {
        "newsroom": [str(item["source_ids"][0]) for item in plan["evidence_items"]],
        "focus_numbers": [str(item["source_ids"][0]) for item in plan["focus_numbers"]],
    }
    for section, items, fields in (
        ("newsroom", plan["evidence_items"], ("headline", "evidence")),
        ("focus", plan["focus_numbers"], ("entity", "number", "meaning")),
    ):
        for item in items:
            if item.get("mix_classification") != "AI_ADOPTION":
                continue
            text = " ".join(str(item.get(field, "")) for field in fields)
            print(
                f"semantic={section}:{item['source_ids'][0]}:"
                f"{_has_ai_adoption_evidence(text)}"
            )
    validated = validate_judgement_plan(
        plan,
        {str(item["source_id"]) for item in prepared},
        focus_eligible,
        verified_mix,
        allocated,
    )
    alive_moment = validate_alive_moment(
        load_alive_moment(alive_path),
        history=[],
        expected_edition_id=edition_id,
        expected_date=config["date"],
    )
    html = render_enhanced_email(
        plan=validated,
        sources=prepared,
        joke=config["joke"],
        edition_number=edition_number,
        generated_at=proof_date,
        alive_moment=alive_moment,
    )
    output_path.write_text(html)
    selected_ids = allocated["newsroom"] + allocated["focus_numbers"]
    selected_classes = [verified_mix[source_id] for source_id in selected_ids]
    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    print(f"proof={output_path}")
    print(f"sha256={digest}")
    print(f"newsroom={','.join(allocated['newsroom'])}")
    print(f"focus={','.join(allocated['focus_numbers'])}")
    print(f"adoption={selected_classes.count('AI_ADOPTION')}")
    print(f"industry_impact={selected_classes.count('AI_INDUSTRY_IMPACT')}")
    print(f"focus_eligible={len(focus_eligible)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
