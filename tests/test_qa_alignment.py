import unittest
import os
from unittest.mock import patch
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from src.qa_gate import (
    check_edition_number,
    check_release_identity,
    check_subject_body_alignment,
    create_receipt,
)


class SubjectBodyAlignmentTests(unittest.TestCase):
    def test_calendar_gate_accepts_friday_and_saturday_edition_0042(self):
        brisbane = ZoneInfo("Australia/Brisbane")
        friday = datetime(2026, 8, 28, 6, 0, tzinfo=brisbane)
        saturday = datetime(2026, 8, 29, 6, 0, tzinfo=brisbane)
        self.assertTrue(check_edition_number(42, Path("."), as_of=friday).passed)
        self.assertTrue(check_edition_number(42, Path("."), as_of=saturday).passed)

    def test_calendar_gate_rejects_stale_edition_on_monday(self):
        monday = datetime(
            2026, 8, 31, 6, 0, tzinfo=ZoneInfo("Australia/Brisbane")
        )
        result = check_edition_number(42, Path("."), as_of=monday)
        self.assertFalse(result.passed)
        self.assertEqual(result.severity, "critical")

    @patch("src.qa_gate.datetime")
    def test_rejects_mismatched_daily_footer_stamp(self, mocked_datetime):
        mocked_datetime.now.return_value = datetime(
            2026, 8, 24, 6, 6, tzinfo=ZoneInfo("Australia/Brisbane")
        )
        html = """
        Edition 0038
        Monday 24 August 2026 | 06:06 AEST
        PF::SIGNAL-0038 // 25.08.2026 // 06:06 AEST
        """

        result = check_subject_body_alignment(html, 38)

        self.assertFalse(result.passed)
        self.assertEqual(result.severity, "critical")
        self.assertIn("Footer stamp does not match", result.message)

    @patch("src.qa_gate.datetime")
    def test_accepts_matching_header_and_footer_metadata(self, mocked_datetime):
        mocked_datetime.now.return_value = datetime(
            2026, 8, 24, 6, 6, tzinfo=ZoneInfo("Australia/Brisbane")
        )
        html = """
        Edition 0038
        Monday 24 August 2026 | 06:06 AEST
        PF::SIGNAL-0038 // 24.08.2026 // 06:06 AEST
        """

        result = check_subject_body_alignment(html, 38)

        self.assertTrue(result.passed)


