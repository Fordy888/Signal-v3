"""The 0048 renderer must survive every optional section being omitted.

These guard the seam between section_policy (which removes sections) and
enhanced_renderer (which must then skip them rather than raise KeyError).
"""
from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from src.enhanced_renderer import render_enhanced_email
from src.section_policy import apply_section_policy

BRISBANE = ZoneInfo("Australia/Brisbane")
GENERATED_AT = datetime(2026, 9, 10, 6, 0, tzinfo=BRISBANE)

SOURCES = [
    {"source_id": f"S0{i}", "source": f"Source {i}", "url": f"https://example.com/{i}"}
    for i in range(1, 6)
]


def _plan():
    return {
        "editorial_revision": "ai-adoption-v1",
        "interpretation_headline": "Adoption is outpacing governance",
        "interpretation": "Buyers are deploying faster than controls mature.",
        "evidence_items": [
            {
                "source_ids": [f"S0{i}"],
                "category": "STRATEGY",
                "action_tag": "WATCH",
                "headline": f"Headline {i}",
                "evidence": "What the source supports.",
                "ai_business_connection": "The practical consequence.",
            }
            for i in range(1, 4)
        ],
        "founders_note": {"headline": "The gap is the risk", "body": "Body text — Paul"},
        "executive_read": {
            "dtl_view": "A considered view.",
            "watch_headline": "Procurement cycles shorten",
            "watch_items": ["First observable", "Second observable"],
        },
        "executive_actions": [
            {
                "action_tag": "ACT",
                "headline": "Review vendor controls",
                "instruction": "Ask procurement for the current control evidence.",
            },
            {
                "action_tag": "WATCH",
                "headline": "Track adoption rate",
                "instruction": "Watch weekly deployment counts against policy sign-off.",
            },
        ],
        "focus_numbers": [
            {
                "source_ids": [f"S0{i}"],
                "entity": f"Entity {i}",
                "number": f"{i}0%",
                "meaning": "Why it matters commercially.",
            }
            for i in range(1, 6)
        ],
        "counter_signal": {
            "headline": "The constraint",
            "statement": "A credible challenge.",
            "would_change_view_if": "Observable disconfirming evidence.",
        },
    }


JOKE = {"id": "J001", "setup": "Why?", "punchline": "Because."}


def _render(plan, joke=JOKE, alive=None):
    return render_enhanced_email(
        plan=plan,
        sources=SOURCES,
        joke=joke,
        edition_number=51,
        generated_at=GENERATED_AT,
        alive_moment=alive,
    )


class FullEditionStillRenders(unittest.TestCase):
    def test_complete_plan_renders_every_section(self):
        html = _render(_plan())
        for marker in (
            "FOCUS ON THE NUMBERS",
            "WHY IT MATTERS",
            "THE OTHER SIDE",
            "WHAT WOULD CHANGE OUR VIEW",
            "WATCH FOR THIS",
            "FOUNDER'S NOTE",
        ):
            self.assertIn(marker, html, f"{marker} missing from a complete edition")

    def test_metadata_the_qa_gate_checks_is_present(self):
        html = _render(_plan())
        self.assertIn("Edition 0051", html)
        self.assertIn("10 September", html)
        self.assertIn("PF::SIGNAL-0051 // 10.09.2026", html)


class OmittedSectionsRenderCleanly(unittest.TestCase):
    def _apply(self, plan, alive=None, joke=JOKE):
        plan, alive, joke, _ = apply_section_policy(plan, alive_moment=alive, joke=joke)
        return _render(plan, joke=joke, alive=alive)

    def test_focus_numbers_omitted(self):
        plan = _plan()
        plan["focus_numbers"] = plan["focus_numbers"][:3]
        html = self._apply(plan)
        self.assertNotIn("FOCUS ON THE NUMBERS", html)
        # The mandatory thesis still renders.
        self.assertIn("WHY IT MATTERS", html)
        self.assertIn("Adoption is outpacing governance", html)

    def test_counter_signal_omitted(self):
        plan = _plan()
        plan["counter_signal"] = {}
        html = self._apply(plan)
        self.assertNotIn("THE OTHER SIDE", html)
        self.assertIn("WHY IT MATTERS", html)

    def test_would_change_view_omitted_keeps_panel(self):
        plan = _plan()
        del plan["counter_signal"]["would_change_view_if"]
        html = self._apply(plan)
        self.assertIn("THE OTHER SIDE", html)
        self.assertNotIn("WHAT WOULD CHANGE OUR VIEW", html)

    def test_watch_for_this_omitted(self):
        plan = _plan()
        plan["executive_read"]["watch_items"] = []
        html = self._apply(plan)
        self.assertNotIn("WATCH FOR THIS", html)

    def test_joke_omitted(self):
        html = self._apply(_plan(), joke=None)
        self.assertIn("WHY IT MATTERS", html)

    def test_every_optional_section_omitted_at_once(self):
        plan = _plan()
        plan["focus_numbers"] = []
        plan["counter_signal"] = {}
        plan["executive_read"]["watch_items"] = []
        html = self._apply(plan, alive=None, joke=None)

        for gone in (
            "FOCUS ON THE NUMBERS",
            "THE OTHER SIDE",
            "WHAT WOULD CHANGE OUR VIEW",
            "WATCH FOR THIS",
        ):
            self.assertNotIn(gone, html, f"{gone} should have been omitted")

        # The four mandatory sections survive, and the edition is still a
        # well-formed document.
        self.assertIn("WHY IT MATTERS", html)
        self.assertIn("FOUNDER'S NOTE", html)
        self.assertIn("Headline 1", html)
        self.assertIn("Edition 0051", html)
        self.assertTrue(html.strip().endswith("</table>"))

    def test_omitted_edition_has_balanced_tables(self):
        """A dropped panel must not orphan its closing tag."""
        plan = _plan()
        plan["focus_numbers"] = []
        plan["counter_signal"] = {}
        plan["executive_read"]["watch_items"] = []
        html = self._apply(plan, alive=None, joke=None)
        self.assertEqual(
            html.count("<table"),
            html.count("</table>"),
            "unbalanced <table> tags after omitting sections",
        )


if __name__ == "__main__":
    unittest.main()
