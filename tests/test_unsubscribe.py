"""Every outbound edition must carry a functional unsubscribe.

Edition 0046 shipped to 33 subscribers with no unsubscribe facility at all:
fetch_unsubscribe_token existed but was never called, and delivery set no
List-Unsubscribe header. These pin the fix.

The load-bearing rule is the LAST class: there is no input — no token, no
WEBSITE_BASE_URL, neither — that produces an edition without an unsubscribe.
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

from src.unsubscribe import (
    apply_unsubscribe,
    inject_unsubscribe,
    list_unsubscribe_headers,
    unsubscribe_target,
)

EDITION = "<html><body><table><tr><td>DTL SIGNAL</td></tr></table></body></html>"


class DocumentedTokenPath(unittest.TestCase):
    """docs/subscriber-sync-spec.md: {WEBSITE_BASE_URL}/unsubscribe?token={token}"""

    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"WEBSITE_BASE_URL": "https://dtlc.ai"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_uses_the_documented_url_format(self):
        href, kind = unsubscribe_target("reader@example.com", "tok-123")
        self.assertEqual(href, "https://dtlc.ai/unsubscribe?token=tok-123")
        self.assertEqual(kind, "link")

    def test_trailing_slash_on_base_url_does_not_double(self):
        with mock.patch.dict(os.environ, {"WEBSITE_BASE_URL": "https://dtlc.ai/"}):
            href, _ = unsubscribe_target("reader@example.com", "tok-123")
        self.assertEqual(href, "https://dtlc.ai/unsubscribe?token=tok-123")

    def test_token_is_url_encoded(self):
        href, _ = unsubscribe_target("reader@example.com", "a b/c&d")
        self.assertNotIn(" ", href)
        self.assertIn("a%20b%2Fc%26d", href)

    def test_link_wording_is_a_plain_instruction(self):
        html, _ = apply_unsubscribe(EDITION, "reader@example.com", "tok-123")
        self.assertIn("Unsubscribe", html)
        self.assertIn("you subscribed at dtlc.ai", html)


class MailtoFallback(unittest.TestCase):
    """A failed token must fall back, never omit. This inverts the spec's rule."""

    def test_no_token_falls_back_to_mailto(self):
        with mock.patch.dict(os.environ, {"WEBSITE_BASE_URL": "https://dtlc.ai"}):
            href, kind = unsubscribe_target("reader@example.com", None)
        self.assertTrue(href.startswith("mailto:"))
        self.assertEqual(kind, "mailto")

    def test_missing_base_url_falls_back_to_mailto(self):
        with mock.patch.dict(os.environ, {"WEBSITE_BASE_URL": ""}):
            href, kind = unsubscribe_target("reader@example.com", "tok-123")
        self.assertTrue(href.startswith("mailto:"))
        self.assertEqual(kind, "mailto")

    def test_mailto_identifies_the_address_to_remove(self):
        with mock.patch.dict(os.environ, {"WEBSITE_BASE_URL": ""}):
            href, _ = unsubscribe_target("reader@example.com", None)
        self.assertIn("UNSUBSCRIBE", href)
        self.assertIn("reader%40example.com", href.replace("%40", "%40"))

    def test_fallback_recipient_is_configurable(self):
        with mock.patch.dict(os.environ, {"WEBSITE_BASE_URL": "",
                                          "SIGNAL_UNSUBSCRIBE_EMAIL": "stop@dtlc.ai"}):
            href, _ = unsubscribe_target("reader@example.com", None)
        self.assertTrue(href.startswith("mailto:stop@dtlc.ai"))

    def test_fallback_copy_tells_the_reader_what_will_happen(self):
        with mock.patch.dict(os.environ, {"WEBSITE_BASE_URL": ""}):
            html, _ = apply_unsubscribe(EDITION, "reader@example.com", None)
        self.assertIn("email us and we will remove you", html)


