"""Graceful omission: optional sections drop out, mandatory ones halt."""
from __future__ import annotations

import unittest

from src.section_policy import (
    EditionHalt,
    apply_section_policy,
    check_mandatory,
    format_omissions,
)


def _plan(**overrides):
    """A complete, qualifying ai-adoption-v1 plan."""
    plan = {
        "editorial_revision": "ai-adoption-v1",
        "interpretation_headline": "Adoption is outpacing governance",
        "interpretation": "Buyers are deploying faster than controls mature.",
        "evidence_items": [
            {"source_ids": ["S01"], "headline": "One"},
            {"source_ids": ["S02"], "headline": "Two"},
            {"source_ids": ["S03"], "headline": "Three"},
        ],
        "founders_note": {"headline": "The gap is the risk", "body": "Body text — Paul"},
        "executive_read": {
            "dtl_view": "A considered view.",
            "watch_headline": "Procurement cycles shorten",
            "watch_items": ["First observable", "Second observable"],
        },
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
    plan.update(overrides)
    return plan


JOKE = {"id": "J001", "setup": "Why?", "punchline": "Because."}
ALIVE = {"id": "A001", "caption": "A moment"}


class MandatorySectionsHalt(unittest.TestCase):
    def test_complete_plan_passes(self):
        check_mandatory(_plan())  # must not raise

    def test_missing_thesis_halts(self):
        with self.assertRaises(EditionHalt) as ctx:
            check_mandatory(_plan(interpretation=""))
        self.assertIn("Today's Signal thesis", str(ctx.exception))

    def test_fewer_than_three_top_signals_halts(self):
        with self.assertRaises(EditionHalt) as ctx:
            check_mandatory(_plan(evidence_items=[{"headline": "Only one"}]))
        self.assertIn("Top Signals", str(ctx.exception))
        self.assertIn("needs >= 3", str(ctx.exception))

    def test_exactly_three_top_signals_is_enough(self):
        check_mandatory(_plan())  # three items, must not raise

    def test_missing_founders_note_halts(self):
        with self.assertRaises(EditionHalt):
            check_mandatory(_plan(founders_note={"headline": "", "body": ""}))

    def test_missing_executive_read_halts(self):
        with self.assertRaises(EditionHalt) as ctx:
            check_mandatory(_plan(executive_read=None))
        self.assertIn("Executive Read", str(ctx.exception))

    def test_halt_reports_every_failure_at_once(self):
        with self.assertRaises(EditionHalt) as ctx:
            check_mandatory(_plan(interpretation="", founders_note={}, evidence_items=[]))
        message = str(ctx.exception)
        self.assertIn("thesis", message)
        self.assertIn("Top Signals", message)
        self.assertIn("Founder's Note", message)


class OptionalSectionsOmit(unittest.TestCase):
    def test_qualifying_edition_omits_nothing(self):
        _, alive, joke, omissions = apply_section_policy(
            _plan(), alive_moment=ALIVE, joke=JOKE
        )
        self.assertEqual(omissions, [])
        self.assertIsNotNone(alive)
        self.assertIsNotNone(joke)
        self.assertIn("none", format_omissions(omissions))

    def test_short_focus_numbers_is_omitted_not_lowered(self):
        plan = _plan()
        plan["focus_numbers"] = plan["focus_numbers"][:4]  # four, not five
        plan, _, _, omissions = apply_section_policy(
            plan, alive_moment=ALIVE, joke=JOKE
        )
        # Omitted entirely rather than rendered with four figures.
        self.assertNotIn("focus_numbers", plan)
        self.assertEqual(len(omissions), 1)
        self.assertEqual(omissions[0].section, "FOCUS ON THE NUMBERS")
        self.assertIn("supplied 4", omissions[0].reason)

    def test_focus_figure_without_source_is_omitted(self):
        plan = _plan()
        plan["focus_numbers"][2]["source_ids"] = []
        plan, _, _, omissions = apply_section_policy(
            plan, alive_moment=ALIVE, joke=JOKE
        )
        self.assertNotIn("focus_numbers", plan)
        self.assertIn("not bound to a source", omissions[0].reason)

    def test_missing_counter_signal_omits_the_other_side(self):
        plan, _, _, omissions = apply_section_policy(
            _plan(counter_signal={}), alive_moment=ALIVE, joke=JOKE
        )
        self.assertNotIn("counter_signal", plan)
        self.assertEqual([o.section for o in omissions], ["THE OTHER SIDE"])

    def test_counter_signal_without_falsifier_keeps_panel(self):
        plan = _plan()
        del plan["counter_signal"]["would_change_view_if"]
        plan, _, _, omissions = apply_section_policy(
            plan, alive_moment=ALIVE, joke=JOKE
        )
        # The panel survives; only the inner line is omitted.
        self.assertIn("counter_signal", plan)
        self.assertNotIn("would_change_view_if", plan["counter_signal"])
        self.assertEqual([o.section for o in omissions], ["WHAT WOULD CHANGE OUR VIEW"])

    def test_single_watch_item_omits_watch_section(self):
        plan = _plan()
        plan["executive_read"]["watch_items"] = ["Only one"]
        plan, _, _, omissions = apply_section_policy(
            plan, alive_moment=ALIVE, joke=JOKE
        )
        self.assertNotIn("watch_headline", plan["executive_read"])
        self.assertEqual([o.section for o in omissions], ["WATCH FOR THIS"])

    def test_missing_alive_moment_is_omitted_not_fatal(self):
        _, alive, _, omissions = apply_section_policy(
            _plan(), alive_moment=None, joke=JOKE
        )
        self.assertIsNone(alive)
        self.assertEqual([o.section for o in omissions], ["Remember the World"])

    def test_missing_joke_is_omitted_not_fatal(self):
        _, _, joke, omissions = apply_section_policy(
            _plan(), alive_moment=ALIVE, joke=None
        )
        self.assertIsNone(joke)
        self.assertEqual([o.section for o in omissions], ["Dad Joke"])

    def test_every_optional_section_can_go_at_once(self):
        plan = _plan(counter_signal={}, focus_numbers=[])
        plan["executive_read"]["watch_items"] = []
        plan, alive, joke, omissions = apply_section_policy(
            plan, alive_moment=None, joke=None
        )
        sections = {o.section for o in omissions}
        self.assertEqual(
            sections,
            {
                "FOCUS ON THE NUMBERS",
                "THE OTHER SIDE",
                "WATCH FOR THIS",
                "Remember the World",
                "Dad Joke",
            },
        )
        # ...and the edition still stands, because the mandatory four survive.
        check_mandatory(plan)

    def test_omission_reasons_reach_the_receipt_line(self):
        plan = _plan(counter_signal={})
        _, _, _, omissions = apply_section_policy(plan, alive_moment=ALIVE, joke=JOKE)
        line = format_omissions(omissions)
        self.assertIn("THE OTHER SIDE", line)
        self.assertIn("no counter-signal headline", line)


if __name__ == "__main__":
    unittest.main()
