import unittest

from src.header_metadata import ensure_header_metadata


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


if __name__ == "__main__":
    unittest.main()
