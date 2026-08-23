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

        self.assertEqual(action, "replaced")
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

        self.assertEqual(action, "injected")
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

        self.assertEqual(action, "unchanged")
        self.assertEqual(corrected, html)


if __name__ == "__main__":
    unittest.main()
