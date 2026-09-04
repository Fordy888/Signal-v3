import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from src.header_metadata import ensure_header_metadata
from src.synthesis import synthesise


class HeaderMetadataTests(unittest.TestCase):
    def test_replaces_wrong_date_line(self):
        html = """
        <table>
          <tr><td><p>DTL SIGNAL</p></td></tr>
          <tr><td><p>Executive Business Intelligence</p></td></tr>
          <tr><td><p>Sunday 23 August 2026 | 06:00 AEST</p></td></tr>
        </table>
        """

        corrected, action = ensure_header_metadata(
            html, "Monday", "24 August 2026", "06:06"
        )

        self.assertEqual(action, "header_replaced")
        self.assertIn("Monday 24 August 2026 | 06:06 AEST", corrected)
        self.assertNotIn("Sunday 23 August 2026", corrected)

    def test_injects_date_when_model_omits_row(self):
        html = """
        <table>
          <tr><td><p>DTL SIGNAL</p></td></tr>
          <tr><td><p>Executive Business Intelligence</p></td></tr>
          <tr><td><p>Today's Signal</p></td></tr>
        </table>
        """

        corrected, action = ensure_header_metadata(
            html, "Monday", "24 August 2026", "06:06"
        )

        self.assertEqual(action, "header_injected")
        self.assertIn("Monday 24 August 2026 | 06:06 AEST", corrected)
        self.assertLess(
            corrected.index("Monday 24 August 2026"),
            corrected.index("Today's Signal"),
        )

    def test_leaves_correct_date_unchanged(self):
        html = "<table><tr><td>Monday 24 August 2026 | 06:06 AEST</td></tr></table>"

        corrected, action = ensure_header_metadata(
            html, "Monday", "24 August 2026", "06:06"
        )

        self.assertEqual(action, "header_unchanged")
        self.assertEqual(corrected, html)

    def test_replaces_mismatched_footer_stamp(self):
        html = """
        <table>
          <tr><td>Monday 24 August 2026 | 06:06 AEST</td></tr>
          <tr><td>PF::SIGNAL-0038 // 25.08.2026 // 06:06 AEST</td></tr>
        </table>
        """

        corrected, action = ensure_header_metadata(
            html,
            "Monday",
            "24 August 2026",
            "06:06",
            edition_number=38,
            date_compact="24.08.2026",
        )

        self.assertIn("footer_replaced", action)
        self.assertIn("PF::SIGNAL-0038 // 24.08.2026 // 06:06 AEST", corrected)
        self.assertNotIn("PF::SIGNAL-0038 // 25.08.2026", corrected)

    def test_weekly_wrap_uses_governed_runtime_for_prompt_header_and_footer(self):
        wrong_clock_html = """
        <table>
          <tr><td>Friday 04 September 2026 | 17:29 AEST</td></tr>
          <tr><td>THE PATTERN</td></tr>
          <tr><td>EXECUTIVE TAKEAWAY</td></tr>
          <tr><td>PF::SIGNAL-047 // 04.09.2026 // 17:29 AEST</td></tr>
        </table>
        """
        response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text=wrong_clock_html)],
            stop_reason="end_turn",
        )
        client = MagicMock()
        client.messages.create.return_value = response
        governed_runtime = datetime(
            2026,
            9,
            5,
            6,
            0,
            tzinfo=ZoneInfo("Australia/Brisbane"),
        )

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            context_path = root / "context.yaml"
            prompt_path = root / "weekly.md"
            context_path.write_text("publication: test\n")
            prompt_path.write_text(
                "{DATE}|{TIMESTAMP}|{DAY_NAME}|{DATE_FORMATTED}|"
                "{DATE_COMPACT}|{TIME}|{EDITION_NUMBER}|{EDITION_STAMP}|"
                "{CONTEXT_MODEL}|{SCORED_ITEMS}"
            )
            with patch.dict(
                "os.environ",
                {"ANTHROPIC_API_KEY": "test-key"},
                clear=False,
            ), patch("src.synthesis.Anthropic", return_value=client):
                html = synthesise(
                    scored_items=[],
                    context_path=str(context_path),
                    synthesis_prompt_path=str(prompt_path),
                    edition_number=47,
                    edition_type="weekly_wrap",
                    generated_at=governed_runtime,
                )

        prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Saturday 05 September 2026", prompt)
        self.assertIn("2026-09-05 06:00 AEST", prompt)
        self.assertIn("Saturday 05 September 2026 | 06:00 AEST", html)
        self.assertIn("PF::SIGNAL-0047 // 05.09.2026 // 06:00 AEST", html)
        self.assertNotIn("Friday 04 September 2026", html)


if __name__ == "__main__":
    unittest.main()
