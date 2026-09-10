"""Freeze + exactly-once: one payload, bound approval, no double sends."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src import freeze as freeze_store

HTML = "<table><tr><td>Edition 0051</td></tr></table>"
OTHER_HTML = "<table><tr><td>Edition 0051 (re-rendered)</td></tr></table>"
SUBJECT = "DTL Signal — Edition 0051"
PAUL = "paul.ford@gmail.com"


class FreezeTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.conn = freeze_store.connect(self.root, db_path="freeze.sqlite3")

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()


class Freezing(FreezeTestCase):
    def test_digest_is_sha256_over_exact_bytes(self):
        import hashlib

        self.assertEqual(
            freeze_store.digest(HTML.encode("utf-8")),
            hashlib.sha256(HTML.encode("utf-8")).hexdigest(),
        )

    def test_freeze_stores_payload_and_hash(self):
        frozen = freeze_store.freeze_edition(self.conn, 51, SUBJECT, HTML)
        self.assertEqual(frozen.edition_number, 51)
        self.assertEqual(frozen.html, HTML)
        self.assertEqual(frozen.sha256, freeze_store.digest(HTML.encode("utf-8")))

    def test_refreezing_identical_html_is_idempotent(self):
        first = freeze_store.freeze_edition(self.conn, 51, SUBJECT, HTML)
        second = freeze_store.freeze_edition(self.conn, 51, SUBJECT, HTML)
        self.assertEqual(first.sha256, second.sha256)
        self.assertEqual(first.frozen_at, second.frozen_at)

    def test_rerendering_different_html_is_refused(self):
        freeze_store.freeze_edition(self.conn, 51, SUBJECT, HTML)
        with self.assertRaises(freeze_store.FreezeConflict):
            freeze_store.freeze_edition(self.conn, 51, SUBJECT, OTHER_HTML)

    def test_loading_detects_tampered_bytes(self):
        freeze_store.freeze_edition(self.conn, 51, SUBJECT, HTML)
        self.conn.execute(
            "UPDATE frozen_edition SET payload = ? WHERE edition_number = 51",
            (b"<table>tampered</table>",),
        )
        self.conn.commit()
        with self.assertRaises(freeze_store.PayloadCorrupt):
            freeze_store.load_frozen(self.conn, 51)


class Approval(FreezeTestCase):
    def test_send_without_approval_is_refused(self):
        freeze_store.freeze_edition(self.conn, 51, SUBJECT, HTML)
        with self.assertRaises(freeze_store.NotApproved):
            freeze_store.load_for_send(self.conn, 51)

    def test_approval_binds_to_the_payload_hash(self):
        frozen = freeze_store.freeze_edition(self.conn, 51, SUBJECT, HTML)
        freeze_store.approve(self.conn, frozen.sha256, PAUL)
        loaded = freeze_store.load_for_send(self.conn, 51)
        self.assertEqual(loaded.html, HTML)

    def test_approval_does_not_carry_to_a_different_payload(self):
        frozen = freeze_store.freeze_edition(self.conn, 51, SUBJECT, HTML)
        freeze_store.approve(self.conn, frozen.sha256, PAUL)
        # A different payload (edition 52) is not covered by 51's approval.
        freeze_store.freeze_edition(self.conn, 52, SUBJECT, OTHER_HTML)
        with self.assertRaises(freeze_store.NotApproved):
            freeze_store.load_for_send(self.conn, 52)

    def test_sending_an_unfrozen_edition_is_refused(self):
        with self.assertRaises(freeze_store.FreezeError):
            freeze_store.load_for_send(self.conn, 99)

    def test_proof_can_load_without_approval(self):
        freeze_store.freeze_edition(self.conn, 51, SUBJECT, HTML)
        loaded = freeze_store.load_for_send(self.conn, 51, require_approval=False)
        self.assertEqual(loaded.html, HTML)


class ExactlyOnce(FreezeTestCase):
    def setUp(self):
        super().setUp()
        self.frozen = freeze_store.freeze_edition(self.conn, 51, SUBJECT, HTML)

    def test_first_claim_succeeds(self):
        freeze_store.claim_send(self.conn, 51, PAUL, self.frozen.sha256)
        self.assertTrue(freeze_store.already_sent(self.conn, 51, PAUL))

    def test_second_claim_to_same_recipient_is_refused(self):
        freeze_store.claim_send(self.conn, 51, PAUL, self.frozen.sha256)
        with self.assertRaises(freeze_store.AlreadySent):
            freeze_store.claim_send(self.conn, 51, PAUL, self.frozen.sha256)

    def test_claim_is_case_and_whitespace_insensitive(self):
        freeze_store.claim_send(self.conn, 51, PAUL, self.frozen.sha256)
        with self.assertRaises(freeze_store.AlreadySent):
            freeze_store.claim_send(self.conn, 51, f"  {PAUL.upper()} ", self.frozen.sha256)

    def test_other_recipients_are_unaffected(self):
        freeze_store.claim_send(self.conn, 51, PAUL, self.frozen.sha256)
        freeze_store.claim_send(self.conn, 51, "someone@example.com", self.frozen.sha256)
        self.assertTrue(freeze_store.already_sent(self.conn, 51, "someone@example.com"))

    def test_next_edition_to_same_recipient_is_allowed(self):
        freeze_store.claim_send(self.conn, 51, PAUL, self.frozen.sha256)
        next_frozen = freeze_store.freeze_edition(self.conn, 52, SUBJECT, OTHER_HTML)
        freeze_store.claim_send(self.conn, 52, PAUL, next_frozen.sha256)
        self.assertTrue(freeze_store.already_sent(self.conn, 52, PAUL))

    def test_released_claim_can_be_retried(self):
        freeze_store.claim_send(self.conn, 51, PAUL, self.frozen.sha256)
        freeze_store.release_send(self.conn, 51, PAUL)
        self.assertFalse(freeze_store.already_sent(self.conn, 51, PAUL))
        freeze_store.claim_send(self.conn, 51, PAUL, self.frozen.sha256)  # must not raise


class ProofToSendContinuity(FreezeTestCase):
    def test_bytes_sent_are_the_bytes_proofed(self):
        """The 0049 failure mode: content drifting between proof and send."""
        frozen_at_proof = freeze_store.freeze_edition(self.conn, 51, SUBJECT, HTML)
        proof_bytes = frozen_at_proof.payload

        freeze_store.approve(self.conn, frozen_at_proof.sha256, PAUL)

        # A later run reloads for delivery — no re-render happens.
        frozen_at_send = freeze_store.load_for_send(self.conn, 51)
        self.assertEqual(frozen_at_send.payload, proof_bytes)
        self.assertEqual(frozen_at_send.sha256, frozen_at_proof.sha256)


if __name__ == "__main__":
    unittest.main()
