from __future__ import annotations

import unittest
from pathlib import Path

from src.release_history import load_cutover_history, merge_release_histories


ROOT = Path(__file__).resolve().parents[1]


class ReleaseHistoryTests(unittest.TestCase):
    def test_cutover_seed_preserves_exact_0047_sources_and_recent_images(self) -> None:
        history = load_cutover_history(ROOT)
        self.assertEqual(10, len(history["source_urls"]))
        self.assertEqual([], history["joke_ids"])
        self.assertEqual(
            ["REMEMBER-0047-NORDERNEY-MARIENHOEHE", "REMEMBER-0048-GARY-PLANT-WELDERS"],
            [moment["id"] for moment in history["alive_moments"]],
        )

    def test_merge_deduplicates_jokes_and_images_without_losing_source_urls(self) -> None:
        merged = merge_release_histories(
            {
                "source_urls": {"https://example.com/one"},
                "joke_ids": ["J001"],
                "alive_moments": [{"id": "IMAGE-1", "date": "2026-09-04"}],
            },
            {
                "source_urls": {"https://example.com/two"},
                "joke_ids": ["J001", "J002"],
                "alive_moments": [{"id": "IMAGE-1", "date": "2026-09-05"}],
            },
        )
        self.assertEqual(
            {"https://example.com/one", "https://example.com/two"},
            merged["source_urls"],
        )
        self.assertEqual(["J001", "J002"], merged["joke_ids"])
        self.assertEqual([{"id": "IMAGE-1", "date": "2026-09-05"}], merged["alive_moments"])


if __name__ == "__main__":
    unittest.main()
