"""Repair-based planning: minimum-change repair, bounded, with protected fields.

Regenerating the whole plan on each rejection re-rolled fields that were already
valid, so fixing the reported defect could break another. These cover the repair
machinery that replaces it.

Nothing here relaxes validation — repairs are re-validated by the same
untouched validator, and a repair that moves a protected fact is discarded.
"""
from __future__ import annotations

import json
import unittest

from src.judgement_plan import (
    MAX_GENERATIONS,
    MAX_REPAIRS,
    build_repair_prompt,
    diff_plan_fields,
    immutable_violations,
)


def _plan(**over):
    plan = {
        "editorial_revision": "ai-adoption-v1",
        "interpretation": "Adoption is outpacing governance.",
        "evidence_items": [
            {
                "source_ids": ["S03"],
                "mix_classification": "AI_ADOPTION",
                "headline": "Telstra cuts handling time",
                "evidence": "Telstra deployed AI routing and cut handling time 18 percent.",
            },
            {
                "source_ids": ["S12"],
                "mix_classification": "AI_ADOPTION",
                "headline": "Bank automates checks",
                "evidence": "The bank used AI to screen documents, cutting review cost.",
            },
        ],
    }
    plan.update(over)
    return plan


class BudgetIsBounded(unittest.TestCase):
    def test_limits_are_finite_and_small(self):
        self.assertGreaterEqual(MAX_GENERATIONS, 1)
        self.assertGreaterEqual(MAX_REPAIRS, 1)
        self.assertLessEqual(MAX_GENERATIONS * (MAX_REPAIRS + 1), 8)

    def test_worst_case_call_count_is_capped(self):
        """No input can produce more planner calls than this."""
        self.assertEqual(MAX_GENERATIONS * (MAX_REPAIRS + 1), 8)


class FieldDiff(unittest.TestCase):
    def test_identical_plans_report_no_change(self):
        self.assertEqual(diff_plan_fields(_plan(), _plan()), [])

    def test_single_edit_is_located_precisely(self):
        after = _plan()
        after["evidence_items"][1]["evidence"] = "Shorter copy."
        self.assertEqual(
            diff_plan_fields(_plan(), after),
            ["evidence_items[1].evidence"],
        )

    def test_multiple_edits_are_all_reported(self):
        after = _plan()
        after["evidence_items"][0]["headline"] = "New headline"
        after["interpretation"] = "Something else."
        self.assertEqual(
            sorted(diff_plan_fields(_plan(), after)),
            ["evidence_items[0].headline", "interpretation"],
        )

    def test_added_and_removed_fields_are_detected(self):
        after = _plan()
        after["evidence_items"][0].pop("headline")
        after["evidence_items"][0]["note"] = "added"
        changed = diff_plan_fields(_plan(), after)
        self.assertIn("evidence_items[0].headline", changed)
        self.assertIn("evidence_items[0].note", changed)


class ProtectedFieldsCannotMove(unittest.TestCase):
    def test_changing_mix_classification_is_a_violation(self):
        after = _plan()
        after["evidence_items"][0]["mix_classification"] = "AI_INDUSTRY_IMPACT"
        violations = immutable_violations(_plan(), after)
        self.assertTrue(violations)
        self.assertIn("mix_classification", violations[0])

    def test_changing_source_ids_is_a_violation(self):
        after = _plan()
        after["evidence_items"][0]["source_ids"] = ["S99"]
        violations = immutable_violations(_plan(), after)
        self.assertTrue(violations)
        self.assertIn("source_ids", violations[0])

    def test_editing_reader_copy_is_not_a_violation(self):
        """The whole point of a repair — copy may change, facts may not."""
        after = _plan()
        after["evidence_items"][0]["evidence"] = "Repaired copy naming the AI use."
        self.assertEqual(immutable_violations(_plan(), after), [])

    def test_an_unchanged_plan_has_no_violations(self):
        self.assertEqual(immutable_violations(_plan(), _plan()), [])


class RepairPromptContract(unittest.TestCase):
    def setUp(self):
        self.prompt = build_repair_prompt(
            _plan(),
            ValueError("Focus AI_ADOPTION reader copy must state the real-world use"),
        )

    def test_quotes_the_exact_defect(self):
        self.assertIn("Focus AI_ADOPTION reader copy must state the real-world use", self.prompt)

    def test_includes_the_rejected_plan_as_json(self):
        self.assertIn("REJECTED PLAN:", self.prompt)
        self.assertIn('"S03"', self.prompt)
        # The embedded plan must be real JSON, not a paraphrase.
        body = self.prompt.split("REJECTED PLAN:\n", 1)[1]
        self.assertEqual(json.loads(body)["evidence_items"][0]["source_ids"], ["S03"])

    def test_demands_minimum_change(self):
        self.assertIn("minimum field(s) required", self.prompt)
        self.assertIn("byte-identical", self.prompt)

    def test_forbids_moving_protected_facts(self):
        self.assertIn("Never change any source_ids or mix_classification", self.prompt)

    def test_forbids_dropping_a_section_to_dodge_the_error(self):
        self.assertIn("Do not drop, shorten or empty a section", self.prompt)

    def test_keeps_every_other_rule_in_force(self):
        self.assertIn("word limit and evidence requirement", self.prompt)

    def test_requires_a_complete_object_not_a_fragment(self):
        self.assertIn("complete JSON object, not a fragment", self.prompt)


if __name__ == "__main__":
    unittest.main()
