import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from src.delivery import send_brief
from src.release_registry import (
    RegistryIntegrityError,
    RegistryTransitionError,
    build_frozen_release,
    classify_delivery_window,
    recipient_idempotency_key,
    sha256_text,
    stored_release_matches,
    validate_transition,
    validate_uncertain_send_retry,
    verify_frozen_release,
)


UTC = timezone.utc


def _recipient(email: str, marker: str) -> dict:
    return {
        "email": email,
        "subscriber_id": 100 + len(marker),
        "first_name": marker,
        "unsubscribe_token": f"token-{marker}",
        "html_body": f"<!DOCTYPE html><html><body>{marker}</body></html>",
    }


def _release(*, edition_type: str = "daily"):
    scheduled_for = datetime(2026, 9, 8, 20, 0, tzinfo=UTC)
    return build_frozen_release(
        edition_number=49,
        issue_date=date(2026, 9, 9),
        edition_type=edition_type,
        release_scope="production",
        editorial_revision="ai-adoption-v1",
        renderer="enhanced-v4-focus-numbers" if edition_type == "daily" else "weekly-wrap-current",
        release_id="ai-adoption-v1-registry-0049",
        git_commit="a" * 40,
        subject="DTL Signal | Edition 0049 | Wednesday 09 September 2026",
        html_body="<!DOCTYPE html><html><body>Locked edition</body></html>",
        image_id="REMEMBER-0049" if edition_type == "daily" else None,
        image_sha256="b" * 64 if edition_type == "daily" else None,
        scheduled_for=scheduled_for,
        window_start=scheduled_for - timedelta(minutes=5),
        window_end=scheduled_for + timedelta(minutes=20),
        recipients=[
            _recipient("z@example.com", "Zed"),
            _recipient("a@example.com", "Ann"),
        ],
        metadata={"source_urls": ["https://example.com/story"]},
        registry_id="00000000-0000-4000-8000-000000000049",
    )


