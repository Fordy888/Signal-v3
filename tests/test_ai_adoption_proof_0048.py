import hashlib
import html as html_lib
import json
import os
import re
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.alive_moment import load_alive_moment, validate_alive_moment
from src.enhanced_renderer import render_enhanced_email
from src.judgement_plan import (
    prepare_ai_adoption_evidence,
    prepare_focus_number_evidence,
    validate_judgement_plan,
)
from src.locked_edition import render_locked_edition
from src.qa_gate import load_release_manifest


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "data" / "ai-adoption-proof-plan-0048.json"
EVIDENCE_PATH = ROOT / "data" / "ai-adoption-proof-evidence-0048.json"
PROOF_PATH = ROOT / "data" / "ai-adoption-proof-0048.html"
MANIFEST_PATH = ROOT / "data" / "release_manifest_ai_adoption_0048.json"
ALIVE_PATH = ROOT / "data" / "fixtures" / "alive_moment_0048.json"
PROOF_SHA256 = "e77af51c5fe7ef1ab1fdd0d2cd571e0b261a2bf6914bc3e8d333e1dd57d2045f"


class AIAdoptionProof0048Tests(unittest.TestCase):
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
        history = [
            json.loads((ROOT / "data" / "fixtures" / name).read_text())
            for name in ("alive_moment_0046.json", "alive_moment_0047.json")
        ]
        self.alive_moment = validate_alive_moment(
            load_alive_moment(ALIVE_PATH),
            history=history,
            expected_edition_id="0048",
            expected_date="2026-09-07",
        )

    def _render(self):
        return render_enhanced_email(
            plan=self.validated,
            sources=self.prepared,
            joke={
                "setup": "Why did the robot take a welding class?",
                "punchline": "It wanted to make stronger connections.",
            },
            edition_number=48,
            generated_at=datetime(
                2026, 9, 7, 6, 0, tzinfo=ZoneInfo("Australia/Brisbane")
            ),
            alive_moment=self.alive_moment,
        )

    def test_proof_has_adoption_majority_in_both_sections(self):
        newsroom_classes = [
            self.verified_mix[source_id] for source_id in self.allocated["newsroom"]
        ]
        focus_classes = [
            self.verified_mix[source_id] for source_id in self.allocated["focus_numbers"]
        ]
        selected = self.allocated["newsroom"] + self.allocated["focus_numbers"]
        self.assertEqual(newsroom_classes.count("AI_ADOPTION"), 3)
        self.assertEqual(focus_classes.count("AI_ADOPTION"), 4)
        self.assertEqual((newsroom_classes + focus_classes).count("AI_ADOPTION"), 7)
        self.assertEqual((newsroom_classes + focus_classes).count("AI_INDUSTRY_IMPACT"), 3)
        self.assertEqual(len(set(selected)), 10)

    def test_reader_sequence_and_internal_language_are_locked(self):
        rendered = self._render()
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
        positions = [rendered.index(marker) for marker in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("Gary, United States", rendered)
        self.assertIn("M. Marshall", rendered)
        self.assertIn("PUBLIC DOMAIN", rendered)
        for forbidden in (
            "THE ONE THING",
            "THE EVIDENCE",
            "THE SHIFT",
            "WHAT CHANGED",
            "AI_BUSINESS",
            "MAJOR_BUSINESS",
            "AI_ADOPTION",
            "AI_INDUSTRY_IMPACT",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_each_source_link_appears_once_and_does_not_repeat_0047(self):
        rendered = self._render()
        hrefs = [html_lib.unescape(value) for value in re.findall(r'href="([^"]+)"', rendered)]
        source_urls = [item["url"] for item in self.evidence]
        prior_urls = {
            item["url"]
            for item in json.loads(
                (ROOT / "data" / "ai-adoption-proof-evidence-0047.json").read_text()
            )
        }
        for url in source_urls:
            self.assertEqual(hrefs.count(url), 1, url)
        self.assertEqual(len([href for href in hrefs if href in source_urls]), 10)
        self.assertFalse(set(source_urls).intersection(prior_urls))

    def test_proof_and_proposed_manifest_checksums_match(self):
        rendered = self._render()
        self.assertEqual(hashlib.sha256(PROOF_PATH.read_bytes()).hexdigest(), PROOF_SHA256)
        self.assertEqual(rendered, PROOF_PATH.read_text())
        with patch.dict(
            os.environ,
            {"SIGNAL_RELEASE_MANIFEST_PATH": str(MANIFEST_PATH)},
            clear=False,
        ):
            manifest = load_release_manifest()
        self.assertEqual(manifest["status"], "PROPOSED")
        self.assertEqual(manifest["approved_proof_sha256"], PROOF_SHA256)
        self.assertEqual(
            manifest["editorial_contract"]["minimum_ai_adoption_items"], 6
        )
        self.assertEqual(
            manifest["editorial_contract"]["minimum_ai_adoption_items_per_section"],
            3,
        )

    def test_locked_manifest_reproduces_exact_committed_proof(self):
        html, plan, evidence, joke, moment = render_locked_edition(ROOT, 48)
        self.assertEqual(html, PROOF_PATH.read_text())
        self.assertEqual(hashlib.sha256(html.encode()).hexdigest(), PROOF_SHA256)
        self.assertEqual(plan["editorial_revision"], "ai-adoption-v1")
        self.assertEqual(len(evidence), 10)
        self.assertEqual(joke["setup"], "Why did the robot take a welding class?")
        self.assertEqual(moment["id"], "REMEMBER-0048-GARY-PLANT-WELDERS")
        self.assertEqual(moment["date"], "2026-09-07")


if __name__ == "__main__":
    unittest.main()
