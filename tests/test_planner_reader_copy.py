"""Planner reader-copy repair and informed retries.

These cover the two changes made after Edition 0052 aborted on
"Newsroom AI_ADOPTION reader copy must state an explicit AI subject and
concrete business consequence":

  A. retries now quote the actual validation error back to the planner
  B. Top Signals (Newsroom) items get the same final-attempt reader-copy
     repair that Focus items have had since 0048

The point of both is to help the planner MEET the bar. The bar itself must not
move, so the first test class pins the validator's behaviour.
"""
from __future__ import annotations

import unittest

from src.judgement_plan import (
    JudgementPlanError,
    _reader_sentence_from_source,
    _retry_suffix,
    _validate_reader_visible_mix_copy,
    complete_newsroom_reader_copy,
)

# A sentence that genuinely clears the bar: names an AI system and a concrete
# commercial consequence, and describes a real operating change.
GOOD = (
    "Telstra deployed an AI call-routing system that cut average handling time "
    "by 18 percent and reduced contact-centre costs."
)
# Real AI subject and a business-shaped verb, but no adoption evidence — no
# real-world use, process or operating change.
NO_ADOPTION = "The company announced a new AI model architecture this week."
# Real AI subject, but no business consequence at all.
NO_CONSEQUENCE = "The AI model was discussed at a conference."
# Business consequence, but no AI subject.
NO_AI = "The company cut operating costs by 18 percent after restructuring."


def _source(**over):
    src = {
        "source_id": "S01",
        "title": "Telstra automates contact-centre routing",
        "evidence": GOOD,
        "source_evidence": "",
        "scoring_reason": "",
    }
    src.update(over)
    return src


def _plan(evidence_items):
    return {
        "editorial_revision": "ai-adoption-v1",
        "evidence_items": evidence_items,
    }


class StandardIsUnchanged(unittest.TestCase):
    """The validation gate must behave exactly as before. Guard against drift."""

    def test_ai_item_without_a_consequence_is_still_rejected(self):
        with self.assertRaises(JudgementPlanError) as ctx:
            _validate_reader_visible_mix_copy(
                {"headline": "Model released", "evidence": NO_CONSEQUENCE},
                "AI_ADOPTION",
                section="Newsroom",
            )
        self.assertIn("explicit AI subject", str(ctx.exception))

    def test_adoption_item_without_adoption_evidence_is_still_rejected(self):
        """AI subject + business verb is not enough for AI_ADOPTION."""
        with self.assertRaises(JudgementPlanError) as ctx:
            _validate_reader_visible_mix_copy(
                {"headline": "Model released", "evidence": NO_ADOPTION},
                "AI_ADOPTION",
                section="Newsroom",
            )
        self.assertIn("real-world use, process", str(ctx.exception))

    def test_ai_item_without_ai_subject_is_still_rejected(self):
        with self.assertRaises(JudgementPlanError):
            _validate_reader_visible_mix_copy(
                {"headline": "Costs fall", "evidence": NO_AI},
                "AI_BUSINESS",
                section="Newsroom",
            )

    def test_major_business_with_ai_angle_is_still_rejected(self):
        with self.assertRaises(JudgementPlanError) as ctx:
            _validate_reader_visible_mix_copy(
                {"headline": "Telstra results", "evidence": GOOD},
                "MAJOR_BUSINESS",
                section="Newsroom",
            )
        self.assertIn("must not introduce an AI-led angle", str(ctx.exception))

    def test_qualifying_item_still_passes(self):
        _validate_reader_visible_mix_copy(
            {"headline": "Telstra cuts handling time", "evidence": GOOD},
            "AI_ADOPTION",
            section="Newsroom",
        )  # must not raise

    def test_validator_still_reads_only_reader_visible_fields(self):
        """Burying the wording in ai_business_connection must NOT satisfy it."""
        with self.assertRaises(JudgementPlanError):
            _validate_reader_visible_mix_copy(
                {
                    "headline": "Model released",
                    "evidence": NO_ADOPTION,
                    "ai_business_connection": GOOD,
                },
                "AI_ADOPTION",
                section="Newsroom",
            )


class SentenceSelection(unittest.TestCase):
    def test_returns_a_qualifying_sentence(self):
        got = _reader_sentence_from_source(_source(), "AI_ADOPTION", word_limit=26)
        self.assertIsNotNone(got)
        self.assertIn("AI", got)

    def test_refuses_when_source_lacks_a_consequence(self):
        src = _source(title=NO_CONSEQUENCE, evidence=NO_CONSEQUENCE)
        self.assertIsNone(
            _reader_sentence_from_source(src, "AI_ADOPTION", word_limit=26)
        )

    def test_refuses_when_source_lacks_an_ai_subject(self):
        src = _source(title=NO_AI, evidence=NO_AI)
        self.assertIsNone(_reader_sentence_from_source(src, "AI_BUSINESS", word_limit=26))

    def test_result_respects_the_word_limit(self):
        got = _reader_sentence_from_source(_source(), "AI_ADOPTION", word_limit=26)
        self.assertLessEqual(len(got.split()), 26)

    def test_a_trim_that_breaks_the_bar_is_refused(self):
        """Trimming must never smuggle through copy that no longer qualifies."""
        # The consequence sits at the end, so a tight limit removes it.
        self.assertIsNone(
            _reader_sentence_from_source(_source(), "AI_ADOPTION", word_limit=4)
        )

    def test_sentence_carrying_a_source_id_is_skipped(self):
        src = _source(evidence="S01 shows " + GOOD, source_evidence="", scoring_reason="")
        got = _reader_sentence_from_source(src, "AI_ADOPTION", word_limit=26)
        self.assertIsNone(got)


