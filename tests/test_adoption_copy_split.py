"""The two corrections made after Edition 0052's fourth run.

1. Internal marker fields are stripped from the JSON shown to the repair model.
   The model saw "reader_copy_completed_from_source" in the plan, inferred a
   sibling "reader_copy" field, and wrote its fixes into a field that does not
   exist — burning a whole generation's repair budget on a phantom.

2. For AI_ADOPTION the AI subject may be named in the headline or the copy
   field (the reader sees them as one unit), while the real-world use and the
   business consequence must both be explicit in the copy field itself.

Correction 2 is a TIGHTENING on two of the three elements: adoption evidence
and business consequence must now live in the short copy rather than anywhere
in the combined text. Nothing is relaxed. The first class below pins that.
"""
from __future__ import annotations

import json
import unittest

from src.judgement_plan import (
    INTERNAL_PLAN_FIELDS,
    _has_ai_adoption_evidence,
    JudgementPlanError,
    _validate_reader_visible_mix_copy,
    build_repair_prompt,
    strip_internal_fields,
)

# Names the AI, the real-world use and the consequence — clears the bar alone.
FULL_COPY = (
    "Telstra deployed an AI call-routing system that cut average handling time "
    "by 18 percent and reduced contact-centre costs."
)
# Names the AI and a real-world use, but no business consequence.
AI_AND_USE_ONLY = "The bank deployed an AI assistant across its claims processing team."
# Names the AI and a consequence, but no real-world use or operating change.
AI_AND_CONSEQUENCE_ONLY = "The AI vendor reduced its licensing costs this quarter."


class AdoptionCopyMustCarryUseAndConsequence(unittest.TestCase):
    """Tightening: for AI_ADOPTION both must be in the copy field itself."""

    def test_fully_qualifying_copy_passes(self):
        _validate_reader_visible_mix_copy(
            {"headline": "Telstra cuts handling time", "evidence": FULL_COPY},
            "AI_ADOPTION",
            section="Newsroom",
        )  # must not raise

    def test_consequence_only_in_headline_is_rejected(self):
        """Previously the combined text satisfied this. Now the copy must."""
        with self.assertRaises(JudgementPlanError) as ctx:
            _validate_reader_visible_mix_copy(
                {"headline": "AI routing cuts costs 18 percent",
                 "evidence": AI_AND_USE_ONLY},
                "AI_ADOPTION",
                section="Newsroom",
            )
        self.assertIn("explicit AI subject", str(ctx.exception))

    def test_real_world_use_only_in_headline_is_rejected(self):
        with self.assertRaises(JudgementPlanError) as ctx:
            _validate_reader_visible_mix_copy(
                {"headline": "Telstra deploys AI routing across contact centre",
                 "evidence": AI_AND_CONSEQUENCE_ONLY},
                "AI_ADOPTION",
                section="Newsroom",
            )
        self.assertIn("real-world use, process", str(ctx.exception))

    def test_focus_section_uses_meaning_as_its_copy_field(self):
        _validate_reader_visible_mix_copy(
            {"entity": "Telstra", "number": "18 percent lower handling time",
             "meaning": FULL_COPY},
            "AI_ADOPTION",
            section="Focus",
        )  # must not raise

    def test_focus_consequence_borrowed_from_number_is_rejected(self):
        with self.assertRaises(JudgementPlanError):
            _validate_reader_visible_mix_copy(
                {"entity": "Telstra", "number": "18 percent cost reduction",
                 "meaning": AI_AND_USE_ONLY},
                "AI_ADOPTION",
                section="Focus",
            )


