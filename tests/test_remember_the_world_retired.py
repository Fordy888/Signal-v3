"""REMEMBER THE WORLD is retired as of Edition 0054.

The photograph stopped rendering once the image moved off the Manus CDN to
Wikimedia, which discourages hotlinking. Rather than chase image hosting, the
section was removed.

Two things are pinned here: the section does not render, and the retirement
also closed the failure mode that aborted the 0054 production run — a stale
SIGNAL_ALIVE_MOMENT_PATH pointing at a missing file used to raise inside
synthesis and kill the edition. Nothing reads that variable now.
"""
from __future__ import annotations

import json
import re
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.enhanced_renderer import render_enhanced_email

ROOT = Path(__file__).resolve().parents[1]
BRISBANE = ZoneInfo("Australia/Brisbane")


def _render(alive_moment):
    plan = json.loads((ROOT / "data" / "edition0042-enhanced-plan.json").read_text())
    evidence = json.loads((ROOT / "data" / "fixtures" / "edition0042_evidence.json").read_text())
    return render_enhanced_email(
        plan=plan,
        sources=evidence,
        joke={"setup": "Why did the duck get promoted?", "punchline": "Ducks in a row."},
        edition_number=54,
        generated_at=datetime(2026, 9, 15, 5, 0, tzinfo=BRISBANE),
        alive_moment=alive_moment,
    )


class SectionIsGone(unittest.TestCase):
    def test_no_remember_the_world_heading(self):
        self.assertNotIn("REMEMBER THE WORLD", _render(None))

    def test_no_image_tag_at_all(self):
        """The broken-image placeholder is what prompted the removal."""
        self.assertEqual(re.findall(r"<img[^>]*>", _render(None)), [])

    def test_no_photo_credit_or_licence_line(self):
        html = _render(None)
        for fragment in ("Wikimedia", "CC BY-SA", "Photo:", "upload.wikimedia.org"):
            self.assertNotIn(fragment, html)

    def test_the_rest_of_the_edition_is_intact(self):
        html = _render(None)
        for section in ("THE ONE THING", "FOUNDER'S NOTE", "THE EVIDENCE",
                        "EXECUTIVE READ", "COUNTER-SIGNAL", "DAD JOKE"):
            self.assertIn(section, html)

    def test_dad_joke_still_closes_the_edition(self):
        """Remember the World sat between What to Watch and the Dad Joke."""
        html = _render(None)
        self.assertLess(html.index("What to Watch"), html.index("DAD JOKE"))


class PipelineNoLongerLoadsAMoment(unittest.TestCase):
    def test_main_does_not_read_the_moment_path(self):
        body = (ROOT / "src" / "main.py").read_text()
        self.assertNotIn('os.environ.get("SIGNAL_ALIVE_MOMENT_PATH"', body)
        self.assertNotIn("load_alive_moment(", body)
        self.assertNotIn("validate_alive_moment(", body)

    def test_the_flag_is_still_accepted_so_live_commands_keep_working(self):
        """--alive-moment must not become an unrecognised-argument error."""
        body = (ROOT / "src" / "main.py").read_text()
        self.assertIn('"--alive-moment"', body)

    def test_a_stale_moment_path_can_no_longer_abort_an_edition(self):
        """The exact 0054 failure: a path to a file that does not exist."""
        import os
        from unittest import mock
        with mock.patch.dict(os.environ,
                             {"SIGNAL_ALIVE_MOMENT_PATH": "data/fixtures/alive_moment_0046.json"}):
            html = _render(None)          # must not raise
        self.assertNotIn("REMEMBER THE WORLD", html)


if __name__ == "__main__":
    unittest.main()
