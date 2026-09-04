from __future__ import annotations

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

PLAN_PATH = ROOT / "data" / "ai-adoption-proof-plan-0047.json"
EVIDENCE_PATH = ROOT / "data" / "ai-adoption-proof-evidence-0047.json"
OUTPUT_PATH = ROOT / "data" / "ai-adoption-proof-0047.html"
ALIVE_PATH = ROOT / "data" / "fixtures" / "alive_moment_0047.json"


def main() -> int:
    plan = json.loads(PLAN_PATH.read_text())
    evidence = json.loads(EVIDENCE_PATH.read_text())
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
        load_alive_moment(ALIVE_PATH),
        history=[],
        expected_edition_id="0047",
        expected_date="2026-09-04",
    )
    html = render_enhanced_email(
        plan=validated,
        sources=prepared,
        joke={
            "setup": "Why did the workflow bring a ruler to the meeting?",
            "punchline": "It wanted to measure the impact before scaling.",
        },
        edition_number=47,
        generated_at=datetime(
            2026, 9, 4, 6, 0, tzinfo=ZoneInfo("Australia/Brisbane")
        ),
        alive_moment=alive_moment,
    )
    OUTPUT_PATH.write_text(html)
    selected_ids = allocated["newsroom"] + allocated["focus_numbers"]
    selected_classes = [verified_mix[source_id] for source_id in selected_ids]
    digest = hashlib.sha256(OUTPUT_PATH.read_bytes()).hexdigest()
    print(f"proof={OUTPUT_PATH}")
    print(f"sha256={digest}")
    print(f"newsroom={','.join(allocated['newsroom'])}")
    print(f"focus={','.join(allocated['focus_numbers'])}")
    print(f"adoption={selected_classes.count('AI_ADOPTION')}")
    print(f"industry_impact={selected_classes.count('AI_INDUSTRY_IMPACT')}")
    print(f"focus_eligible={len(focus_eligible)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
