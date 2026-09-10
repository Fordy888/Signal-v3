"""Rejection diagnostic: make a failed plan identifiable from the logs.

Edition 0052 was rejected for "Newsroom source S03 is verified as AI_ADOPTION,
not AI_INDUSTRY_IMPACT", but the plan was never logged, so the offending item
could not be identified afterwards. This summary closes that gap.

Observability only — nothing here affects what the validator accepts.
"""
from __future__ import annotations

import unittest

from src.judgement_plan import _describe_rejected_mix


class RejectedMixSummary(unittest.TestCase):
    def test_reports_source_id_and_claimed_classification(self):
        plan = {
            "evidence_items": [
                {"source_ids": ["S03"], "mix_classification": "AI_INDUSTRY_IMPACT"},
                {"source_ids": ["S07"], "mix_classification": "AI_ADOPTION"},
            ]
        }
        got = _describe_rejected_mix(plan)
        # The exact pair that caused the 0052 rejection must be visible.
        self.assertIn("S03=AI_INDUSTRY_IMPACT", got)
        self.assertIn("S07=AI_ADOPTION", got)

    def test_covers_both_sections(self):
        plan = {
            "evidence_items": [{"source_ids": ["S01"], "mix_classification": "AI_ADOPTION"}],
            "focus_numbers": [{"source_ids": ["S09"], "mix_classification": "AI_INDUSTRY_IMPACT"}],
        }
        got = _describe_rejected_mix(plan)
        self.assertIn("evidence_items:", got)
        self.assertIn("focus_numbers:", got)
        self.assertIn("S09=AI_INDUSTRY_IMPACT", got)

    def test_multi_source_item_is_shown_joined(self):
        plan = {"evidence_items": [
            {"source_ids": ["S01", "S02"], "mix_classification": "AI_ADOPTION"}
        ]}
        self.assertIn("S01+S02=AI_ADOPTION", _describe_rejected_mix(plan))

    def test_missing_classification_is_marked_not_hidden(self):
        plan = {"evidence_items": [{"source_ids": ["S04"]}]}
        self.assertIn("S04=?", _describe_rejected_mix(plan))

    def test_missing_source_ids_is_marked_not_hidden(self):
        plan = {"evidence_items": [{"mix_classification": "AI_ADOPTION"}]}
        self.assertIn("?=AI_ADOPTION", _describe_rejected_mix(plan))


class NeverMasksTheRealError(unittest.TestCase):
    """A malformed plan must never make the diagnostic raise."""

    def test_none_is_handled(self):
        self.assertEqual(_describe_rejected_mix(None), "no plan object")

    def test_non_dict_is_handled(self):
        self.assertEqual(_describe_rejected_mix("garbage"), "no plan object")

    def test_plan_without_classified_items_is_handled(self):
        self.assertEqual(_describe_rejected_mix({}), "no classified items")

    def test_wrong_shaped_sections_are_handled(self):
        self.assertEqual(
            _describe_rejected_mix({"evidence_items": "not a list"}),
            "no classified items",
        )

    def test_non_dict_items_are_skipped(self):
        got = _describe_rejected_mix({"evidence_items": ["junk", None, 42]})
        self.assertEqual(got, "no classified items")

    def test_odd_source_ids_shape_does_not_raise(self):
        got = _describe_rejected_mix(
            {"evidence_items": [{"source_ids": "S03", "mix_classification": "AI_ADOPTION"}]}
        )
        self.assertIn("AI_ADOPTION", got)


if __name__ == "__main__":
    unittest.main()
