from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from src.enhanced_renderer import render_enhanced_email
from src.human_signal import load_jokes, select_joke
from src.judgement_plan import JudgementPlanError, validate_judgement_plan
from src.signal_memory import apply_memory_update
from src.visual_signal import render_visual_signal


ROOT = Path(__file__).resolve().parents[1]


def valid_plan() -> dict:
    return {
        "one_thing": {
            "statement": "AI advantage is moving from model choice to operating discipline.",
            "business_implication": "Leaders should fund governance, knowledge quality and workflow design before adding more models.",
            "confidence": "HIGH",
            "evidence_ids": ["S01", "S03", "S06"],
        },
        "evidence_items": [
            {
                "source_ids": [f"S0{i}"],
                "category": category,
                "action_tag": "OPPORTUNITY" if i == 4 else ("WATCH" if i > 1 else "ACT"),
                "headline": headline,
                "evidence": "A source-backed fact remains separate from judgement.",
            }
            for i, (category, headline) in enumerate(
                [
                    ("Operations & Workflow", "Constrained agents outperform autonomous ones"),
                    ("Finance & Commercial Performance", "Infrastructure costs are moving up"),
                    ("Strategy & Leadership", "Cheaper models are winning buyers"),
                    ("Sales & Marketing", "AI products still need sales teams"),
                    ("People & Capability", "AI pressure is reaching wages"),
                    ("Data & Systems", "Messy knowledge breaks reliable agents"),
                    ("Governance & Risk", "Opaque automation creates regulatory risk"),
                ],
                1,
            )
        ],
        "interpretation": "The collective evidence indicates that AI value is being limited by operating discipline more than access to models.",
        "founders_note": {
            "headline": "AI is infrastructure now. Price it that way.",
            "body": (
                "The stack is getting boring. That's a good sign. When serious buyers start focusing on "
                "billing flexibility, cost controls and operating discipline rather than magic, the technology "
                "is settling into its real role. Infrastructure. Commodity. Table stakes. The edge is no longer "
                "access because everyone has access. The edge is judgement about where to deploy it, which "
                "constraint it removes, and what that frees up. Most businesses are still asking whether they "
                "should use AI. The smarter question is where it produces a measurable business advantage. "
                "The technology is not the strategy. It never was. That is the whole game now. — Paul"
            ),
        },
        "what_changed": {
            "position_id": "ai-advantage-operating-system",
            "classification": "STRENGTHENS",
            "prior_position": "The operating system around AI matters more than model choice.",
            "current_position": "New evidence strengthens the operating-discipline thesis.",
            "explanation": "Constrained agents, cheaper models and data-quality failures point in the same direction.",
            "confidence": "HIGH",
        },
        "visual_signal": {
            "eligible": True,
            "type": "TENSION_MAP",
            "title": "Where AI advantage is moving",
            "subtitle": "Capability is abundant; operating discipline is scarce.",
            "rows": [
                {"label": "Model access", "status": "SUPPORTED", "detail": "Cheaper capable models are widening access."},
                {"label": "Knowledge quality", "status": "CONSTRAINED", "detail": "Messy documents limit reliability."},
                {"label": "Governance", "status": "EXPOSED", "detail": "Opaque automated decisions create risk."},
            ],
        },
        "counter_signal": {
            "statement": "Premium model capability may still dominate in high-value specialist work.",
            "would_change_view_if": "Enterprises demonstrate materially higher ROI from premium autonomous models than constrained workflows.",
            "confidence_effect": "That evidence would weaken the operating-discipline thesis.",
        },
        "executive_actions": ["Audit one AI workflow for data, permission and human-review constraints."],
        "executive_read": {
            "dtl_view": "The next AI advantage is operational, not theatrical.",
            "watch_items": ["Whether premium models produce measurable ROI advantages."],
        },
        "memory_update": {
            "position_id": "ai-advantage-operating-system",
            "theme": "AI commercial advantage",
            "statement": "Operating discipline is becoming the binding constraint on AI value.",
            "confidence": "HIGH",
            "supporting_source_ids": ["S01", "S03", "S06"],
        },
    }


