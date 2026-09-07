from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.main import main
from src.weekly_wrap_qa import validate_weekly_wrap_html


ROOT = Path(__file__).resolve().parents[1]


def _scored_items() -> list[dict[str, str]]:
    categories = (
        "ai_market_signals",
        "strategy_decision_making",
        "opportunity_radar",
        "product_service_ideas",
    )
    return [{"category": categories[index % 4]} for index in range(25)]


def _focus_numbers_plan() -> dict:
    plan = json.loads((ROOT / "data" / "edition0042-enhanced-plan.json").read_text())
    plan["editorial_revision"] = "focus-on-the-numbers-v1"
    plan.pop("one_thing")
    plan.pop("visual_signal")
    plan["evidence_items"] = plan["evidence_items"][:5]
    for index, item in enumerate(plan["evidence_items"], 6):
        item["source_ids"] = [f"S{index:02d}"]
        item["mix_classification"] = "AI_BUSINESS" if index <= 8 else "MAJOR_BUSINESS"
        if item["mix_classification"] == "AI_BUSINESS":
            item["headline"] = f"AI changes business story {index}"
            item["evidence"] = "AI is changing a real business process and commercial result."
            item["ai_business_connection"] = "AI changes a real business process, decision or commercial result."
        else:
            item["headline"] = f"Major business story {index}"
            item["evidence"] = "A major company decision changes investment and customer demand."
    plan["interpretation_headline"] = "The numbers are changing operating priorities"
    plan["executive_actions"] = [
        {
            "action_tag": "ACT",
            "headline": "Follow the commercial proof",
            "instruction": "Identify which reported number would genuinely change a decision in your business.",
        }
    ]
    plan["counter_signal"]["headline"] = "One day does not make a pattern"
    plan["executive_read"]["watch_headline"] = "Look for numbers that repeat"
    plan["founders_note"]["body"] = (
        "The most useful business stories usually have a number hiding inside them. Revenue, price, wages, customers and investment tell us whether change is real or merely interesting. Do not chase every headline. Find the number that changes a decision, then ask what it means for your business today. — Paul"
    )
    plan["focus_numbers"] = [
        {
            "source_ids": [f"S0{index}"],
            "entity": f"Business {index}",
            "number": f"{index * 10}% movement",
            "meaning": "The reported movement changes the commercial decision leaders need to consider today.",
        }
        for index in range(1, 6)
    ]
    for index, item in enumerate(plan["focus_numbers"], 1):
        item["mix_classification"] = "AI_BUSINESS" if index <= 3 else "MAJOR_BUSINESS"
        if item["mix_classification"] == "AI_BUSINESS":
            item["meaning"] = "AI changes a real business process and commercial result."
            item["ai_business_connection"] = "AI changes a real business process, decision or commercial result."
    return plan


def _ai_adoption_plan() -> dict:
    plan = _focus_numbers_plan()
    plan["editorial_revision"] = "ai-adoption-v1"
    for index, item in enumerate(plan["evidence_items"]):
        item["mix_classification"] = (
            "AI_INDUSTRY_IMPACT" if index == 4 else "AI_ADOPTION"
        )
        item["headline"] = (
            "OpenAI cuts enterprise AI prices"
            if index == 4
            else "Banks deploy AI into fraud reviews"
        )
        item["evidence"] = (
            "The change reduces software costs for business customers."
            if index == 4
            else "The automated workflow cut operating costs while improving customer service."
        )
        item["ai_business_connection"] = (
            "The explicit AI change affects a real process, cost or business decision."
        )
    for index, item in enumerate(plan["focus_numbers"]):
        item["mix_classification"] = (
            "AI_INDUSTRY_IMPACT" if index == 4 else "AI_ADOPTION"
        )
        item["ai_business_connection"] = (
            "The explicit AI change affects a real process, cost or business decision."
        )
        if index == 4:
            item["entity"] = "OpenAI"
            item["meaning"] = "The AI price cut reduces software costs for business customers."
        else:
            item["entity"] = "Retail AI teams"
            item["meaning"] = "The company used AI to automate customer service work and reduce operating costs."
    return plan


def _ai_adoption_majority_plan() -> dict:
    plan = _ai_adoption_plan()
    item = plan["evidence_items"][3]
    item["mix_classification"] = "AI_INDUSTRY_IMPACT"
    item["headline"] = "AI infrastructure prices change procurement"
    item["evidence"] = "The AI change reduces software costs for business customers."
    return plan


