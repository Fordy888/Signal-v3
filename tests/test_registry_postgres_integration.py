from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

from src.release_registry import ReleaseRegistry, build_frozen_release


BRISBANE = ZoneInfo("Australia/Brisbane")
DATABASE_URL = os.getenv("SIGNAL_REGISTRY_TEST_DATABASE_URL")


@unittest.skipUnless(DATABASE_URL, "requires SIGNAL_REGISTRY_TEST_DATABASE_URL")
class RegistryPostgresIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        with psycopg.connect(DATABASE_URL) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    TRUNCATE signal_release_events, signal_release_recipients, signal_releases
                    RESTART IDENTITY
                    """
                )
        self.registry = ReleaseRegistry(DATABASE_URL)
        self.issue_time = datetime(2026, 9, 7, 6, 0, tzinfo=BRISBANE)

    def _release(
        self,
        *,
        edition_number: int = 48,
        table_fragment: bool = False,
        release_scope: str = "proof",
        issue_time: datetime | None = None,
        metadata: dict | None = None,
    ):
        issue_time = issue_time or self.issue_time
        release_html = (
            "<table>" + ("Locked Signal release content " * 100) + "</table>"
            if table_fragment
            else "<!DOCTYPE html><html><body>Edition</body></html>"
        )
        recipient_html = (
            "<table>" + ("Personalised Signal content for Paul " * 100) + "</table>"
            if table_fragment
            else "<!DOCTYPE html><html><body>Paul</body></html>"
        )
        return build_frozen_release(
            edition_number=edition_number,
            issue_date=issue_time.date(),
            edition_type="daily",
            release_scope=release_scope,
            editorial_revision="ai-adoption-v1",
            renderer="enhanced-v4-focus-numbers",
            release_id=f"ai-adoption-v1-registry-{edition_number:04d}-{release_scope}",
            git_commit="a" * 40,
            subject=f"[PROOF] DTL Signal Edition {edition_number:04d}",
            html_body=release_html,
            image_id=f"REMEMBER-{edition_number:04d}",
            image_sha256="b" * 64,
            scheduled_for=issue_time,
            window_start=issue_time - timedelta(minutes=5),
            window_end=issue_time + timedelta(minutes=20),
            recipients=[
                {
                    "subscriber_id": 1,
                    "email": "paul@example.com",
                    "first_name": "Paul",
                    "html_body": recipient_html,
                }
            ],
            metadata=metadata,
        )

    def _deliver(self, release, *, at: datetime) -> None:
        self.registry.store_locked_release(release)
        claimed = self.registry.claim_scheduled_release(
            issue_date=release.issue_date,
            edition_type="daily",
            release_scope=release.release_scope,
            now=at,
        )
        recipient = self.registry.claim_next_recipient(
            release_id=release.id,
            claim_token=str(claimed["claim_token"]),
            now=at,
        )
        self.registry.mark_recipient_sent(
            release_id=release.id,
            claim_token=str(claimed["claim_token"]),
            recipient_id=int(recipient["id"]),
            provider_message_id=f"provider-{release.edition_number}",
        )
        self.registry.complete_release(
            release_id=release.id,
            claim_token=str(claimed["claim_token"]),
        )

    def test_table_fragment_stores_and_reloads_through_real_postgres(self) -> None:
        release = self._release(table_fragment=True)
        self.registry.store_locked_release(release)
        stored = self.registry.load_frozen_release(release.id)
        self.assertEqual(release, stored)
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT state, audience_count FROM signal_releases WHERE id = %s",
                    (release.id,),
                )
                row = cursor.fetchone()
        self.assertEqual("SCHEDULED", row["state"])
        self.assertEqual(1, row["audience_count"])

    def test_full_claim_send_complete_path_and_append_only_events(self) -> None:
        release = self._release()
        self.registry.store_locked_release(release)
        claimed = self.registry.claim_scheduled_release(
            issue_date=release.issue_date,
            edition_type="daily",
            release_scope="proof",
            now=self.issue_time,
        )
        recipient = self.registry.claim_next_recipient(
            release_id=release.id,
            claim_token=str(claimed["claim_token"]),
            now=self.issue_time,
        )
        self.registry.mark_recipient_sent(
            release_id=release.id,
            claim_token=str(claimed["claim_token"]),
            recipient_id=int(recipient["id"]),
            provider_message_id="provider-1",
        )
        self.assertEqual(
            "DELIVERED",
            self.registry.complete_release(
                release_id=release.id, claim_token=str(claimed["claim_token"])
            ),
        )
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT state FROM signal_releases WHERE id = %s", (release.id,)
                )
                self.assertEqual("DELIVERED", cursor.fetchone()["state"])
                cursor.execute(
                    "SELECT event_type FROM signal_release_events WHERE release_id = %s",
                    (release.id,),
                )
                event_types = {row["event_type"] for row in cursor.fetchall()}
        self.assertTrue(
            {
                "release_prepared",
                "release_locked",
                "release_scheduled",
                "release_claimed",
                "recipient_send_claimed",
                "recipient_sent",
                "release_completed",
            }.issubset(event_types)
        )
        with self.assertRaises(psycopg.Error):
            with psycopg.connect(DATABASE_URL) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE signal_release_events SET event_type = 'tampered' "
                        "WHERE release_id = %s",
                        (release.id,),
                    )

    def test_locked_release_and_recipient_identity_are_immutable(self) -> None:
        release = self._release()
        self.registry.store_locked_release(release)
        with self.assertRaises(psycopg.Error):
            with psycopg.connect(DATABASE_URL) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE signal_releases SET html_body = '<html>changed</html>' "
                        "WHERE id = %s",
                        (release.id,),
                    )
        with self.assertRaises(psycopg.Error):
            with psycopg.connect(DATABASE_URL) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE signal_release_recipients SET recipient_email = 'other@example.com' "
                        "WHERE release_id = %s",
                        (release.id,),
                    )

    def test_active_claim_blocks_duplicate_trigger(self) -> None:
        release = self._release()
        self.registry.store_locked_release(release)
        first = self.registry.claim_scheduled_release(
            issue_date=release.issue_date,
            edition_type="daily",
            release_scope="proof",
            now=self.issue_time,
        )
        second = self.registry.claim_scheduled_release(
            issue_date=release.issue_date,
            edition_type="daily",
            release_scope="proof",
            now=self.issue_time + timedelta(minutes=1),
        )
        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_recent_delivery_history_survives_restart_and_scopes_sources(self) -> None:
        proof_time = self.issue_time - timedelta(days=1)
        proof = self._release(
            edition_number=48,
            issue_time=proof_time,
            metadata={
                "source_urls": ["https://example.com/proof-only"],
                "joke_id": "J048",
                "alive_moment": {"id": "IMAGE-48", "category": "craft"},
            },
        )
        production = self._release(
            edition_number=49,
            release_scope="production",
            issue_time=self.issue_time,
            metadata={
                "source_urls": ["https://example.com/production"],
                "joke_id": "J049",
                "alive_moment": {"id": "IMAGE-49", "category": "water"},
            },
        )
        self._deliver(proof, at=proof_time)
        self._deliver(production, at=self.issue_time)

        restarted_registry = ReleaseRegistry(DATABASE_URL)
        history = restarted_registry.load_recent_delivery_history(
            as_of=datetime.now(BRISBANE) + timedelta(hours=1)
        )

        self.assertEqual(
            {"https://example.com/production"},
            history["source_urls"],
        )
        self.assertEqual(["J048", "J049"], history["joke_ids"])
        self.assertEqual(
            ["IMAGE-48", "IMAGE-49"],
            [moment["id"] for moment in history["alive_moments"]],
        )


if __name__ == "__main__":
    unittest.main()
