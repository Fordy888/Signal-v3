"""The one-recipient production canary.

Coach's requirement is precise: the canary must exercise the same release
gate, subscriber logic and durable-write path as a real subscriber send —
not a watered-down parallel route. These tests pin that property to the
source, because the whole value of the canary is that it is NOT special.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = (ROOT / "src" / "main.py").read_text()


def _cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "src.main", *args],
        cwd=ROOT, capture_output=True, text=True,
    )


class CanaryArgumentContract(unittest.TestCase):
    def test_canary_requires_send(self):
        r = _cli("--proof", "--canary-recipient", "paul.ford@gmail.com")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--canary-recipient requires --send", r.stderr)

    def test_canary_requires_an_email_address(self):
        r = _cli("--send", "--canary-recipient", "paul")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("must be an email address", r.stderr)

    def test_dry_run_cannot_carry_a_canary(self):
        r = _cli("--dry-run", "--canary-recipient", "paul.ford@gmail.com")
        self.assertNotEqual(r.returncode, 0)


class CanaryUsesTheRealSendPath(unittest.TestCase):
    """The narrowing must sit AFTER every send-mode control."""

    def _index(self, needle):
        i = MAIN.find(needle)
        self.assertNotEqual(i, -1, f"expected to find {needle!r} in main.py")
        return i

    def test_narrowing_happens_after_the_double_fetch_failsafe(self):
        failsafe = self._index("Source of truth verified")
        narrow = self._index("recipients = match[:1]")
        self.assertLess(
            failsafe, narrow,
            "the canary must not skip the double-fetch fail-safe",
        )

    def test_narrowing_happens_after_recipient_integrity(self):
        integrity = self._index("if not verify_recipient_integrity(recipients)")
        narrow = self._index("recipients = match[:1]")
        self.assertLess(integrity, narrow)

    def test_release_identity_is_enforced_because_mode_stays_send(self):
        # mode is derived from --proof/--send only; a canary is still "send",
        # so check_release_identity enforces rather than observes.
        self.assertIn(
            'mode = "proof" if args.proof else "send" if args.send else "dry-run"',
            MAIN,
        )
        self.assertNotIn("canary_recipient else", MAIN.split("mode =")[1][:200])

    def test_durable_writes_are_not_skipped_for_a_canary(self):
        # Bookkeeping is gated on args.send alone. A canary IS args.send, so
        # record_edition / record_joke / memory update all run.
        self.assertIn("if args.send and success_count > 0:", MAIN)
        bookkeeping = MAIN[MAIN.find("if args.send and success_count > 0:"):]
        bookkeeping = bookkeeping[:bookkeeping.find("        bookkeeping_error = str(e)")]
        self.assertNotIn("canary_recipient", bookkeeping)

    def test_subscriber_fetch_is_not_bypassed(self):
        # The canary must never construct its own recipient list the way
        # --proof does. It only filters what the live API returned.
        self.assertIn(
            'match = [r for r in recipients if r["email"].lower().strip() == wanted]',
            MAIN,
        )


class CanaryDoesNotTripTheRecipientFloor(unittest.TestCase):
    """A one-recipient canary must not be held by the <3 recipients rule.

    check_recipient_count treats fewer than 3 recipients in send mode as a
    CRITICAL failure — it is there to catch a truncated subscriber API. A
    canary narrows delivery to one address on purpose, so the gate has to
    judge the audience the API returned, not the narrowed list.
    """

    def test_qa_gate_is_given_the_fetched_audience_not_the_narrowed_list(self):
        self.assertIn(
            "recipient_count=canary_audience_size or len(recipients)", MAIN,
            "the QA gate must see the pre-narrowing audience size",
        )

    def test_the_floor_itself_is_unchanged(self):
        from src.qa_gate import check_recipient_count
        # Still critical for a genuinely truncated list.
        self.assertFalse(check_recipient_count(1, "send").passed)
        self.assertFalse(check_recipient_count(2, "send").passed)
        self.assertFalse(check_recipient_count(0, "send").passed)
        self.assertEqual(check_recipient_count(1, "send").severity, "critical")
        # And passes for a real audience.
        self.assertTrue(check_recipient_count(33, "send").passed)

    def test_non_canary_runs_are_unaffected(self):
        # canary_audience_size is None outside a canary, so the expression
        # falls through to len(recipients) exactly as before.
        self.assertIn("canary_audience_size = None", MAIN)


class CanaryContainment(unittest.TestCase):
    def test_unknown_address_aborts_rather_than_being_invented(self):
        self.assertIn("CANARY ABORT:", MAIN)
        abort = MAIN[MAIN.find("if not match:"):]
        self.assertIn("return 1", abort[:900])

    def test_exactly_one_recipient_survives(self):
        self.assertIn("recipients = match[:1]", MAIN)

    def test_receipt_cannot_read_as_a_subscriber_send(self):
        self.assertIn("This is NOT a subscriber send.", MAIN)
        self.assertIn("production-canary", MAIN)


if __name__ == "__main__":
    unittest.main()
