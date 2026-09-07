import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.delivery import DeliveryRejectedError, DeliveryUncertainError
from src.registry_pipeline import deliver_release, prepare_release
from src.release_registry import RegistryIntegrityError, RegistryProviderUncertainError


BRISBANE = ZoneInfo("Australia/Brisbane")


class FakeRegistry:
    def __init__(self):
        self.frozen = None
        self.claim_available = True
        self.failed_reason = None
        self.sent = []
        self.failed = []
        self._queue = []

    def store_locked_release(self, release):
        self.frozen = release
        self._queue = [
            {
                "id": index,
                "subscriber_id": recipient.subscriber_id,
                "recipient_email": recipient.email,
                "recipient_html_body": recipient.html_body,
                "idempotency_key": recipient.idempotency_key,
            }
            for index, recipient in enumerate(release.recipients, 1)
        ]
        return release.id

    def claim_scheduled_release(self, **_kwargs):
        if not self.claim_available or self.frozen is None:
            return None
        self.claim_available = False
        return {"id": self.frozen.id, "claim_token": "claim-1"}

    def load_frozen_release(self, _release_id):
        return self.frozen

    def claim_next_recipient(self, **_kwargs):
        return self._queue.pop(0) if self._queue else None

    def mark_recipient_sent(self, **kwargs):
        self.sent.append(kwargs)

    def mark_recipient_failed(self, **kwargs):
        self.failed.append(kwargs)

    def complete_release(self, **_kwargs):
        return "FAILED" if self.failed else "DELIVERED"

    def fail_claimed_release(self, **kwargs):
        self.failed_reason = kwargs["reason"]


def _image():
    return {"id": "REMEMBER-0048", "image_sha256": "b" * 64}


def _recipients():
    return [
        {"id": 11, "email": "a@example.com", "firstName": "Ann"},
        {"id": 12, "email": "b@example.com", "firstName": "Ben"},
    ]