def _focus_evidence() -> list[dict]:
    evidence = json.loads(
        (ROOT / "data" / "fixtures" / "edition0042_evidence.json").read_text()
    )
    for index in range(7, 11):
        evidence.append({
            "source_id": f"S{index:02d}",
            "title": f"Distinct Newsroom story {index}",
            "source": f"Source {index}",
            "url": f"https://example.com/source-{index}",
            "category": "Strategy & Business Model",
            "score": 30,
            "evidence": "A distinct source-backed business development for the Newsroom test.",
        })
    return evidence


def _weekly_html() -> str:
    stories = []
    for index in range(1, 6):
        stories.append(
            f'<tr><td><span>WATCH</span><h2>Story {index}</h2>'
            f'<p><strong>What happened:</strong> Development {index} '
            f'<a href="https://example.com/source-{index}">Source {index}</a></p>'
            '<p><strong>Why it matters:</strong> Commercial implication.</p>'
            '<p><strong>Signal:</strong> Executive response.</p></td></tr>'
        )
    padding = "Weekly analysis and context. " * 50
    return (
        '<table><tr><td>DTL SIGNAL WEEKLY WRAP</td><td>Edition 0042</td></tr>'
        '<tr><td>Saturday 29 August 2026 | 06:00 AEST</td></tr>'
        '<tr><td>The Week in One Signal</td></tr>'
        + "".join(stories)
        + f'<tr><td>{padding}</td></tr>'
        '<tr><td>THE PATTERN</td></tr><tr><td>OPPORTUNITY</td></tr>'
        '<tr><td>RISK</td></tr><tr><td>What to Watch Next Week</td></tr>'
        '<tr><td>EXECUTIVE TAKEAWAY</td></tr>'
        '<tr><td>PF::SIGNAL-0042 // 29.08.2026 // 06:00 AEST</td></tr></table>'
    )


class ReleaseSimulationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "test-only",
                "RESEND_API_KEY": "test-only",
                "RESEND_FROM_EMAIL": "signal@signal.dtlc.ai",
                "PROOF_RECIPIENT_EMAIL": "paul.ford@gmail.com",
                "ENABLE_GAUGE": "static",
                "SIGNAL_RELEASE_PROFILE": "v4.0",
                "SIGNAL_V4_LAUNCH_DATE": "2026-08-31",
                "SIGNAL_EXPECTED_DAILY_RENDERER": "enhanced-v4-focus-numbers",
                "SIGNAL_EXPECTED_GIT_BRANCH": "master",
                "SIGNAL_EXPECTED_GIT_COMMIT": "abcdef1234567890",
                "SIGNAL_EXPECTED_RENDER_SERVICE_ID": "crn-d8ouk0bsq97s73fgc36g",
                "SIGNAL_TARGET_RELEASE_ID": "focus-numbers-60-40-v1",
                "SIGNAL_EXPECTED_APPROVED_PROOF_SHA256": "7ff05b54870a4ed4e2db737752380bb3d1ae5da915c9f8d3c5b0c9cc67b606e3",
                "SIGNAL_RELEASE_MANIFEST_PATH": "data/release_manifest.json",
                "SIGNAL_ALIVE_MOMENT_PATH": "data/fixtures/alive_moment_0046.json",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        logging.shutdown()
        logging.getLogger().handlers.clear()

    def _common_patches(self):
        subscribers = [
            {"email": f"eligible-{i}@example.com", "firstName": f"Reader{i}"}
            for i in range(1, 5)
        ]
        source_counts = {
            "active": 40,
            "disabled": 0,
            "probation": 0,
            "active_names": [f"source-{i}" for i in range(40)],
        }
        return (
            patch("src.main.fetch_subscribers", return_value=subscribers),
            patch("src.main.get_source_counts", return_value=source_counts),
            patch("src.main.fetch_all", return_value=([object()] * 40, [], [])),
            patch("src.main.score_items", return_value=_scored_items()),
            patch("src.main.record_source_failures", return_value=[]),
            patch("src.main.save_receipt", return_value=None),
            patch("src.main.send_brief", return_value=True),
            patch(
                "src.main.verify_alive_moment_asset",
                return_value={
                    "sha256": "f" * 64,
                    "bytes": 1000,
                    "content_type": "image/jpeg",
                },
            ),
        )

    def _run_ai_daily_dry(
        self,
        *,
        as_of: str,
        moment_path: str,
        alive_history: list[dict] | None = None,
        plan: dict | None = None,
    ) -> tuple[int, object, str]:
        output = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
        output.close()
        patches = self._common_patches()
        with ExitStack() as stack:
            entered = [stack.enter_context(item) for item in patches]
            send_mock = entered[6]
            self.last_fetch_mock = entered[2]
            stack.enter_context(
                patch("src.main.scored_items_to_evidence", return_value=_focus_evidence())
            )
            stack.enter_context(
                patch(
                    "src.main.generate_judgement_plan",
                    return_value=plan or _ai_adoption_plan(),
                )
            )
            stack.enter_context(
                patch(
                    "src.main.load_signal_memory",
                    return_value={"version": 1, "positions": [], "events": []},
                )
            )
            stack.enter_context(
                patch("src.main.load_alive_history", return_value=alive_history or [])
            )
            stack.enter_context(
                patch.dict(
                    os.environ,
                    {"SIGNAL_ALIVE_MOMENT_PATH": moment_path},
                    clear=False,
                )
            )
            stack.enter_context(
                patch(
                    "sys.argv",
                    [
                        "signal",
                        "--dry-run",
                        "--enhanced",
                        "--as-of",
                        as_of,
                        "--save-html",
                        output.name,
                    ],
                )
            )
            with redirect_stdout(io.StringIO()):
                result = main()
        html = Path(output.name).read_text()
        Path(output.name).unlink(missing_ok=True)
        return result, send_mock, html

    def _run_locked_send(self, delivery_results: list[bool]) -> tuple[int, object, object, object]:
        recipients = [
            {"email": f"eligible-{i}@example.com", "firstName": f"Reader{i}"}
            for i in range(1, len(delivery_results) + 1)
        ]
        source_counts = {
            "active": 40,
            "disabled": 0,
            "probation": 0,
            "active_names": [f"source-{i}" for i in range(40)],
        }
        friday = datetime(
            2026, 8, 28, 6, 0, tzinfo=ZoneInfo("Australia/Brisbane")
        )
        with ExitStack() as stack:
            stack.enter_context(
                patch.dict(
                    os.environ,
                    {"SIGNAL_REGISTRY_REQUIRED": "0"},
                    clear=False,
                )
            )
            mocked_datetime = stack.enter_context(patch("src.main.datetime"))
            mocked_datetime.now.return_value = friday
            stack.enter_context(patch("src.main.get_next_edition", return_value=42))
            stack.enter_context(patch("src.main.fetch_subscribers", return_value=recipients))
            stack.enter_context(patch("src.main.get_source_counts", return_value=source_counts))
            stack.enter_context(patch("src.main.fetch_all", return_value=([object()] * 40, [], [])))
            stack.enter_context(patch("src.main.score_items", return_value=_scored_items()))
            stack.enter_context(patch("src.main.record_source_failures", return_value=[]))
            stack.enter_context(patch("src.main.recover_signal_memory_from_resend", return_value={"version": 1, "positions": [], "events": []}))
            stack.enter_context(patch("src.main.time.sleep", return_value=None))
            send_mock = stack.enter_context(patch("src.main.send_brief", side_effect=delivery_results))
            save_memory_mock = stack.enter_context(patch("src.main.save_signal_memory"))
            stack.enter_context(patch("src.main.record_joke"))
            stack.enter_context(patch("src.main.record_alive_moment"))
            stack.enter_context(patch("src.main.record_edition"))
            stack.enter_context(patch("src.main.increment_edition"))
            stack.enter_context(patch("src.main.resolve_subscriber_ids", return_value={}))
            stack.enter_context(patch("src.main.save_receipt"))
            receipt_mock = stack.enter_context(patch("src.main.send_receipt_email"))
            stack.enter_context(patch("src.main.ping_heartbeat"))
            stack.enter_context(
                patch(
                    "sys.argv",
                    ["signal", "--send", "--enhanced", "--locked-edition", "42"],
                )
            )
            result = main()
        return result, send_mock, save_memory_mock, receipt_mock

    def test_friday_locked_edition_0042_full_dry_run_never_delivers(self) -> None:
        output = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
        output.close()
        patches = self._common_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6] as send_mock, patch(
            "src.main.synthesise"
        ) as synthesise_mock, patch(
            "sys.argv",
            [
                "signal",
                "--dry-run",
                "--enhanced",
                "--locked-edition",
                "42",
                "--as-of",
                "2026-08-28T06:00:00+10:00",
                "--save-html",
                output.name,
            ],
        ), redirect_stdout(io.StringIO()):
            result = main()
        html = Path(output.name).read_text()
        Path(output.name).unlink(missing_ok=True)
        self.assertEqual(result, 0)
        send_mock.assert_not_called()
        synthesise_mock.assert_not_called()
        self.assertIn("Edition 0042", html)
        self.assertIn("THINK.</span>", html)
        self.assertIn("YOUR SIGNAL AT A GLANCE", html)
        self.assertIn("REMEMBER THE WORLD", html)
        self.assertIn("DAD JOKE OF THE DAY", html)

    def test_all_ai_daily_holds_when_image_record_has_wrong_date(self) -> None:
        result, send_mock, html = self._run_ai_daily_dry(
            as_of="2026-08-31T06:00:00+10:00",
            moment_path="data/fixtures/alive_moment_0046.json",
        )
        self.assertEqual(result, 1)
        send_mock.assert_not_called()
        self.assertEqual(html, "")

    def test_all_ai_daily_holds_when_required_image_record_is_missing(self) -> None:
        result, send_mock, html = self._run_ai_daily_dry(
            as_of="2026-09-04T06:00:00+10:00",
            moment_path="data/fixtures/does-not-exist.json",
        )
        self.assertEqual(result, 1)
        send_mock.assert_not_called()
        self.assertEqual(html, "")

    def test_all_ai_daily_holds_when_image_was_recently_delivered(self) -> None:
        moment = json.loads(
            (ROOT / "data" / "fixtures" / "alive_moment_0047.json").read_text()
        )
        result, send_mock, html = self._run_ai_daily_dry(
            as_of="2026-09-04T06:00:00+10:00",
            moment_path="data/fixtures/alive_moment_0047.json",
            alive_history=[moment],
        )
        self.assertEqual(result, 1)
        send_mock.assert_not_called()
        self.assertEqual(html, "")

    def test_all_ai_daily_renders_fresh_image_before_dad_joke_without_optional_flag(self) -> None:
        result, send_mock, html = self._run_ai_daily_dry(
            as_of="2026-09-04T06:00:00+10:00",
            moment_path="data/alive_moments/{date}.json",
        )
        self.assertEqual(result, 0)
        send_mock.assert_not_called()
        self.assertIn("Edition 0047", html)
        self.assertIn("Friday 04 September 2026", html)
        self.assertIn("THINK.</span>", html)
        self.assertIn("DECIDE.</span>", html)
        self.assertIn("LOOK UP.</span>", html)
        self.assertIn("SMILE.</span>", html)
        self.assertIn("YOUR SIGNAL AT A GLANCE", html)
        self.assertIn("FOUNDER'S NOTE", html)
        self.assertIn("DTL SIGNAL NEWSROOM — READ THIS", html)
        self.assertIn("FOCUS ON THE NUMBERS", html)
        self.assertNotIn("THE EVIDENCE", html)
        self.assertNotIn("THE ONE THING", html)
        self.assertNotIn("THE SHIFT", html)
        self.assertNotIn("WHAT CHANGED", html)
        self.assertIn("REMEMBER THE WORLD", html)
        self.assertIn("Norderney, Germany", html)
        self.assertIn("Dietmar Rabich", html)
        self.assertLess(html.index("REMEMBER THE WORLD"), html.index("DAD JOKE OF THE DAY"))
        self.assertIn("DAD JOKE OF THE DAY", html)
        self.assertIn("PF::SIGNAL-0047 // 04.09.2026 // 06:00 AEST", html)

    def test_monday_0048_majority_uses_weekend_window_and_renders_fresh_image(self) -> None:
        result, send_mock, html = self._run_ai_daily_dry(
            as_of="2026-09-07T06:00:00+10:00",
            moment_path="data/alive_moments/{date}.json",
            plan=_ai_adoption_majority_plan(),
        )

        self.assertEqual(result, 0)
        send_mock.assert_not_called()
        self.last_fetch_mock.assert_called_once()
        self.assertEqual(self.last_fetch_mock.call_args.kwargs["edition_type"], "daily")
        self.assertEqual(
            self.last_fetch_mock.call_args.kwargs["reference_time"].weekday(),
            0,
        )
        self.assertIn("Edition 0048", html)
        self.assertIn("Monday 07 September 2026", html)
        self.assertIn("Gary, United States", html)
        self.assertIn("M. Marshall", html)
        self.assertLess(html.index("REMEMBER THE WORLD"), html.index("DAD JOKE OF THE DAY"))
        self.assertIn("PF::SIGNAL-0048 // 07.09.2026 // 06:00 AEST", html)

    def test_all_ai_release_canary_holds_against_historical_sixty_forty_manifest(self) -> None:
        plan = _ai_adoption_plan()
        evidence = _focus_evidence()
        patches = self._common_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6] as send_mock, patch(
            "src.main.scored_items_to_evidence", return_value=evidence
        ), patch(
            "src.main.generate_judgement_plan", return_value=plan
        ), patch(
            "src.main.load_signal_memory", return_value={"version": 1, "positions": [], "events": []}
        ), patch(
            "src.main.load_alive_history", return_value=[]
        ), patch.dict(
            os.environ,
            {
                "RENDER": "true",
                "RENDER_GIT_BRANCH": "master",
                "RENDER_GIT_COMMIT": "abcdef1234567890",
                "RENDER_SERVICE_ID": "crn-d8ouk0bsq97s73fgc36g",
            },
            clear=False,
        ), patch(
            "sys.argv",
            [
                "signal", "--proof", "--release-canary", "--enhanced",
                "--as-of", "2026-08-31T06:00:00+10:00",
            ],
        ), redirect_stdout(io.StringIO()):
            result = main()

        self.assertEqual(result, 1)
        send_mock.assert_not_called()

    def test_locked_all_ai_release_canary_sends_exact_approved_html_to_paul_only(self) -> None:
        patches = self._common_patches()
        friday = datetime(
            2026, 9, 4, 6, 0, tzinfo=ZoneInfo("Australia/Brisbane")
        )
        approved_html = (ROOT / "data" / "ai-adoption-proof-0047.html").read_text()
        production_env = {
            "RENDER": "true",
            "RENDER_GIT_BRANCH": "master",
            "RENDER_GIT_COMMIT": "abcdef1234567890",
            "RENDER_SERVICE_ID": "crn-d8ouk0bsq97s73fgc36g",
            "SIGNAL_EXPECTED_DAILY_RENDERER": "enhanced-v4-focus-numbers",
            "SIGNAL_EXPECTED_GIT_BRANCH": "master",
            "SIGNAL_EXPECTED_GIT_COMMIT": "abcdef1234567890",
            "SIGNAL_EXPECTED_RENDER_SERVICE_ID": "crn-d8ouk0bsq97s73fgc36g",
            "SIGNAL_TARGET_RELEASE_ID": "ai-adoption-v1-proof-0047",
            "SIGNAL_EXPECTED_APPROVED_PROOF_SHA256": "c43ec4b92fa8bc815ff09538b38e5ee5e32a3882586f90195d6166247c408a06",
            "SIGNAL_RELEASE_MANIFEST_PATH": "data/release_manifest_ai_adoption.json",
            "SIGNAL_ALIVE_MOMENT_PATH": "data/alive_moments/{date}.json",
        }
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, production_env, clear=False))
            mocked_datetime = stack.enter_context(patch("src.main.datetime"))
            mocked_datetime.now.return_value = friday
            stack.enter_context(patch("src.main.get_next_edition", return_value=47))
            entered = [stack.enter_context(item) for item in patches]
            send_mock = entered[6]
            stack.enter_context(
                patch(
                    "src.main.load_signal_memory",
                    return_value={"version": 1, "positions": [], "events": []},
                )
            )
            receipt_mock = stack.enter_context(patch("src.main.send_receipt_email"))
            stack.enter_context(patch("src.main.ping_heartbeat"))
            stack.enter_context(
                patch(
                    "sys.argv",
                    [
                        "signal",
                        "--proof",
                        "--release-canary",
                        "--enhanced",
                        "--alive-moment",
                        "--locked-edition",
                        "47",
                    ],
                )
            )
            with redirect_stdout(io.StringIO()):
                result = main()

        self.assertEqual(result, 0)
        self.assertEqual(send_mock.call_count, 1)
        self.assertEqual(send_mock.call_args.kwargs["recipient_email"], "paul.ford@gmail.com")
        self.assertEqual(
            send_mock.call_args.kwargs["subject_override"],
            "[PROOF] DTL Signal | Final Founder-Led Format | Edition 0047",
        )
        self.assertTrue(send_mock.call_args.kwargs["html_body"].startswith(approved_html))
        receipt = receipt_mock.call_args.args[0]
        self.assertEqual(receipt.release_identity_status, "MATCH")

    def test_monday_proof_subject_uses_the_same_release_clock_as_the_body(self) -> None:
        plan = _focus_numbers_plan()
        evidence = _focus_evidence()
        valid_monday_moment = json.loads(
            (ROOT / "data" / "fixtures" / "alive_moment_0047.json").read_text()
        )
        valid_monday_moment.update(
            {
                "id": "REMEMBER-0043-TEST-CLOCK",
                "edition_id": "0043",
                "date": "2026-08-31",
            }
        )
        production_env = {
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
            "SIGNAL_ALIVE_MOMENT_PATH": "data/fixtures/alive_moment_0047.json",
        }
        patches = self._common_patches()
        with patch.dict(os.environ, production_env, clear=False), patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6] as send_mock, patch(
            "src.main.scored_items_to_evidence", return_value=evidence
        ), patch(
            "src.main.generate_judgement_plan", return_value=plan
        ), patch(
            "src.main.load_signal_memory", return_value={"version": 1, "positions": [], "events": []}
        ), patch(
            "src.main.load_alive_history", return_value=[]
        ), patch(
            "src.main.load_alive_moment", return_value=valid_monday_moment
        ), patch(
            "src.main.send_receipt_email"
        ) as receipt_mock, patch(
            "src.main.ping_heartbeat"
        ), patch(
            "sys.argv",
            [
                "signal",
                "--proof",
                "--release-canary",
                "--enhanced",
                "--alive-moment",
                "--as-of",
                "2026-08-31T06:00:00+10:00",
            ],
        ), redirect_stdout(io.StringIO()):
            result = main()

        self.assertEqual(result, 0)
        self.assertEqual(send_mock.call_count, 1)
        self.assertEqual(
            send_mock.call_args.kwargs["subject_override"],
            "[PROOF] DTL Signal | Final Founder-Led Format | Edition 0043",
        )
        receipt = receipt_mock.call_args.args[0]
        self.assertEqual(receipt.release_identity_status, "MATCH")

    def test_saturday_weekly_wrap_full_dry_run_never_delivers(self) -> None:
        output = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
        output.close()
        patches = self._common_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6] as send_mock, patch(
            "src.main.synthesise", return_value=_weekly_html()
        ), patch(
            "src.main.generate_founders_note", return_value=None
        ), patch(
            "sys.argv",
            [
                "signal",
                "--dry-run",
                "--enhanced",
                "--locked-edition",
                "42",
                "--as-of",
                "2026-08-29T06:00:00+10:00",
                "--save-html",
                output.name,
            ],
        ), redirect_stdout(io.StringIO()):
            result = main()
        html = Path(output.name).read_text()
        Path(output.name).unlink(missing_ok=True)
        self.assertEqual(result, 0)
        send_mock.assert_not_called()
        self.assertIn("WEEKLY WRAP", html)
        self.assertIn("<!-- signal-share-block -->", html)
        self.assertNotIn("YOUR SIGNAL AT A GLANCE", html)
        self.assertNotIn("RATE THIS SIGNAL", html)
        self.assertNotIn("/api/gauge", html)
        self.assertNotIn("SUBSCRIBER_HASH", html)

    def test_weekly_wrap_gate_rejects_four_stories(self) -> None:
        html = _weekly_html().replace("What happened:", "Missing story:", 1)
        passed, issues = validate_weekly_wrap_html(html)
        self.assertFalse(passed)
        self.assertTrue(any("exactly 5" in issue for issue in issues))

    def test_weekly_wrap_gate_rejects_legacy_mismatched_gauge(self) -> None:
        html = _weekly_html().replace(
            "</table>",
            '<p>RATE THIS SIGNAL <a href="https://dtlc.ai/api/gauge?s=5">5</a></p></table>',
        )
        passed, issues = validate_weekly_wrap_html(html)
        self.assertFalse(passed)
        self.assertTrue(any("rating gauge" in issue for issue in issues))

    def test_send_mode_holds_when_live_subscriber_api_returns_empty(self) -> None:
        monday = datetime(
            2026, 8, 31, 6, 0, tzinfo=ZoneInfo("Australia/Brisbane")
        )
        with patch("src.main.datetime") as mocked_datetime, patch(
            "src.main.fetch_subscribers", return_value=[]
        ), patch("src.main.send_alert") as alert_mock, patch(
            "src.main.send_brief"
        ) as send_mock, patch("sys.argv", ["signal", "--send"]):
            mocked_datetime.now.return_value = monday
            result = main()
        self.assertEqual(result, 1)
        alert_mock.assert_called_once()
        send_mock.assert_not_called()

    def test_registry_proof_preparation_freezes_one_recipient_without_delivery(self) -> None:
        patches = self._common_patches()
        frozen = SimpleNamespace(
            id="registry-proof-0048",
            edition_number=48,
            release_scope="proof",
            html_sha256="e" * 64,
            audience_count=1,
        )
        with ExitStack() as stack:
            entered = [stack.enter_context(item) for item in patches]
            send_mock = entered[6]
            image_asset_mock = entered[7]
            fetch_mock = entered[2]
            score_mock = entered[3]
            evidence_mock = stack.enter_context(
                patch("src.main.scored_items_to_evidence")
            )
            planner_mock = stack.enter_context(
                patch("src.main.generate_judgement_plan")
            )
            stack.enter_context(
                patch(
                    "src.main.load_signal_memory",
                    return_value={"version": 1, "positions": [], "events": []},
                )
            )
            stack.enter_context(patch("src.main.load_alive_history", return_value=[]))
            stack.enter_context(patch("src.main.ReleaseRegistry.from_env", return_value=object()))
            prepare_mock = stack.enter_context(
                patch("src.main.prepare_registry_release", return_value=frozen)
            )
            stack.enter_context(
                patch.dict(
                    os.environ,
                    {"SIGNAL_ALIVE_MOMENT_PATH": "data/alive_moments/{date}.json"},
                    clear=False,
                )
            )
            stack.enter_context(
                patch(
                    "sys.argv",
                    [
                        "signal",
                        "--prepare-release",
                        "--release-scope",
                        "proof",
                        "--enhanced",
                        "--locked-edition",
                        "48",
                        "--release-date",
                        "2026-09-07",
                        "--as-of",
                        "2026-09-07T07:00:00+10:00",
                    ],
                )
            )
            with redirect_stdout(io.StringIO()):
                result = main()

        self.assertEqual(0, result)
        send_mock.assert_not_called()
        fetch_mock.assert_not_called()
        score_mock.assert_not_called()
        evidence_mock.assert_not_called()
        planner_mock.assert_not_called()
        image_asset_mock.assert_called_once()
        kwargs = prepare_mock.call_args.kwargs
        self.assertEqual("proof", kwargs["release_scope"])
        self.assertEqual(1, len(kwargs["recipients"]))
        self.assertEqual("paul.ford@gmail.com", kwargs["recipients"][0]["email"])
        self.assertEqual(6, kwargs["issue_time"].hour)
        self.assertEqual(7, kwargs["delivery_time"].hour)
        self.assertEqual(
            "e77af51c5fe7ef1ab1fdd0d2cd571e0b261a2bf6914bc3e8d333e1dd57d2045f",
            hashlib.sha256(kwargs["html"].encode()).hexdigest(),
        )
        self.assertEqual(10, len(kwargs["metadata"]["source_urls"]))

    def test_registry_delivery_bypasses_generation_and_uses_locked_release(self) -> None:
        registry_result = {
            "release_id": "registry-proof-0048",
            "edition_number": 48,
            "scope": "proof",
            "state": "DELIVERED",
            "sent": 1,
            "failed": 0,
            "total": 1,
            "html_sha256": "e" * 64,
            "audience_sha256": "a" * 64,
        }
        with patch("src.main.ReleaseRegistry.from_env", return_value=object()), patch(
            "src.main.deliver_registry_release", return_value=registry_result
        ) as deliver_mock, patch("src.main.fetch_all") as fetch_mock, patch(
            "src.main.ping_heartbeat"
        ) as heartbeat_mock, patch(
            "sys.argv",
            [
                "signal",
                "--deliver-release",
                "--release-scope",
                "proof",
                "--release-date",
                "2026-09-07",
                "--force-type",
                "daily",
                "--as-of",
                "2026-09-07T07:05:00+10:00",
            ],
        ):
            result = main()

        self.assertEqual(0, result)
        fetch_mock.assert_not_called()
        heartbeat_mock.assert_called_once()
        self.assertEqual("proof", deliver_mock.call_args.kwargs["release_scope"])

    def test_registry_production_preparation_revalidates_audience_without_delivery(self) -> None:
        plan = _ai_adoption_majority_plan()
        patches = self._common_patches()
        frozen = SimpleNamespace(
            id="registry-production-0048",
            edition_number=48,
            release_scope="production",
            html_sha256="e" * 64,
            audience_count=4,
        )
        release_env = {
            "RENDER": "true",
            "RENDER_GIT_BRANCH": "master",
            "RENDER_GIT_COMMIT": "abcdef1234567890abcdef1234567890abcdef12",
            "RENDER_SERVICE_ID": "crn-d8ouk0bsq97s73fgc36g",
            "SIGNAL_EXPECTED_DAILY_RENDERER": "enhanced-v4-focus-numbers",
            "SIGNAL_EXPECTED_GIT_BRANCH": "master",
            "SIGNAL_EXPECTED_GIT_COMMIT": "abcdef1234567890abcdef1234567890abcdef12",
            "SIGNAL_EXPECTED_RENDER_SERVICE_ID": "crn-d8ouk0bsq97s73fgc36g",
            "SIGNAL_REGISTRY_REQUIRED": "1",
            "SIGNAL_PRODUCTION_PREFLIGHT_ENABLED": "1",
            "SIGNAL_APPROVED_EDITORIAL_REVISION": "ai-adoption-v1",
            "SIGNAL_ALIVE_MOMENT_PATH": "data/alive_moments/{date}.json",
        }
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, release_env, clear=False))
            entered = [stack.enter_context(item) for item in patches]
            fetch_subscribers_mock = entered[0]
            send_mock = entered[6]
            image_asset_mock = entered[7]
            stack.enter_context(
                patch("src.main.scored_items_to_evidence", return_value=_focus_evidence())
            )
            stack.enter_context(
                patch("src.main.generate_judgement_plan", return_value=plan)
            )
            stack.enter_context(
                patch(
                    "src.main.load_signal_memory",
                    return_value={"version": 1, "positions": [], "events": []},
                )
            )
            stack.enter_context(patch("src.main.load_alive_history", return_value=[]))
            stack.enter_context(patch("src.main.ReleaseRegistry.from_env", return_value=object()))
            stack.enter_context(
                patch(
                    "src.main.check_registry_preflight_identity",
                    return_value=SimpleNamespace(
                        passed=True,
                        severity="info",
                        check_name="Release Identity",
                        message="approved test release",
                    ),
                )
            )
            prepare_mock = stack.enter_context(
                patch("src.main.prepare_registry_release", return_value=frozen)
            )
            stack.enter_context(
                patch(
                    "sys.argv",
                    [
                        "signal",
                        "--prepare-release",
                        "--release-scope",
                        "production",
                        "--enhanced",
                        "--next-issue-date",
                        "--as-of",
                        "2026-09-06T18:00:00+10:00",
                    ],
                )
            )
            with redirect_stdout(io.StringIO()):
                result = main()

        self.assertEqual(0, result)
        self.assertEqual(2, fetch_subscribers_mock.call_count)
        send_mock.assert_not_called()
        image_asset_mock.assert_called_once()
        kwargs = prepare_mock.call_args.kwargs
        self.assertEqual("production", kwargs["release_scope"])
        self.assertEqual(4, len(kwargs["recipients"]))
        self.assertEqual(6, kwargs["issue_time"].hour)
        self.assertEqual(6, kwargs["delivery_time"].hour)
        self.assertEqual(0, kwargs["delivery_time"].minute)
        self.assertEqual("2026-09-07", kwargs["issue_time"].date().isoformat())

    def test_production_delivery_disabled_before_registry_claim(self) -> None:
        with patch.dict(
            os.environ,
            {"SIGNAL_PRODUCTION_DELIVERY_ENABLED": "0"},
            clear=False,
        ), patch("src.main.ReleaseRegistry.from_env") as registry_mock, patch(
            "src.main.deliver_registry_release"
        ) as deliver_mock, patch("src.main.send_alert") as alert_mock, patch(
            "sys.argv",
            [
                "signal",
                "--deliver-release",
                "--release-scope",
                "production",
                "--force-type",
                "daily",
            ],
        ):
            result = main()
        self.assertEqual(1, result)
        registry_mock.assert_not_called()
        deliver_mock.assert_not_called()
        alert_mock.assert_called_once()

    def test_production_preflight_disabled_before_subscriber_fetch(self) -> None:
        with patch.dict(
            os.environ,
            {"SIGNAL_PRODUCTION_PREFLIGHT_ENABLED": "0"},
            clear=False,
        ), patch("src.main.fetch_subscribers") as fetch_mock, patch(
            "src.main.send_alert"
        ) as alert_mock, patch(
            "sys.argv",
            [
                "signal",
                "--prepare-release",
                "--release-scope",
                "production",
                "--enhanced",
                "--next-issue-date",
                "--force-type",
                "daily",
            ],
        ):
            result = main()
        self.assertEqual(1, result)
        fetch_mock.assert_not_called()
        alert_mock.assert_called_once()

    def test_registry_required_blocks_legacy_direct_send_before_audience_fetch(self) -> None:
        with patch.dict(
            os.environ, {"SIGNAL_REGISTRY_REQUIRED": "1"}, clear=False
        ), patch("src.main.fetch_subscribers") as fetch_mock, patch(
            "src.main.send_brief"
        ) as send_mock, patch("src.main.send_alert") as alert_mock, patch(
            "sys.argv", ["signal", "--send"]
        ):
            result = main()

        self.assertEqual(1, result)
        fetch_mock.assert_not_called()
        send_mock.assert_not_called()
        alert_mock.assert_called_once()

    def test_all_provider_failures_return_delivery_error_without_memory_write(self) -> None:
        result, send_mock, save_memory_mock, receipt_mock = self._run_locked_send(
            [False, False, False, False]
        )
        self.assertEqual(result, 2)
        self.assertEqual(send_mock.call_count, 4)
        save_memory_mock.assert_not_called()
        receipt_mock.assert_called_once()

    def test_partial_delivery_returns_error_and_records_delivered_memory(self) -> None:
        result, send_mock, save_memory_mock, receipt_mock = self._run_locked_send(
            ["message-id-1", False, "message-id-3", False]
        )
        self.assertEqual(result, 2)
        self.assertEqual(send_mock.call_count, 4)
        save_memory_mock.assert_called_once()
        receipt_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
