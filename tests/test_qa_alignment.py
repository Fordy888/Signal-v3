import unittest
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo

from src.qa_gate import check_subject_body_alignment


class SubjectBodyAlignmentTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

