"""The operating chain is GitHub -> Claude Code -> Render -> Resend.

Two things this pins, both material rather than stylistic:

1. No third-party file host sits in the delivery path. Every edition through
   0046 served its WE ARE ALIVE photograph from a Manus CDN URL, so the
   customer artifact depended on a platform that is not in the chain. The
   photograph is on Wikimedia Commons under CC BY-SA 4.0 and is served from
   there now, and the moment JSON ships from the repo rather than being
   dropped onto the box out of band.

   The fixtures under data/fixtures/ are deliberately exempt: they are
   byte-exact records of editions already delivered, pinned by SHA-256 in
   data/locked_editions/. Editing them would rewrite what was sent. They are
   history; this rule governs what goes out from here.

2. Subscriber delivery stays off until Paul says otherwise. render.yaml is the
   blueprint Render syncs from, so a `--send` here re-arms broadcasting to
   every subscriber even if the dashboard says otherwise.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.alive_moment import render_alive_moment

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_HOSTS = ("manuscdn.com", "manus.im", "files.manuscdn")


def _moment_files() -> list[Path]:
    """Moments that can still reach a reader. Historical fixtures are excluded."""
    live = ROOT / "data" / "alive_moment.json"
    return [live] if live.exists() else []


class NoThirdPartyHostInTheDeliveryPath(unittest.TestCase):
    def test_the_live_moment_exists(self):
        """--alive-moment reads this path; without it the edition cannot render."""
        self.assertTrue(_moment_files(), "data/alive_moment.json is missing")

    def test_no_moment_references_a_manus_host(self):
        for path in _moment_files():
            raw = path.read_text()
            for host in FORBIDDEN_HOSTS:
                self.assertNotIn(host, raw, f"{path.name} still references {host}")

    def test_every_image_is_served_from_wikimedia(self):
        for path in _moment_files():
            url = json.loads(path.read_text())["image_url"]
            self.assertTrue(
                url.startswith("https://upload.wikimedia.org/"),
                f"{path.name} serves its image from {url}",
            )

    def test_rendered_block_carries_no_third_party_host(self):
        for path in _moment_files():
            html = render_alive_moment(json.loads(path.read_text()))
            for host in FORBIDDEN_HOSTS:
                self.assertNotIn(host, html, f"{path.name} renders {host}")

    def test_the_daily_moment_ships_from_the_repo(self):
        """It must not have to be placed on the box by something outside the chain."""
        self.assertIn("!data/alive_moment.json", (ROOT / ".gitignore").read_text())


class SubscriberDeliveryStaysOff(unittest.TestCase):
    def setUp(self):
        self.blueprint = (ROOT / "render.yaml").read_text()

    def test_production_cron_does_not_broadcast(self):
        self.assertIn("python -m src.main --dry-run --enhanced --alive-moment", self.blueprint)

    def test_no_service_starts_the_pipeline_in_send_mode(self):
        self.assertNotIn("src.main --send", self.blueprint)

    def test_the_proof_sends_only_to_the_proof_recipient(self):
        self.assertIn("python -m src.main --proof --enhanced --alive-moment", self.blueprint)
        self.assertIn("PROOF_RECIPIENT_EMAIL", self.blueprint)

    def test_the_spent_subscriber_one_off_cannot_re_arm(self):
        self.assertNotIn('schedule: "0 5 14 7 *"', self.blueprint)


if __name__ == "__main__":
    unittest.main()