class NewsroomRepair(unittest.TestCase):
    def test_repairs_a_failing_newsroom_item_from_its_own_source(self):
        plan = _plan([{
            "source_ids": ["S01"],
            "mix_classification": "AI_ADOPTION",
            "headline": "Telstra changes routing",
            "evidence": NO_ADOPTION,
        }])
        repaired, repairs = complete_newsroom_reader_copy(plan, [_source()])
        self.assertEqual(repairs, ["evidence_items[0].evidence"])
        item = repaired["evidence_items"][0]
        # It now passes the untouched validator.
        _validate_reader_visible_mix_copy(item, "AI_ADOPTION", section="Newsroom")
        self.assertEqual(item["reader_copy_completed_from_source"], "S01")

    def test_headline_is_never_rewritten(self):
        plan = _plan([{
            "source_ids": ["S01"],
            "mix_classification": "AI_ADOPTION",
            "headline": "Telstra changes routing",
            "evidence": NO_ADOPTION,
        }])
        repaired, _ = complete_newsroom_reader_copy(plan, [_source()])
        self.assertEqual(repaired["evidence_items"][0]["headline"], "Telstra changes routing")

    def test_already_qualifying_item_is_left_alone(self):
        plan = _plan([{
            "source_ids": ["S01"],
            "mix_classification": "AI_ADOPTION",
            "headline": "Telstra cuts handling time",
            "evidence": GOOD,
        }])
        repaired, repairs = complete_newsroom_reader_copy(plan, [_source()])
        self.assertEqual(repairs, [])
        self.assertEqual(repaired["evidence_items"][0]["evidence"], GOOD)

    def test_major_business_is_never_touched(self):
        plan = _plan([{
            "source_ids": ["S01"],
            "mix_classification": "MAJOR_BUSINESS",
            "headline": "Telstra results",
            "evidence": "Revenue rose 4 percent.",
        }])
        repaired, repairs = complete_newsroom_reader_copy(plan, [_source()])
        self.assertEqual(repairs, [])

    def test_item_citing_two_sources_is_not_repaired(self):
        """Never blend language across sources."""
        plan = _plan([{
            "source_ids": ["S01", "S02"],
            "mix_classification": "AI_ADOPTION",
            "headline": "Telstra changes routing",
            "evidence": NO_ADOPTION,
        }])
        _, repairs = complete_newsroom_reader_copy(
            plan, [_source(), _source(source_id="S02")]
        )
        self.assertEqual(repairs, [])

    def test_no_repair_when_the_source_cannot_support_it(self):
        plan = _plan([{
            "source_ids": ["S01"],
            "mix_classification": "AI_ADOPTION",
            "headline": "Something happened",
            "evidence": NO_ADOPTION,
        }])
        weak = _source(title=NO_CONSEQUENCE, evidence=NO_CONSEQUENCE)
        _, repairs = complete_newsroom_reader_copy(plan, [weak])
        self.assertEqual(repairs, [])

    def test_source_ids_and_classification_are_never_changed(self):
        plan = _plan([{
            "source_ids": ["S01"],
            "mix_classification": "AI_ADOPTION",
            "headline": "Telstra changes routing",
            "evidence": NO_ADOPTION,
        }])
        repaired, _ = complete_newsroom_reader_copy(plan, [_source()])
        item = repaired["evidence_items"][0]
        self.assertEqual(item["source_ids"], ["S01"])
        self.assertEqual(item["mix_classification"], "AI_ADOPTION")

    def test_repaired_evidence_respects_the_28_word_bound(self):
        plan = _plan([{
            "source_ids": ["S01"],
            "mix_classification": "AI_ADOPTION",
            "headline": "Telstra changes routing",
            "evidence": NO_ADOPTION,
        }])
        repaired, _ = complete_newsroom_reader_copy(plan, [_source()])
        self.assertLessEqual(len(repaired["evidence_items"][0]["evidence"].split()), 28)


class InformedRetries(unittest.TestCase):
    def test_first_attempt_carries_no_suffix(self):
        self.assertEqual(_retry_suffix(0, None), "")

    def test_retry_quotes_the_actual_error(self):
        err = JudgementPlanError(
            "Newsroom AI_ADOPTION reader copy must state an explicit AI subject "
            "and concrete business consequence"
        )
        suffix = _retry_suffix(1, err)
        self.assertIn("REJECTED", suffix)
        self.assertIn("explicit AI subject", suffix)
        self.assertIn("retry 2", suffix)

    def test_retry_forbids_relaxing_or_dropping_sections(self):
        suffix = _retry_suffix(1, JudgementPlanError("boom"))
        self.assertIn("do not relax any of them", suffix)
        self.assertIn("do not drop or shorten a section", suffix)

    def test_retry_without_a_recorded_error_still_nudges(self):
        suffix = _retry_suffix(2, None)
        self.assertIn("retry 3", suffix)
        self.assertNotIn("REJECTED", suffix)


if __name__ == "__main__":
    unittest.main()