class RegistryPipelineTests(unittest.TestCase):
    def setUp(self):
        self.issue_time = datetime(2026, 9, 7, 6, 0, tzinfo=BRISBANE)

    def _prepare(self, registry, *, scope="production", recipients=None):
        return prepare_release(
            registry=registry,
            edition_number=48,
            issue_time=self.issue_time,
            delivery_time=self.issue_time,
            edition_type="daily",
            release_scope=scope,
            editorial_revision="ai-adoption-v1",
            renderer="enhanced-v4-focus-numbers",
            release_id="ai-adoption-v1-registry-0048",
            git_commit="a" * 40,
            html="<!DOCTYPE html><html><body>{{SUBSCRIBER_HASH}}</body></html>",
            recipients=recipients or _recipients(),
            image=_image(),
            delivery_memory=None,
            metadata={"source_urls": ["https://example.com/ai"]},
        )

    def test_preflight_freezes_recipient_html_subject_and_scope(self):
        registry = FakeRegistry()
        release = self._prepare(
            registry,
            scope="proof",
            recipients=[{"email": "paul@example.com", "firstName": "Paul"}],
        )
        self.assertEqual("proof", release.release_scope)
        self.assertEqual(1, release.audience_count)
        self.assertIn("[PROOF] DTL Signal", release.subject)
        self.assertNotIn("{{SUBSCRIBER_HASH}}", release.recipients[0].html_body)
        self.assertIs(registry.frozen, release)

    @patch("src.registry_pipeline.report_send_results")
    @patch("src.registry_pipeline.send_brief")
    def test_delivery_sends_only_frozen_rows_with_permanent_keys(self, mock_send, mock_report):
        registry = FakeRegistry()
        release = self._prepare(registry)
        mock_send.side_effect = ["provider-a", "provider-b"]
        result = deliver_release(
            registry=registry,
            issue_time=self.issue_time,
            release_issue_date=None,
            edition_type="daily",
            release_scope="production",
            actual_git_commit="a" * 40,
        )
        self.assertEqual("DELIVERED", result["state"])
        self.assertEqual(2, result["sent"])
        self.assertEqual(2, mock_send.call_count)
        for call, recipient in zip(mock_send.call_args_list, release.recipients):
            self.assertEqual(recipient.html_body, call.kwargs["html_body"])
            self.assertEqual(recipient.idempotency_key, call.kwargs["idempotency_key"])
        mock_report.assert_called_once()

    @patch("src.registry_pipeline.send_brief")
    def test_duplicate_or_competing_trigger_sends_nothing(self, mock_send):
        registry = FakeRegistry()
        self._prepare(registry)
        registry.claim_available = False
        with self.assertRaisesRegex(RegistryIntegrityError, "no claimable"):
            deliver_release(
                registry=registry,
                issue_time=self.issue_time,
                release_issue_date=None,
                edition_type="daily",
                release_scope="production",
                actual_git_commit="a" * 40,
            )
        mock_send.assert_not_called()

    @patch("src.registry_pipeline.send_brief")
    def test_commit_mismatch_fails_before_provider_call(self, mock_send):
        registry = FakeRegistry()
        self._prepare(registry)
        with self.assertRaisesRegex(RegistryIntegrityError, "does not match deployed commit"):
            deliver_release(
                registry=registry,
                issue_time=self.issue_time,
                release_issue_date=None,
                edition_type="daily",
                release_scope="production",
                actual_git_commit="c" * 40,
            )
        self.assertIn("does not match deployed commit", registry.failed_reason)
        mock_send.assert_not_called()

    @patch("src.registry_pipeline.report_send_results")
    @patch("src.registry_pipeline.send_brief", return_value=False)
    def test_provider_failure_is_persisted_and_release_fails(self, _mock_send, mock_report):
        registry = FakeRegistry()
        self._prepare(
            registry,
            recipients=[{"id": 11, "email": "a@example.com", "firstName": "Ann"}],
        )
        result = deliver_release(
            registry=registry,
            issue_time=self.issue_time,
            release_issue_date=None,
            edition_type="daily",
            release_scope="production",
            actual_git_commit="a" * 40,
        )
        self.assertEqual("FAILED", result["state"])
        self.assertEqual(1, result["failed"])
        self.assertEqual(1, len(registry.failed))
        mock_report.assert_not_called()

    @patch("src.registry_pipeline.report_send_results", side_effect=RuntimeError("DTL PL unavailable"))
    @patch("src.registry_pipeline.send_brief", return_value="provider-a")
    def test_attribution_failure_does_not_reclassify_confirmed_delivery(self, _mock_send, _mock_report):
        registry = FakeRegistry()
        self._prepare(
            registry,
            recipients=[{"id": 11, "email": "a@example.com", "firstName": "Ann"}],
        )
        result = deliver_release(
            registry=registry,
            issue_time=self.issue_time,
            release_issue_date=None,
            edition_type="daily",
            release_scope="production",
            actual_git_commit="a" * 40,
        )
        self.assertEqual("DELIVERED", result["state"])
        self.assertIn("DTL PL unavailable", result["attribution_warning"])
        self.assertIsNone(registry.failed_reason)

    @patch("src.registry_pipeline.send_brief", side_effect=RuntimeError("provider timeout"))
    def test_uncertain_provider_outcome_preserves_claim_for_idempotent_resume(self, _mock_send):
        registry = FakeRegistry()
        self._prepare(
            registry,
            recipients=[{"id": 11, "email": "a@example.com", "firstName": "Ann"}],
        )
        with self.assertRaises(RegistryProviderUncertainError):
            deliver_release(
                registry=registry,
                issue_time=self.issue_time,
                release_issue_date=None,
                edition_type="daily",
                release_scope="production",
                actual_git_commit="a" * 40,
            )
        self.assertIsNone(registry.failed_reason)

    @patch(
        "src.registry_pipeline.send_brief",
        side_effect=DeliveryRejectedError("recipient rejected"),
    )
    def test_known_provider_rejection_is_terminal_for_recipient(self, _mock_send):
        registry = FakeRegistry()
        self._prepare(
            registry,
            recipients=[{"id": 11, "email": "a@example.com", "firstName": "Ann"}],
        )
        result = deliver_release(
            registry=registry,
            issue_time=self.issue_time,
            release_issue_date=None,
            edition_type="daily",
            release_scope="production",
            actual_git_commit="a" * 40,
        )
        self.assertEqual("FAILED", result["state"])
        self.assertEqual(1, result["failed"])
        self.assertEqual("recipient rejected", registry.failed[0]["error"])
        self.assertIsNone(registry.failed_reason)

    @patch(
        "src.registry_pipeline.send_brief",
        side_effect=DeliveryUncertainError("provider timeout"),
    )
    def test_typed_uncertain_provider_outcome_preserves_claim(self, _mock_send):
        registry = FakeRegistry()
        self._prepare(
            registry,
            recipients=[{"id": 11, "email": "a@example.com", "firstName": "Ann"}],
        )
        with self.assertRaises(RegistryProviderUncertainError):
            deliver_release(
                registry=registry,
                issue_time=self.issue_time,
                release_issue_date=None,
                edition_type="daily",
                release_scope="production",
                actual_git_commit="a" * 40,
            )
        self.assertIsNone(registry.failed_reason)


if __name__ == "__main__":
    unittest.main()