class AdoptionEvidenceCouplingIsPinned(unittest.TestCase):
    """Documents a real constraint found while implementing this change.

    _has_ai_adoption_evidence internally requires AI_SUBJECT_RE and
    BUSINESS_IMPACT_RE in the SAME text. So requiring adoption evidence in the
    copy field independently forces the AI subject into the copy too — the
    "AI subject may come from the headline" allowance cannot take effect for
    AI_ADOPTION items. Pinned so the limitation is visible rather than assumed
    away; changing it would mean altering an evidence standard, which is out of
    scope.
    """

    def test_adoption_evidence_requires_the_ai_subject_in_the_same_text(self):
        no_ai = "The bank deployed the system across claims processing, cutting costs 18 percent."
        self.assertFalse(_has_ai_adoption_evidence(no_ai))

    def test_so_ai_named_only_in_the_headline_cannot_satisfy_adoption(self):
        with self.assertRaises(JudgementPlanError):
            _validate_reader_visible_mix_copy(
                {"headline": "Telstra AI routing cuts handling time",
                 "evidence": "The rollout cut average handling time by 18 percent."},
                "AI_ADOPTION",
                section="Newsroom",
            )


class OtherClassificationsUnchanged(unittest.TestCase):
    """The split applies to AI_ADOPTION only. Nothing else moved."""

    def test_ai_industry_impact_may_still_span_the_combined_text(self):
        _validate_reader_visible_mix_copy(
            {"headline": "AI chip demand lifts supplier revenue",
             "evidence": "Orders rose sharply across the quarter."},
            "AI_INDUSTRY_IMPACT",
            section="Newsroom",
        )  # must not raise

    def test_ai_business_may_still_span_the_combined_text(self):
        _validate_reader_visible_mix_copy(
            {"headline": "AI platform lifts quarterly revenue",
             "evidence": "The increase came through in the latest results."},
            "AI_BUSINESS",
            section="Newsroom",
        )  # must not raise

    def test_major_business_with_an_ai_angle_is_still_rejected(self):
        with self.assertRaises(JudgementPlanError) as ctx:
            _validate_reader_visible_mix_copy(
                {"headline": "Telstra results", "evidence": FULL_COPY},
                "MAJOR_BUSINESS",
                section="Newsroom",
            )
        self.assertIn("must not introduce an AI-led angle", str(ctx.exception))


class InternalFieldsAreHidden(unittest.TestCase):
    def _plan(self):
        return {
            "evidence_items": [{
                "source_ids": ["S03"],
                "mix_classification": "AI_ADOPTION",
                "headline": "Telstra AI routing cuts handling time",
                "evidence": FULL_COPY,
                "reader_copy_completed_from_source": "S03",
                "reader_copy": "a phantom field from an earlier repair",
            }],
            "focus_numbers": [{
                "source_ids": ["S14"],
                "entity": "Telstra",
                "number_recovered_from_source": "S14",
            }],
        }

    def test_marker_that_caused_the_phantom_is_removed(self):
        stripped = strip_internal_fields(self._plan())
        item = stripped["evidence_items"][0]
        self.assertNotIn("reader_copy_completed_from_source", item)

    def test_phantom_field_cannot_persist_into_the_next_repair(self):
        stripped = strip_internal_fields(self._plan())
        self.assertNotIn("reader_copy", stripped["evidence_items"][0])

    def test_all_internal_markers_are_covered(self):
        stripped = json.dumps(strip_internal_fields(self._plan()))
        for field in INTERNAL_PLAN_FIELDS:
            self.assertNotIn(field, stripped)

    def test_real_fields_survive_untouched(self):
        item = strip_internal_fields(self._plan())["evidence_items"][0]
        self.assertEqual(item["source_ids"], ["S03"])
        self.assertEqual(item["mix_classification"], "AI_ADOPTION")
        self.assertEqual(item["evidence"], FULL_COPY)
        self.assertEqual(item["headline"], "Telstra AI routing cuts handling time")

    def test_the_working_plan_is_not_mutated(self):
        plan = self._plan()
        strip_internal_fields(plan)
        self.assertIn("reader_copy_completed_from_source", plan["evidence_items"][0])

    def test_repair_prompt_shows_no_internal_fields(self):
        prompt = build_repair_prompt(self._plan(), ValueError("some defect"))
        for field in INTERNAL_PLAN_FIELDS:
            self.assertNotIn(field, prompt)
        # ...but the real content is still there to repair.
        self.assertIn('"S03"', prompt)

    def test_repair_prompt_forbids_inventing_a_field(self):
        prompt = build_repair_prompt(self._plan(), ValueError("some defect"))
        self.assertIn("Do not invent", prompt)


if __name__ == "__main__":
    unittest.main()