class ReleaseIdentityTests(unittest.TestCase):
    def setUp(self):
        self.monday = datetime(
            2026, 8, 31, 6, 0, tzinfo=ZoneInfo("Australia/Brisbane")
        )
        self.production_env = {
            "RENDER": "true",
            "RENDER_GIT_BRANCH": "master",
            "RENDER_GIT_COMMIT": "abcdef1234567890",
            "RENDER_SERVICE_ID": "crn-d8ouk0bsq97s73fgc36g",
            "SIGNAL_RELEASE_PROFILE": "v4.0",
            "SIGNAL_V4_LAUNCH_DATE": "2026-08-31",
            "SIGNAL_EXPECTED_DAILY_RENDERER": "enhanced-v4-focus-numbers",
            "SIGNAL_EXPECTED_GIT_BRANCH": "master",
            "SIGNAL_EXPECTED_GIT_COMMIT": "abcdef1234567890",
            "SIGNAL_EXPECTED_RENDER_SERVICE_ID": "crn-d8ouk0bsq97s73fgc36g",
            "SIGNAL_TARGET_RELEASE_ID": "focus-numbers-60-40-v1",
            "SIGNAL_EXPECTED_APPROVED_PROOF_SHA256": "7ff05b54870a4ed4e2db737752380bb3d1ae5da915c9f8d3c5b0c9cc67b606e3",
            "SIGNAL_RELEASE_MANIFEST_PATH": "data/release_manifest.json",
        }

    def test_monday_v4_identity_passes_only_with_complete_render_evidence(self):
        with patch.dict(os.environ, self.production_env, clear=False):
            result = check_release_identity(
                renderer_id="enhanced-v4-focus-numbers",
                edition_type="daily",
                mode="send",
                as_of=self.monday,
            )
        self.assertTrue(result.passed)
        self.assertIn("MATCH", result.message)
        self.assertIn("abcdef123456", result.message)

    def test_monday_v4_identity_can_be_enforced_inside_proof_canary(self):
        with patch.dict(os.environ, self.production_env, clear=False):
            result = check_release_identity(
                renderer_id="enhanced-v4-focus-numbers",
                edition_type="daily",
                mode="send",
                as_of=self.monday,
            )
            receipt = create_receipt(
                edition_number=43,
                mode="proof",
                recipients_attempted=1,
                recipients_delivered=1,
                pipeline_result="success",
                code_version="abcdef1234567890",
                edition_type="daily",
                renderer_id="enhanced-v4-focus-numbers",
                html_sha256="2" * 64,
                release_identity_status="MATCH" if result.passed else "MISMATCH",
            )
        self.assertTrue(result.passed)
        self.assertEqual(receipt.release_identity_status, "MATCH")
        self.assertIn("CANARY DELIVERED — TARGET RELEASE MATCHED", receipt.alert_email_html())
        self.assertEqual(
            receipt.alert_email_subject(),
            "[CANARY] DTL Signal 0043 — Target release matched",
        )

    def test_monday_v4_identity_holds_when_live_commit_is_missing(self):
        env = dict(self.production_env)
        env["RENDER_GIT_COMMIT"] = ""
        with patch.dict(os.environ, env, clear=False):
            result = check_release_identity(
                renderer_id="enhanced-v4-focus-numbers",
                edition_type="daily",
                mode="send",
                as_of=self.monday,
            )
        self.assertFalse(result.passed)
        self.assertEqual(result.severity, "critical")
        self.assertIn("RENDER_GIT_COMMIT is missing", result.message)

    def test_monday_v4_identity_holds_if_legacy_command_runs(self):
        with patch.dict(os.environ, self.production_env, clear=False):
            result = check_release_identity(
                renderer_id="legacy-daily",
                edition_type="daily",
                mode="send",
                as_of=self.monday,
            )
        self.assertFalse(result.passed)
        self.assertIn("expected enhanced-v4-focus-numbers", result.message)

    def test_target_release_holds_when_old_commit_is_still_deployed(self):
        env = dict(self.production_env)
        env["RENDER_GIT_COMMIT"] = "6c39f001c256c8d401f34cfbbdaa23ce5041b24a"
        with patch.dict(os.environ, env, clear=False):
            result = check_release_identity(
                renderer_id="enhanced-v4-focus-numbers",
                edition_type="daily",
                mode="send",
                as_of=self.monday,
            )
            receipt = create_receipt(
                edition_number=45,
                mode="send",
                recipients_attempted=33,
                recipients_delivered=33,
                pipeline_result="success",
                code_version=env["RENDER_GIT_COMMIT"],
                edition_type="daily",
                renderer_id="enhanced-v4-focus-numbers",
                html_sha256="3" * 64,
            )
        self.assertFalse(result.passed)
        self.assertIn("deployed commit is 6c39f001c256", result.message)
        self.assertEqual(receipt.release_identity_status, "MISMATCH")
        self.assertIn("DELIVERY SUCCEEDED — TARGET RELEASE MISMATCH", receipt.alert_email_html())
        self.assertIn("approved release is not proven live", receipt.alert_email_html())
        self.assertIn("TARGET RELEASE MISMATCH", receipt.plain_english_summary())
        self.assertEqual(
            receipt.alert_email_subject(),
            "[CRITICAL] DTL Signal 0045 — Delivered; target release MISMATCH",
        )

    def test_edition_0046_target_requires_the_approved_image_identity(self):
        thursday = datetime(
            2026, 9, 3, 6, 0, tzinfo=ZoneInfo("Australia/Brisbane")
        )
        env = dict(self.production_env)
        env["SIGNAL_ALIVE_MOMENT_PATH"] = "data/fixtures/alive_moment_0046.json"
        with patch.dict(os.environ, env, clear=False):
            matched = check_release_identity(
                renderer_id="enhanced-v4-focus-numbers",
                edition_type="daily",
                mode="send",
                as_of=thursday,
            )
            receipt = create_receipt(
                edition_number=46,
                mode="send",
                pipeline_result="success",
                code_version=env["RENDER_GIT_COMMIT"],
                edition_type="daily",
                renderer_id="enhanced-v4-focus-numbers",
                html_sha256="5" * 64,
            )
        self.assertTrue(matched.passed)
        self.assertEqual(
            receipt.approved_image_identity,
            "REMEMBER-0046-QUANG-PHU-CAU-INCENSE",
        )
        self.assertEqual(receipt.configured_image_identity, receipt.approved_image_identity)
        self.assertIn("REMEMBER-0046-QUANG-PHU-CAU-INCENSE", receipt.alert_email_html())

        stale = dict(env)
        stale["SIGNAL_ALIVE_MOMENT_PATH"] = "data/fixtures/alive_moment_0043.json"
        with patch.dict(os.environ, stale, clear=False):
            mismatched = check_release_identity(
                renderer_id="enhanced-v4-focus-numbers",
                edition_type="daily",
                mode="send",
                as_of=thursday,
            )
        self.assertFalse(mismatched.passed)
        self.assertIn("image identity is", mismatched.message)

    def test_plain_proof_delivery_never_claims_target_release_is_live(self):
        with patch.dict(os.environ, self.production_env, clear=False):
            receipt = create_receipt(
                edition_number=46,
                mode="proof",
                recipients_attempted=1,
                recipients_delivered=1,
                pipeline_result="success",
                code_version="local-proof",
                edition_type="daily",
                renderer_id="enhanced-v4-focus-numbers",
                html_sha256="4" * 64,
            )
        self.assertEqual(receipt.release_identity_status, "OBSERVED_ONLY")
        self.assertIn("PROOF DELIVERED — TARGET RELEASE NOT VERIFIED", receipt.alert_email_html())
        self.assertIn("not evidence that the target release is deployed", receipt.plain_english_summary())
        self.assertEqual(
            receipt.alert_email_subject(),
            "[PROOF] DTL Signal 0046 — Delivered; target release not verified",
        )

    def test_receipt_exposes_release_identity_and_never_precertifies_tomorrow(self):
        with patch.dict(os.environ, self.production_env, clear=False):
            receipt = create_receipt(
                edition_number=43,
                mode="send",
                recipients_attempted=32,
                recipients_delivered=32,
                pipeline_result="success",
                code_version="abcdef1234567890",
                edition_type="daily",
                renderer_id="enhanced-v4-focus-numbers",
                html_sha256="1" * 64,
            )
        html = receipt.alert_email_html()
        self.assertEqual(receipt.release_identity_status, "MATCH")
        self.assertIn("DELIVERED — TARGET RELEASE MATCHED", html)
        self.assertIn("enhanced-v4-focus-numbers", html)
        self.assertIn("abcdef1234567890", html)
        self.assertIn("focus-numbers-60-40-v1", html)
        self.assertIn("7ff05b54870a4ed4e2db737752380bb3d1ae5da915c9f8d3c5b0c9cc67b606e3", html)
        self.assertIn("1" * 64, html)
        self.assertIn("Not pre-certified", html)
        self.assertNotIn("Tomorrow's edition is safe", html)

    def test_render_blueprint_uses_v4_daily_command_and_build_gate(self):
        blueprint = yaml.safe_load((Path(__file__).resolve().parents[1] / "render.yaml").read_text())
        service = next(item for item in blueprint["services"] if item["name"] == "dtl-signal")
        self.assertEqual(
            service["startCommand"],
            "python -m src.main --send --enhanced --alive-moment",
        )
        self.assertIn("python -m unittest discover -s tests -v", service["buildCommand"])
        env = {item["key"]: item.get("value") for item in service["envVars"]}
        self.assertEqual(env["SIGNAL_RELEASE_PROFILE"], "v4.0")
        self.assertEqual(env["SIGNAL_V4_LAUNCH_DATE"], "2026-08-31")
        self.assertEqual(env["SIGNAL_EXPECTED_DAILY_RENDERER"], "enhanced-v4-focus-numbers")
        self.assertEqual(env["SIGNAL_EXPECTED_GIT_BRANCH"], "master")
        expected_commit = next(
            item for item in service["envVars"]
            if item["key"] == "SIGNAL_EXPECTED_GIT_COMMIT"
        )
        self.assertFalse(expected_commit.get("value"))
        self.assertEqual(env["SIGNAL_TARGET_RELEASE_ID"], "focus-numbers-60-40-v1")
        self.assertEqual(
            env["SIGNAL_EXPECTED_APPROVED_PROOF_SHA256"],
            "7ff05b54870a4ed4e2db737752380bb3d1ae5da915c9f8d3c5b0c9cc67b606e3",
        )
        self.assertEqual(
            env["SIGNAL_EXPECTED_RENDER_SERVICE_ID"],
            "crn-d8ouk0bsq97s73fgc36g",
        )
        self.assertEqual(env["SIGNAL_ALIVE_MOMENT_PATH"], "data/fixtures/alive_moment_0046.json")
        proof_service = next(
            item for item in blueprint["services"] if item["name"] == "dtl-signal-proof"
        )
        self.assertEqual(
            proof_service["startCommand"],
            "python -m src.main --proof --release-canary --enhanced --alive-moment --as-of 2026-09-03T06:00:00+10:00 --save-html data/deployed-canary-0046.html",
        )


if __name__ == "__main__":
    unittest.main()
