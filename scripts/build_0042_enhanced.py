"""Build the no-send Edition 0042 Enhanced draft from validated local inputs."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.alive_moment import load_alive_history, load_alive_moment, validate_alive_moment
from src.enhanced_renderer import render_enhanced_email
from src.human_signal import load_joke_history, load_jokes, select_joke
from src.judgement_plan import validate_judgement_plan


def main() -> int:
    evidence_path = ROOT / "data" / "fixtures" / "edition0042_evidence.json"
    plan_path = ROOT / "data" / "edition0042-enhanced-plan.json"
    moment_path = ROOT / "data" / "fixtures" / "alive_moment_0042.json"
    output_path = ROOT / "data" / "edition0042-enhanced-draft.html"

    evidence = json.loads(evidence_path.read_text())
    plan = validate_judgement_plan(
        json.loads(plan_path.read_text()),
        {str(item["source_id"]) for item in evidence},
    )
    moment = validate_alive_moment(
        load_alive_moment(moment_path),
        load_alive_history(ROOT / "data" / "alive_moment_history.json"),
    )
    joke = select_joke(
        load_jokes(ROOT / "data" / "dad_jokes.json"),
        edition_number=42,
        recent_ids=load_joke_history(ROOT / "data" / "joke_history.json"),
    )
    generated_at = datetime.fromisoformat("2026-08-28T06:00:00+10:00")
    html = render_enhanced_email(
        plan,
        evidence,
        joke,
        edition_number=42,
        generated_at=generated_at,
        alive_moment=moment,
    )
    output_path.write_text(html)
    print(f"Validated plan: {plan_path}")
    print(f"Enhanced HTML: {output_path}")
    print(f"THE ONE THING: {plan['one_thing']['statement']}")
    print(f"FOUNDER'S NOTE: {plan['founders_note']['headline']}")
    print(f"REMEMBER THE WORLD: {moment['id']}")
    print(f"DAILY DAD JOKE: {joke['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
