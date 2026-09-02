from __future__ import annotations

import hashlib
import json
import unittest
from datetime import date
from urllib.parse import unquote
from unittest.mock import Mock, patch

from src.edition_counter import edition_for_date
from src.share_block import (
    SHARE_MARKER,
    SUBSCRIBER_PLACEHOLDER,
    build_share_block,
    inject_share_block,
    personalise_share_for_subscriber,
)
from src.signal_gauge import GAUGE_BLOCK_MARKER, generate_gauge_html, inject_gauge_into_html
from src.signal_memory import (
    apply_alive_moment_update,
    alive_history_from_memory,
    embed_delivery_memory,
    extract_delivery_memory,
    recover_signal_memory_from_resend,
)
from src.locked_edition import LockedEditionError, render_locked_edition
from src.email_html_qa import validate_email_html


class ProductionParityTests(unittest.TestCase):
    def test_weekday_calendar_numbering_and_weekend_rollover(self) -> None:
        self.assertEqual(edition_for_date(date(2026, 7, 24)), 17)
        self.assertEqual(edition_for_date(date(2026, 8, 28)), 42)
        self.assertEqual(edition_for_date(date(2026, 8, 29)), 42)
        self.assertEqual(edition_for_date(date(2026, 8, 30)), 42)
        self.assertEqual(edition_for_date(date(2026, 8, 31)), 43)

    def test_gauge_label_is_optional(self) -> None:
        labelled = generate_gauge_html(42, 1, show_label=True)
        unlabelled = generate_gauge_html(42, 2, show_label=False)
        self.assertEqual(labelled.count("RATE THIS SIGNAL"), 1)
        self.assertNotIn("RATE THIS SIGNAL", unlabelled)

    def test_gauge_injection_labels_only_first_item_and_accepts_opportunity(self) -> None:
        detail = "Evidence and implication remain inside this realistic story block. " * 4
        html = f"""
        <table>
        <tr><td><span>ACT</span><p>{detail}</p><p>Signal: First</p></td></tr>
        <tr><td style="padding: 16px 40px;"><table><tr><td style="border-top: 1px solid #e8e8e8;"></td></tr></table></td></tr>
        <tr><td><span>OPPORTUNITY</span><p>{detail}</p><p>Signal: Second</p></td></tr>
        <tr><td style="padding: 16px 40px;"><table><tr><td style="border-top: 1px solid #e8e8e8;"></td></tr></table></td></tr>
        </table>
        """
        rendered = inject_gauge_into_html(html, [{}, {}], 42)
        self.assertEqual(rendered.count("RATE THIS SIGNAL"), 1)
        self.assertEqual(rendered.count(GAUGE_BLOCK_MARKER), 2)

    def test_share_block_is_tracked_idempotent_and_personalised(self) -> None:
        block = build_share_block(42)
        decoded_block = unquote(block)
        self.assertIn("utm_campaign=edition_0042", decoded_block)
        self.assertIn("utm_content=share_email", decoded_block)
        self.assertIn("utm_content=share_linkedin", decoded_block)
        self.assertIn("utm_content=forwarded_subscribe", decoded_block)
        self.assertIn(SUBSCRIBER_PLACEHOLDER, block)

        html = f"<table><tr><td>Signal learns</td></tr></table>"
        injected = inject_share_block(html, 42)
        self.assertEqual(injected.count(SHARE_MARKER), 1)
        self.assertEqual(inject_share_block(injected, 42), injected)
        self.assertLess(injected.index(SHARE_MARKER), injected.index("Signal learns"))

        expected = hashlib.sha256(b"paul.ford@gmail.com").hexdigest()[:12]
        personalised = personalise_share_for_subscriber(injected, expected)
        self.assertIn(expected, personalised)
        self.assertNotIn("SUBSCRIBER_HASH", personalised)

    def test_delivery_memory_capsule_round_trips_without_visible_markup(self) -> None:
        memory = {"version": 1, "positions": [{"position_id": "p1"}], "events": []}
        rendered = embed_delivery_memory("<table></table>", memory)
        self.assertTrue(rendered.startswith("<table></table><!-- dtl-signal-memory:"))
        self.assertEqual(extract_delivery_memory(rendered), memory)

    def test_delivery_memory_carries_image_identity(self) -> None:
        memory = {"version": 1, "positions": [], "events": []}
        moment = {
            "id": "image-1",
            "date": "2026-09-01",
            "location": "Sydney",
            "country": "Australia",
            "category": "human_life",
            "species": "",
            "image_url": "https://images.example.com/one.jpg",
            "image_original_url": "https://original.example.com/one.jpg",
            "image_source_url": "https://source.example.com/one",
            "photographer": "Example Photographer",
        }
        updated = apply_alive_moment_update(
            memory, moment, edition_number=44, delivered_at="2026-09-01T06:00:00+10:00"
        )
        self.assertEqual(len(alive_history_from_memory(updated)), 1)
        self.assertEqual(updated["alive_moments"][0]["image_source_url"], moment["image_source_url"])

    @patch("src.signal_memory.requests.get")
    def test_resend_memory_recovery_excludes_proofs_and_requires_live_tags(self, get: Mock) -> None:
        memory = {"version": 1, "positions": [{"position_id": "live"}], "events": []}
        list_response = Mock()
        list_response.raise_for_status.return_value = None
        list_response.json.return_value = {
            "data": [
                {
                    "id": "proof-id",
                    "subject": "[PROOF] DTL Signal | Edition 0042 | Final Format",
                    "last_event": "opened",
                },
                {
                    "id": "live-id",
                    "subject": "DTL Signal | Edition 0042 | Friday 28 August 2026",
                    "last_event": "delivered",
                },
            ]
        }
        email_response = Mock()
        email_response.raise_for_status.return_value = None
        email_response.json.return_value = {
            "id": "live-id",
            "last_event": "delivered",
            "tags": [
                {"name": "message_type", "value": "signal"},
                {"name": "format", "value": "enhanced-v4-focus-numbers"},
                {"name": "delivery_mode", "value": "production"},
            ],
            "html": embed_delivery_memory(
                '<table><tr><td>REMEMBER THE WORLD'
                '<img src="https://images.example.com/whale.jpg" alt="Whale and calf">'
                '<a href="https://source.example.com/whale">image source</a>'
                '</td></tr></table>',
                memory,
            ),
        }
        get.side_effect = [list_response, email_response]

        recovered = recover_signal_memory_from_resend("secret")
        self.assertEqual(recovered["positions"], memory["positions"])
        self.assertEqual(len(recovered["alive_moments"]), 1)
        self.assertEqual(
            recovered["alive_moments"][0]["image_source_url"],
            "https://source.example.com/whale",
        )
        self.assertEqual(get.call_count, 2)
        self.assertTrue(get.call_args_list[1].args[0].endswith("/live-id"))

    def test_locked_edition_0042_reproduces_the_approved_html(self) -> None:
        root = __import__("pathlib").Path(__file__).resolve().parents[1]
        html, plan, evidence, joke, moment = render_locked_edition(root, 42)
        self.assertIn("Edition 0042", html)
        self.assertIn("THINK.</span>", html)
        self.assertIn("YOUR SIGNAL AT A GLANCE", html)
        self.assertIn("REMEMBER THE WORLD", html)
        self.assertIn("DAD JOKE OF THE DAY", html)
        self.assertEqual(plan["one_thing"]["statement"], "The AI divide is no longer adoption. It is economic control.")
        self.assertEqual(len(evidence), 6)
        self.assertIsNotNone(joke)
        self.assertEqual(moment["id"], "REMEMBER-0042-MOOREA-HUMPBACK")

    def test_missing_locked_edition_is_rejected(self) -> None:
        root = __import__("pathlib").Path(__file__).resolve().parents[1]
        with self.assertRaises(LockedEditionError):
            render_locked_edition(root, 43)

    def test_locked_edition_is_email_client_safe(self) -> None:
        root = __import__("pathlib").Path(__file__).resolve().parents[1]
        html, *_ = render_locked_edition(root, 42)
        passed, issues = validate_email_html(html)
        self.assertTrue(passed, issues)

    def test_email_client_gate_rejects_unsafe_or_unresolved_markup(self) -> None:
        passed, issues = validate_email_html(
            '<table width="100%"><script></script><img src="http://bad/image.jpg"></table>{{NAME}}'
        )
        self.assertFalse(passed)
        self.assertTrue(any("<script" in issue for issue in issues))
        self.assertTrue(any("Unresolved" in issue for issue in issues))
        self.assertTrue(any("not HTTPS" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