class ListUnsubscribeHeader(unittest.TestCase):
    def test_header_wraps_the_href_in_angle_brackets(self):
        self.assertEqual(
            list_unsubscribe_headers("https://dtlc.ai/unsubscribe?token=t"),
            {"List-Unsubscribe": "<https://dtlc.ai/unsubscribe?token=t>"},
        )

    def test_header_matches_the_link_path(self):
        with mock.patch.dict(os.environ, {"WEBSITE_BASE_URL": "https://dtlc.ai"}):
            _, headers = apply_unsubscribe(EDITION, "reader@example.com", "tok-123")
        self.assertIn("https://dtlc.ai/unsubscribe?token=tok-123",
                      headers["List-Unsubscribe"])

    def test_header_matches_the_mailto_path(self):
        with mock.patch.dict(os.environ, {"WEBSITE_BASE_URL": ""}):
            _, headers = apply_unsubscribe(EDITION, "reader@example.com", None)
        self.assertIn("mailto:", headers["List-Unsubscribe"])


class InjectionPreservesTheEdition(unittest.TestCase):
    """No redesign: the block is appended, nothing existing is altered."""

    def test_original_content_survives_untouched(self):
        html = inject_unsubscribe(EDITION, "https://x/u?token=t", "link")
        self.assertIn("DTL SIGNAL", html)
        self.assertIn("<table><tr><td>DTL SIGNAL</td></tr></table>", html)

    def test_block_lands_inside_the_body(self):
        html = inject_unsubscribe(EDITION, "https://x/u?token=t", "link")
        self.assertLess(html.index("Unsubscribe"), html.lower().index("</body>"))

    def test_fragment_without_body_still_gets_the_block(self):
        html = inject_unsubscribe("<table><tr><td>x</td></tr></table>",
                                  "https://x/u?token=t", "link")
        self.assertIn("Unsubscribe", html)

    def test_href_is_attribute_escaped(self):
        html = inject_unsubscribe(EDITION, 'https://x/u?token=a"b', "link")
        self.assertNotIn('token=a"b"', html)
        self.assertIn("&quot;", html)


class NoEditionCanEscapeWithoutUnsubscribe(unittest.TestCase):
    """The rule that matters. No input produces an edition without one."""

    CASES = [
        ("token + base url", {"WEBSITE_BASE_URL": "https://dtlc.ai"}, "tok-123"),
        ("token, no base url", {"WEBSITE_BASE_URL": ""}, "tok-123"),
        ("base url, no token", {"WEBSITE_BASE_URL": "https://dtlc.ai"}, None),
        ("neither", {"WEBSITE_BASE_URL": ""}, None),
        ("empty-string token", {"WEBSITE_BASE_URL": "https://dtlc.ai"}, ""),
        ("whitespace base url", {"WEBSITE_BASE_URL": "   "}, "tok-123"),
    ]

    def test_every_combination_yields_a_functional_unsubscribe(self):
        for label, env, token in self.CASES:
            with self.subTest(case=label):
                with mock.patch.dict(os.environ, env):
                    html, headers = apply_unsubscribe(EDITION, "reader@example.com", token)
                self.assertIn("Unsubscribe", html, f"{label}: no instruction in body")
                self.assertRegex(html, r'href="(https?://|mailto:)',
                                 f"{label}: no actionable href")
                self.assertIn("List-Unsubscribe", headers, f"{label}: no header")
                self.assertRegex(headers["List-Unsubscribe"], r"^<(https?://|mailto:)",
                                 f"{label}: header not actionable")

    def test_no_case_requires_a_login_or_account(self):
        for label, env, token in self.CASES:
            with self.subTest(case=label):
                with mock.patch.dict(os.environ, env):
                    html, _ = apply_unsubscribe(EDITION, "reader@example.com", token)
                for word in ("sign in", "log in", "password", "create an account"):
                    self.assertNotIn(word, html.lower(), f"{label}: {word} required")


class SendLoopCarriesItThrough(unittest.TestCase):
    """The wiring, not just the helper: delivery must receive the header."""

    def test_delivery_accepts_and_forwards_headers(self):
        import inspect
        from src.delivery import send_brief
        self.assertIn("headers", inspect.signature(send_brief).parameters)

    def test_main_calls_apply_unsubscribe_per_recipient(self):
        from pathlib import Path
        src = Path(__file__).resolve().parents[1] / "src" / "main.py"
        body = src.read_text()
        self.assertIn("apply_unsubscribe(", body)
        self.assertIn("fetch_unsubscribe_token(email)", body)
        self.assertIn("headers=unsubscribe_headers", body)


if __name__ == "__main__":
    unittest.main()
