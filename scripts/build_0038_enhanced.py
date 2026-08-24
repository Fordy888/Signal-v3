"""Build Edition 0038 Enhanced from the same seven evidence items as the control.

This is an acceptance-test tool. It does not fetch, send, update the edition
counter, write production Signal Memory or modify the live synthesis prompt.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.enhanced_renderer import render_enhanced_email
from src.human_signal import load_joke_history, load_jokes, select_joke
from src.judgement_plan import generate_judgement_plan, validate_judgement_plan
from src.signal_memory import load_signal_memory, memory_context


BRISBANE = ZoneInfo("Australia/Brisbane")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build sandboxed Edition 0038 Enhanced")
    parser.add_argument("--evidence", default=str(ROOT / "data" / "fixtures" / "edition0038_evidence.json"))
    parser.add_argument("--memory", default=str(ROOT / "data" / "fixtures" / "signal_memory_0038.json"))
    parser.add_argument("--plan-input", default=None, help="Render an existing validated plan instead of calling the planner")
    parser.add_argument("--plan-output", default=str(ROOT / "data" / "edition0038-enhanced-plan.json"))
    parser.add_argument("--html-output", default=str(ROOT / "data" / "edition0038-enhanced.html"))
    args = parser.parse_args()

    evidence_path = Path(args.evidence)
    memory_path = Path(args.memory)
    evidence = json.loads(evidence_path.read_text())
    available_ids = {str(item["source_id"]) for item in evidence}

    if args.plan_input:
        plan = validate_judgement_plan(json.loads(Path(args.plan_input).read_text()), available_ids)
    else:
        memory = memory_context(load_signal_memory(memory_path))
        plan = generate_judgement_plan(
            evidence_items=evidence,
            prior_memory=memory,
            prompt_path=ROOT / "prompts" / "judgement_planner_prompt.md",
        )

    plan_output = Path(args.plan_output)
    plan_output.parent.mkdir(parents=True, exist_ok=True)
    plan_output.write_text(json.dumps(plan, indent=2) + "\n")

    jokes = load_jokes(ROOT / "data" / "dad_jokes.json")
    recent_ids = load_joke_history(ROOT / "data" / "joke_history.json")
    joke = select_joke(jokes, edition_number=38, recent_ids=recent_ids)
    generated_at = datetime(2026, 8, 24, 6, 6, tzinfo=BRISBANE)
    html = render_enhanced_email(plan, evidence, joke, edition_number=38, generated_at=generated_at)

    html_output = Path(args.html_output)
    html_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.write_text(html)

    print(f"Validated plan: {plan_output}")
    print(f"Enhanced HTML: {html_output}")
    print(f"THE ONE THING: {plan['one_thing']['statement']}")
    print(f"WHAT CHANGED: {plan['what_changed']['classification']}")
    print(f"Visual Signal: {plan['visual_signal']['eligible']} / {plan['visual_signal']['type']}")
    print(f"Human Signal: {joke['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
