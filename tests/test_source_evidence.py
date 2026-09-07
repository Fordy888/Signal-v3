from __future__ import annotations

import unittest

from src.judgement_plan import (
    allocate_ai_adoption_content,
    prepare_ai_adoption_evidence,
    prepare_focus_number_evidence,
    scored_items_to_evidence,
)
from src.scoring import ScoredItem
from datetime import datetime
from zoneinfo import ZoneInfo

from src.sources import RawItem, _entry_source_evidence, resolve_max_age_hours


class SourceEvidenceTests(unittest.TestCase):
    def test_monday_daily_window_bridges_weekend_without_changing_other_runs(self) -> None:
        brisbane = ZoneInfo("Australia/Brisbane")
        monday = datetime(2026, 9, 7, 6, 0, tzinfo=brisbane)
        tuesday = datetime(2026, 9, 8, 6, 0, tzinfo=brisbane)
        saturday = datetime(2026, 9, 5, 6, 0, tzinfo=brisbane)

        self.assertEqual(resolve_max_age_hours(48, "daily", monday), 96)
        self.assertEqual(resolve_max_age_hours(48, "daily", tuesday), 48)
        self.assertEqual(resolve_max_age_hours(48, "weekly_wrap", saturday), 48)

    def test_feed_detail_is_cleaned_and_retained_from_same_entry(self) -> None:
        entry = {
            "summary": "<p>A bank deployed AI into fraud review.</p>",
            "description": "<p>A bank deployed AI into fraud review.</p>",
            "content": [
                {
                    "value": (
                        "<style>.hidden{display:none}</style>"
                        "<p>The bank reduced review costs 27% across customer claims.</p>"
                        "<script>ignore()</script>"
                    )
                }
            ],
        }

        evidence = _entry_source_evidence(entry)

        self.assertIn("A bank deployed AI into fraud review.", evidence)
        self.assertIn("reduced review costs 27%", evidence)
        self.assertNotIn("<p>", evidence)
        self.assertNotIn("ignore()", evidence)

    def test_scoring_payload_includes_bounded_publisher_evidence(self) -> None:
        item = RawItem(
            item_id="rss::bank::1",
            title="Bank changes fraud review",
            summary="A bank deployed AI into fraud review.",
            url="https://example.com/bank-ai",
            source="Example",
            category="banking_finance",
            source_evidence="A bank deployed AI into fraud review, reducing costs 27%.",
        )

        payload = item.to_scoring_payload()

        self.assertEqual(payload["source_evidence"], item.source_evidence)
        self.assertLessEqual(len(payload["source_evidence"]), 1200)

    def test_publisher_detail_repairs_realistic_two_source_focus_attrition(self) -> None:
        scored: list[ScoredItem] = []
        for index in range(1, 11):
            if index in {5, 10}:
                summary = "OpenAI cut enterprise AI prices, reducing software costs for businesses."
                detail = f"OpenAI cut enterprise AI prices {10 + index}%, reducing software costs for businesses."
            else:
                summary = "A bank deployed AI to automate fraud review workflow and improve customer service."
                detail = (
                    f"A bank deployed AI to automate fraud review workflow, reducing costs {10 + index}%."
                    if index <= 4
                    else summary
                )
            raw = RawItem(
                item_id=f"rss::source::{index}",
                title=f"AI business change {index}",
                summary=summary,
                url=f"https://example.com/{index}",
                source=f"Source {index}",
                category="banking_finance",
                source_evidence=detail,
            )
            scored.append(ScoredItem(raw=raw, scores={}, total=30, reason=""))

        evidence = scored_items_to_evidence(scored)
        without_detail = [
            {key: value for key, value in item.items() if key != "source_evidence"}
            for item in evidence
        ]
        base_prepared, base_focus_ids = prepare_focus_number_evidence(without_detail)
        base_prepared, base_classes = prepare_ai_adoption_evidence(base_prepared)
        self.assertEqual(
            sum(
                source_id in base_focus_ids and classification == "AI_ADOPTION"
                for source_id, classification in base_classes.items()
            ),
            0,
        )

        prepared, focus_ids = prepare_focus_number_evidence(evidence)
        prepared, classes = prepare_ai_adoption_evidence(prepared)
        allocation = allocate_ai_adoption_content(prepared, focus_ids, classes)

        self.assertEqual(len(allocation["focus_numbers"]), 5)
        self.assertEqual(len(allocation["newsroom"]), 5)
        self.assertFalse(set(allocation["focus_numbers"]).intersection(allocation["newsroom"]))
        self.assertEqual(
            sum(
                source_id in focus_ids and classification == "AI_ADOPTION"
                for source_id, classification in classes.items()
            ),
            4,
        )


if __name__ == "__main__":
    unittest.main()
