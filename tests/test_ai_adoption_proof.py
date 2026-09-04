import hashlib
import html as html_lib
import json
import re
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.enhanced_renderer import render_enhanced_email
from src.alive_moment import load_alive_moment, validate_alive_moment
from src.judgement_plan import (
    prepare_ai_adoption_evidence,
    prepare_focus_number_evidence,
    validate_judgement_plan,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "data" / "ai-adoption-proof-plan-0047.json"
EVIDENCE_PATH = ROOT / "data" / "ai-adoption-proof-evidence-0047.json"
PROOF_PATH = ROOT / "data" / "ai-adoption-proof-0047.html"
HISTORICAL_PROOF_PATH = ROOT / "data" / "final-founder-led-proof.html"
ALIVE_PATH = ROOT / "data" / "fixtures" / "alive_moment_0047.json"
PROOF_SHA256 = "c43ec4b92fa8bc815ff09538b38e5ee5e32a3882586f90195d6166247c408a06"
HISTORICAL_PROOF_SHA256 = "7ff05b54870a4ed4e2db737752380bb3d1ae5da915c9f8d3c5b0c9cc67b606e3"


class AIAdoptionProofTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(PLAN_PATH.read_text())
        self.evidence = json.loads(EVIDENCE_PATH.read_text())
        prepared, focus_eligible = prepare_focus_number_evidence(self.evidence)
        self.prepared, self.verified_mix = prepare_ai_adoption_evidence(prepared)
        self.allocated = {
            "newsroom": [item["source_ids"][0] for item in self.plan["evidence_items"]],
            "focus_numbers": [item["source_ids"][0] for item in self.plan["focus_numbers"]],
        }
        self.validated = validate_judgement_plan(
            self.plan,
            {item["source_id"] for item in self.prepared},
            focus_eligible,
            self.verified_mix,
            self.allocated,
        )
        self.alive_moment = validate_alive_moment(
            load_alive_moment(ALIVE_PATH),
            history=[],
            expected_edition_id="0047",
            expected_date="2026-09-04",
        )

    def _render(self):
        return render_enhanced_email(
            plan=self.validated,
            sources=self.prepared,
            joke={
                "setup": "Why did the workflow bring a ruler to the meeting?",
                "punchline": "It wanted to measure the impact before scaling.",
            },
            edition_number=47,
            generated_at=datetime(
                2026, 9, 4, 6, 0, tzinfo=ZoneInfo("Australia/Brisbane")
            ),
            alive_moment=self.alive_moment,
        )

    def test_proof_has_eight_adoption_and_two_practical_industry_items(self):
        selected = self.allocated["newsroom"] + self.allocated["focus_numbers"]
        classes = [self.verified_mix[source_id] for source_id in selected]
        self.assertEqual(classes.count("AI_ADOPTION"), 8)
        self.assertEqual(classes.count("AI_INDUSTRY_IMPACT"), 2)
        self.assertEqual(len(set(selected)), 10)

    def test_reader_sequence_and_internal_language_are_locked(self):
        html = self._render()
        ordered = [
            "FOUNDER'S NOTE",
            "DTL SIGNAL NEWSROOM — READ THIS",
            "FOCUS ON THE NUMBERS",
            "WHY IT MATTERS",
            "WHAT TO DO NOW",
            "THE OTHER SIDE",
            "WATCH FOR THIS",
            "REMEMBER THE WORLD",
            "DAD JOKE OF THE DAY",
        ]
        positions = [html.index(marker) for marker in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("Norderney, Germany", html)
        self.assertIn("Dietmar Rabich", html)
        self.assertIn("CC BY-SA 4.0", html)
        for forbidden in (
            "THE ONE THING", "THE EVIDENCE", "THE SHIFT", "WHAT CHANGED",
            "AI_BUSINESS", "MAJOR_BUSINESS", "AI_ADOPTION", "AI_INDUSTRY_IMPACT",
        ):
            self.assertNotIn(forbidden, html)

    def test_each_of_the_ten_source_links_appears_once(self):
        html = self._render()
        hrefs = [html_lib.unescape(value) for value in re.findall(r'href="([^"]+)"', html)]
        source_urls = [item["url"] for item in self.evidence]
        for url in source_urls:
            self.assertEqual(hrefs.count(url), 1, url)
        self.assertEqual(len([href for href in hrefs if href in source_urls]), 10)

    def test_new_and_historical_proof_checksums_are_immutable(self):
        self.assertEqual(hashlib.sha256(PROOF_PATH.read_bytes()).hexdigest(), PROOF_SHA256)
        self.assertEqual(
            hashlib.sha256(HISTORICAL_PROOF_PATH.read_bytes()).hexdigest(),
            HISTORICAL_PROOF_SHA256,
        )
        self.assertEqual(self._render(), PROOF_PATH.read_text())


if __name__ == "__main__":
    unittest.main()