class ReleaseRegistryContractTests(unittest.TestCase):
    def test_complete_table_email_fragment_is_accepted_without_document_wrapper(self):
        release = build_frozen_release(
            edition_number=48,
            issue_date=date(2026, 9, 7),
            edition_type="daily",
            release_scope="proof",
            editorial_revision="ai-adoption-v1",
            renderer="enhanced-v4-focus-numbers",
            release_id="ai-adoption-v1-proof-0048",
            git_commit="a" * 40,
            subject="[PROOF] DTL Signal | Edition 0048 | Monday 07 September 2026",
            html_body="<table>" + ("Signal content " * 100) + "</table>",
            image_id="REMEMBER-0048",
            image_sha256="b" * 64,
            scheduled_for=datetime(2026, 9, 7, 7, 0, tzinfo=UTC),
            window_start=datetime(2026, 9, 7, 6, 0, tzinfo=UTC),
            window_end=datetime(2026, 9, 7, 20, 0, tzinfo=UTC),
            recipients=[_recipient("paul@example.com", "Paul")],
        )
        self.assertEqual("proof", release.release_scope)

    def test_short_table_fragment_is_rejected(self):
        with self.assertRaisesRegex(RegistryIntegrityError, "HTML is incomplete"):
            build_frozen_release(
                edition_number=48,
                issue_date=date(2026, 9, 7),
                edition_type="daily",
                release_scope="proof",
                editorial_revision="ai-adoption-v1",
                renderer="enhanced-v4-focus-numbers",
                release_id="ai-adoption-v1-proof-0048",
                git_commit="a" * 40,
                subject="[PROOF] DTL Signal | Edition 0048 | Monday 07 September 2026",
                html_body="<table><tr><td>short</td></tr></table>",
                image_id="REMEMBER-0048",
                image_sha256="b" * 64,
                scheduled_for=datetime(2026, 9, 7, 7, 0, tzinfo=UTC),
                window_start=datetime(2026, 9, 7, 6, 0, tzinfo=UTC),
                window_end=datetime(2026, 9, 7, 20, 0, tzinfo=UTC),
                recipients=[_recipient("paul@example.com", "Paul")],
            )

    def test_build_freezes_sorted_audience_and_permanent_idempotency(self):
        release = _release()
        self.assertEqual(2, release.audience_count)
        self.assertEqual(
            sorted(item.recipient_hash for item in release.recipients),
            [item.recipient_hash for item in release.recipients],
        )
        for recipient in release.recipients:
            self.assertEqual(sha256_text(recipient.html_body), recipient.html_sha256)
            self.assertEqual(
                recipient_idempotency_key(
                    edition_number=49,
                    edition_type="daily",
                    release_scope="production",
                    recipient_hash=recipient.recipient_hash,
                ),
                recipient.idempotency_key,
            )
        verify_frozen_release(release)

    def test_daily_requires_governed_image_but_weekly_wrap_does_not(self):
        with self.assertRaisesRegex(RegistryIntegrityError, "governed image"):
            build_frozen_release(
                edition_number=49,
                issue_date=date(2026, 9, 9),
                edition_type="daily",
                release_scope="production",
                editorial_revision="ai-adoption-v1",
                renderer="enhanced-v4-focus-numbers",
                release_id="release-49",
                git_commit="a" * 40,
                subject="Subject",
                html_body="<html><body>Daily</body></html>",
                image_id=None,
                image_sha256=None,
                scheduled_for=datetime(2026, 9, 8, 20, 0, tzinfo=UTC),
                window_start=datetime(2026, 9, 8, 19, 55, tzinfo=UTC),
                window_end=datetime(2026, 9, 8, 20, 20, tzinfo=UTC),
                recipients=[_recipient("a@example.com", "Ann")],
            )
        verify_frozen_release(_release(edition_type="weekly_wrap"))

    def test_checksum_and_audience_drift_fail_closed(self):
        release = _release()
        with self.assertRaisesRegex(RegistryIntegrityError, "HTML checksum mismatch"):
            verify_frozen_release(replace(release, html_body=release.html_body + "drift"))
        with self.assertRaisesRegex(RegistryIntegrityError, "audience count mismatch"):
            verify_frozen_release(replace(release, audience_count=3))
        corrupted_body = replace(release.recipients[0], html_body="<html>changed</html>")
        with self.assertRaisesRegex(RegistryIntegrityError, "audience checksum mismatch"):
            verify_frozen_release(
                replace(release, recipients=(corrupted_body,) + release.recipients[1:])
            )
        forged_checksum = replace(release.recipients[0], html_sha256="c" * 64)
        with self.assertRaisesRegex(RegistryIntegrityError, "recipient HTML checksum mismatch"):
            verify_frozen_release(
                replace(release, recipients=(forged_checksum,) + release.recipients[1:])
            )
        corrupted_name = replace(release.recipients[0], first_name="Changed")
        with self.assertRaisesRegex(RegistryIntegrityError, "audience checksum mismatch"):
            verify_frozen_release(
                replace(release, recipients=(corrupted_name,) + release.recipients[1:])
            )
        corrupted_token = replace(release.recipients[0], unsubscribe_token="changed")
        with self.assertRaisesRegex(RegistryIntegrityError, "audience checksum mismatch"):
            verify_frozen_release(
                replace(release, recipients=(corrupted_token,) + release.recipients[1:])
            )

    def test_existing_release_reuse_requires_full_immutable_identity(self):
        release = _release()
        existing = {
            "issue_date": release.issue_date,
            "edition_type": release.edition_type,
            "release_scope": release.release_scope,
            "editorial_revision": release.editorial_revision,
            "renderer": release.renderer,
            "release_id": release.release_id,
            "git_commit": release.git_commit,
            "subject": release.subject,
            "html_body": release.html_body,
            "html_sha256": release.html_sha256,
            "image_id": release.image_id,
            "image_sha256": release.image_sha256,
            "audience_sha256": release.audience_sha256,
            "audience_count": release.audience_count,
            "metadata": release.metadata,
            "scheduled_for": release.scheduled_for,
            "window_start": release.window_start,
            "window_end": release.window_end,
        }
        self.assertTrue(stored_release_matches(existing, release))
        self.assertFalse(stored_release_matches({**existing, "release_id": "drift"}, release))
        self.assertFalse(stored_release_matches({**existing, "html_body": "<html>drift</html>"}, release))

    def test_duplicate_and_invalid_recipients_are_rejected(self):
        base = _release()
        kwargs = {
            key: value
            for key, value in base.__dict__.items()
            if key not in {"id", "html_sha256", "audience_sha256", "audience_count", "recipients"}
        }
        with self.assertRaisesRegex(RegistryIntegrityError, "duplicate recipient"):
            build_frozen_release(
                **kwargs,
                recipients=[
                    _recipient("A@example.com", "A"),
                    _recipient("a@example.com", "Duplicate"),
                ],
            )

    def test_release_state_transitions_are_fail_closed(self):
        valid = [
            ("PREPARING", "LOCKED"),
            ("LOCKED", "SCHEDULED"),
            ("SCHEDULED", "DELIVERING"),
            ("DELIVERING", "DELIVERED"),
        ]
        for current, target in valid:
            validate_transition(current, target)
        with self.assertRaises(RegistryTransitionError):
            validate_transition("PREPARING", "DELIVERED")
        with self.assertRaises(RegistryTransitionError):
            validate_transition("DELIVERED", "DELIVERING")

    def test_delivery_window_classification_requires_timezone(self):
        start = datetime(2026, 9, 8, 19, 55, tzinfo=UTC)
        end = datetime(2026, 9, 8, 20, 20, tzinfo=UTC)
        self.assertEqual("EARLY", classify_delivery_window(start - timedelta(seconds=1), start, end))
        self.assertEqual("OPEN", classify_delivery_window(start, start, end))
        self.assertEqual("OPEN", classify_delivery_window(end, start, end))
        self.assertEqual("LATE", classify_delivery_window(end + timedelta(seconds=1), start, end))
        with self.assertRaisesRegex(RegistryIntegrityError, "timezone-aware"):
            classify_delivery_window(datetime(2026, 9, 8, 20, 0), start, end)

    def test_uncertain_send_retry_fails_closed_before_provider_key_expires(self):
        now = datetime(2026, 9, 8, 20, 0, tzinfo=UTC)
        validate_uncertain_send_retry(
            now=now, last_updated=now - timedelta(hours=22, minutes=59)
        )
        with self.assertRaises(RegistryTransitionError):
            validate_uncertain_send_retry(
                now=now, last_updated=now - timedelta(hours=23)
            )

    @patch("src.delivery.resend.Emails.send")
    @patch.dict("os.environ", {"RESEND_API_KEY": "test-key"}, clear=False)
    def test_resend_receives_the_registry_idempotency_key(self, mock_send):
        mock_send.return_value = {"id": "provider-49"}
        result = send_brief(
            html_body="<!DOCTYPE html><html><body>Locked</body></html>",
            recipient_email="a@example.com",
            subject_override="Locked release",
            edition_number=49,
            idempotency_key="registry-key-49",
        )
        self.assertEqual("provider-49", result)
        positional, _ = mock_send.call_args
        self.assertEqual("registry-key-49", positional[1]["idempotency_key"])


if __name__ == "__main__":
    unittest.main()
