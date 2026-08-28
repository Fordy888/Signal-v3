from __future__ import annotations

import io
import json
import logging
import os
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from datetime import datetime
from pathlib import Path
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
                "ENABLE_GAUGE": "static",
                "SIGNAL_RELEASE_PROFILE": "v4.0",
                "SIGNAL_V4_LAUNCH_DATE": "2026-08-31",
                "SIGNAL_EXPECTED_DAILY_RENDERER": "enhanced-v4",
                "SIGNAL_EXPECTED_GIT_BRANCH": "master",
                "SIGNAL_EXPECTED_RENDER_SERVICE_ID": "crn-d8ouk0bsq97s73fgc36g",
                "SIGNAL_ALIVE_MOMENT_PATH": "data/fixtures/alive_moment_0043.json",
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
        )

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

    def test_monday_edition_0043_dynamic_v4_full_dry_run_never_delivers(self) -> None:
        output = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
        output.close()
        plan = json.loads((ROOT / "data" / "edition0042-enhanced-plan.json").read_text())
        evidence = json.loads(
            (ROOT / "data" / "fixtures" / "edition0042_evidence.json").read_text()
        )
        patches = self._common_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6] as send_mock, patch(
            "src.main.scored_items_to_evidence", return_value=evidence
        ), patch(
            "src.main.generate_judgement_plan", return_value=plan
        ), patch(
            "src.main.load_signal_memory", return_value={"version": 1, "positions": [], "events": []}
        ), patch(
            "src.main.load_alive_history", return_value=[]
        ), patch(
            "sys.argv",
            [
                "signal",
                "--dry-run",
                "--enhanced",
                "--alive-moment",
                "--as-of",
                "2026-08-31T06:00:00+10:00",
                "--save-html",
                output.name,
            ],
        ), redirect_stdout(io.StringIO()):
            result = main()
        html = Path(output.name).read_text()
        Path(output.name).unlink(missing_ok=True)
        self.assertEqual(result, 0)
        send_mock.assert_not_called()
        self.assertIn("Edition 0043", html)
        self.assertIn("Monday 31 August 2026", html)
        self.assertIn("THINK.</span>", html)
        self.assertIn("DECIDE.</span>", html)
        self.assertIn("LOOK UP.</span>", html)
        self.assertIn("SMILE.</span>", html)
        self.assertIn("YOUR SIGNAL AT A GLANCE", html)
        self.assertIn("FOUNDER'S NOTE", html)
        self.assertIn("REMEMBER THE WORLD", html)
        self.assertIn("DAD JOKE OF THE DAY", html)
        self.assertIn("PF::SIGNAL-0043 // 31.08.2026 // 06:00 AEST", html)

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
        with patch("src.main.fetch_subscribers", return_value=[]), patch(
            "src.main.send_alert"
        ) as alert_mock, patch("src.main.send_brief") as send_mock, patch(
            "sys.argv", ["signal", "--send"]
        ):
            result = main()
        self.assertEqual(result, 1)
        alert_mock.assert_called_once()
        send_mock.assert_not_called()

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