class JudgementArchitectureTests(unittest.TestCase):
    def test_valid_plan_passes_contract(self) -> None:
        plan = valid_plan()
        self.assertIs(validate_judgement_plan(plan, {f"S0{i}" for i in range(1, 8)}), plan)

    def test_unknown_source_is_rejected(self) -> None:
        plan = valid_plan()
        plan["evidence_items"][0]["source_ids"] = ["S99"]
        with self.assertRaises(JudgementPlanError):
            validate_judgement_plan(plan, {f"S0{i}" for i in range(1, 8)})

    def test_invalid_change_classification_is_rejected(self) -> None:
        plan = valid_plan()
        plan["what_changed"]["classification"] = "NEW"
        with self.assertRaises(JudgementPlanError):
            validate_judgement_plan(plan, {f"S0{i}" for i in range(1, 8)})

    def test_founders_note_requires_established_format_and_inline_signoff(self) -> None:
        plan = valid_plan()
        plan["founders_note"]["body"] = "Compressed CEO view without the established founder format."
        with self.assertRaises(JudgementPlanError):
            validate_judgement_plan(plan, {f"S0{i}" for i in range(1, 8)})

    def test_visual_signal_is_optional_and_governed(self) -> None:
        self.assertEqual(render_visual_signal({"eligible": False, "type": "NONE", "rows": []}), "")
        rendered = render_visual_signal(valid_plan()["visual_signal"])
        self.assertIn("VISUAL SIGNAL", rendered)
        self.assertIn("Knowledge quality", rendered)

    def test_joke_library_has_100_and_rotation_blocks_recent(self) -> None:
        jokes = load_jokes(ROOT / "data" / "dad_jokes.json")
        self.assertEqual(len(jokes), 100)
        first = select_joke(jokes, 38, [])
        second = select_joke(jokes, 38, [first["id"]])
        self.assertNotEqual(first["id"], second["id"])

    def test_memory_update_records_position_movement(self) -> None:
        plan = valid_plan()
        memory = {"version": 1, "positions": [], "events": []}
        updated = apply_memory_update(
            memory,
            plan["memory_update"],
            plan["what_changed"],
            edition_number=38,
            delivered_at="2026-08-24T06:06:00+10:00",
        )
        self.assertEqual(updated["positions"][0]["confidence"], "HIGH")
        self.assertEqual(updated["events"][0]["classification"], "STRENGTHENS")

    def test_renderer_follows_intelligence_sequence_and_boundaries(self) -> None:
        sources = json.loads((ROOT / "data" / "fixtures" / "edition0038_evidence.json").read_text())
        joke = load_jokes(ROOT / "data" / "dad_jokes.json")[0]
        html = render_enhanced_email(
            valid_plan(),
            sources,
            joke,
            edition_number=38,
            generated_at=datetime(2026, 8, 24, 6, 6, tzinfo=ZoneInfo("Australia/Brisbane")),
            alive_moment=json.loads((ROOT / "data" / "fixtures" / "alive_moment_0038.json").read_text()),
        )
        signature = ["THINK.", "DECIDE.", "LOOK UP.", "SMILE."]
        signature_positions = [html.index(label) for label in signature]
        self.assertEqual(signature_positions, sorted(signature_positions))
        self.assertLess(signature_positions[-1], html.index("THE ONE THING"))
        sequence = [
            "THE ONE THING",
            "FOUNDER'S NOTE",
            "AI is infrastructure now. Price it that way.",
            "— Paul",
            "THE EVIDENCE",
            "YOUR SIGNAL AT A GLANCE",
            "VISUAL SIGNAL",
            "INTERPRETATION",
            "WHAT CHANGED?",
            "EXECUTIVE ACTION / WATCH",
            "COUNTER-SIGNAL",
            "REMEMBER THE WORLD",
            "DAD JOKE OF THE DAY",
        ]
        positions = [html.index(label) for label in sequence]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("THE EVIDENCE", html)
        self.assertEqual(html.count("YOUR SIGNAL AT A GLANCE"), 1)
        self.assertEqual(html.count("THINK."), 1)
        self.assertEqual(html.count("DECIDE."), 1)
        self.assertEqual(html.count("LOOK UP."), 1)
        self.assertEqual(html.count("SMILE."), 1)
        self.assertIn('<span style="color:#C43F2C;">THINK.</span>', html)
        self.assertIn('<span style="color:#966300;">DECIDE.</span>', html)
        self.assertIn('<span style="color:#2B7F8C;">LOOK UP.</span>', html)
        self.assertIn('<span style="color:#0B7F78;">SMILE.</span>', html)
        self.assertIn("ACT NOW", html)
        self.assertIn("WATCH CLOSELY", html)
        self.assertIn("OPPORTUNITY", html)
        self.assertIn("Decision or action", html)
        self.assertIn("Developing change", html)
        self.assertIn("Opening to explore", html)
        self.assertIn("background:#E8533A", html)
        self.assertIn("background:#E6A817", html)
        self.assertIn("background:#17A398", html)
        self.assertIn("INTERPRETATION", html)
        self.assertIn("FOUNDER'S NOTE", html)
        self.assertEqual(html.count("FOUNDER'S NOTE"), 1)
        self.assertIn(valid_plan()["founders_note"]["headline"], html)
        self.assertIn(escape(valid_plan()["founders_note"]["body"]), html)
        self.assertEqual(html.count("— Paul"), 1)
        self.assertNotIn("CEO VIEW", html)
        self.assertNotIn("Do something different today … Paul", html)
        self.assertNotIn("WE ARE ALIVE", html)
        self.assertNotIn("Signal learns. Every open, every click, every skip trains the next edition.", html)
        self.assertIn('<table width="100%" cellpadding="0" cellspacing="0" style="width:100%;margin:0;">', html)
        self.assertIn('width="820"', html)
        self.assertIn('max-width:820px', html)
        self.assertIn('color:#6B7280;text-align:left;', html)
        self.assertIn("PF::SIGNAL-0038 // 24.08.2026 // 06:06 AEST", html)
        self.assertIn('color:#17A398;letter-spacing:1px;">Edition 0038', html)
        self.assertIn('font-size:12px;color:#17A398;letter-spacing:1.5px', html)
        self.assertIn('border-top:2px solid #4ECDC4;padding-top:14px;', html)
        self.assertIn('padding:14px 40px 8px 40px;', html)
        self.assertNotIn('color:#aaa;letter-spacing:2px;text-transform:uppercase;">THINK</p>', html)
        self.assertNotIn('color:#aaa;letter-spacing:2px;text-transform:uppercase;">DECIDE</p>', html)
        self.assertNotIn('color:#aaa;letter-spacing:2px;text-transform:uppercase;">LOOK UP</p>', html)
        self.assertNotIn('color:#aaa;letter-spacing:2px;text-transform:uppercase;">SMILE</p>', html)
        self.assertIn('color:#17A398;text-decoration:underline;">→ dtlc.ai</a>', html)
        self.assertNotIn("opacity:", html)
        self.assertIn("Financial Times (via Simon Willison)", html)
        self.assertNotIn("Simon Willison / Financial Times", html)
        self.assertIn("Photo: Charles J. Sharp · Wikimedia Commons", html)
        self.assertIn('text-decoration:underline;">CC BY-SA 4.0</a>', html)
        self.assertNotIn(">source</a>", html)
        self.assertNotIn(">licence</a>", html)
        self.assertEqual(html.count("DAD JOKE OF THE DAY"), 1)
        self.assertLess(html.index("DAD JOKE OF THE DAY"), html.index("PF::SIGNAL-0038"))


if __name__ == "__main__":
    unittest.main()
