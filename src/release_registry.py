from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable


RELEASE_STATES = {
    "PREPARING",
    "HELD",
    "LOCKED",
    "SCHEDULED",
    "DELIVERING",
    "DELIVERED",
    "LATE_RECOVERY",
    "FAILED",
    "EXPIRED",
}

RELEASE_TRANSITIONS = {
    "PREPARING": {"HELD", "LOCKED"},
    "HELD": {"PREPARING", "EXPIRED"},
    "LOCKED": {"SCHEDULED", "EXPIRED"},
    "SCHEDULED": {"DELIVERING", "EXPIRED"},
    "DELIVERING": {"DELIVERED", "FAILED", "LATE_RECOVERY"},
    "DELIVERED": set(),
    "LATE_RECOVERY": set(),
    "FAILED": set(),
    "EXPIRED": set(),
}

DELIVERY_STATES = {"PENDING", "SENDING", "SENT", "DELIVERED", "BOUNCED", "FAILED"}
CLAIM_LEASE_MINUTES = 30
PROVIDER_IDEMPOTENCY_SAFE_HOURS = 23
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class RegistryError(RuntimeError):
    pass


class RegistryConfigurationError(RegistryError):
    pass


class RegistryIntegrityError(RegistryError):
    pass


class RegistryTransitionError(RegistryError):
    pass


class RegistryProviderUncertainError(RegistryError):
    pass


@dataclass(frozen=True)
class FrozenRecipient:
    subscriber_id: int | None
    email: str
    first_name: str
    unsubscribe_token: str
    html_body: str
    recipient_hash: str
    html_sha256: str
    idempotency_key: str


@dataclass(frozen=True)
class FrozenRelease:
    id: str
    edition_number: int
    issue_date: date
    edition_type: str
    release_scope: str
    editorial_revision: str
    renderer: str
    release_id: str
    git_commit: str
    subject: str
    html_body: str
    html_sha256: str
    image_id: str | None
    image_sha256: str | None
    audience_sha256: str
    audience_count: int
    metadata: dict[str, Any]
    scheduled_for: datetime
    window_start: datetime
    window_end: datetime
    recipients: tuple[FrozenRecipient, ...]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalise_email(value: str) -> str:
    email = str(value or "").strip().lower()
    if not email or "@" not in email:
        raise RegistryIntegrityError("recipient email is missing or invalid")
    return email


def validate_sha256(value: str, label: str) -> str:
    candidate = str(value or "").strip().lower()
    if not SHA256_RE.fullmatch(candidate):
        raise RegistryIntegrityError(f"{label} must be a lowercase SHA-256 value")
    return candidate


def validate_transition(current: str, target: str) -> None:
    if current not in RELEASE_STATES or target not in RELEASE_STATES:
        raise RegistryTransitionError(f"unknown release state transition: {current} -> {target}")
    if target == current:
        return
    if target not in RELEASE_TRANSITIONS[current]:
        raise RegistryTransitionError(f"illegal release state transition: {current} -> {target}")


def classify_delivery_window(now: datetime, window_start: datetime, window_end: datetime) -> str:
    if now.tzinfo is None or window_start.tzinfo is None or window_end.tzinfo is None:
        raise RegistryIntegrityError("delivery-window timestamps must be timezone-aware")
    if window_end < window_start:
        raise RegistryIntegrityError("delivery window end precedes its start")
    if now < window_start:
        return "EARLY"
    if now > window_end:
        return "LATE"
    return "OPEN"


def validate_uncertain_send_retry(*, now: datetime, last_updated: datetime) -> None:
    if now.tzinfo is None or last_updated.tzinfo is None:
        raise RegistryIntegrityError("uncertain-send timestamps must be timezone-aware")
    if now - last_updated >= timedelta(hours=PROVIDER_IDEMPOTENCY_SAFE_HOURS):
        raise RegistryTransitionError(
            "uncertain provider send is outside the safe idempotency retry window"
        )


def recipient_idempotency_key(
    *, edition_number: int, edition_type: str, release_scope: str, recipient_hash: str
) -> str:
    validate_sha256(recipient_hash, "recipient hash")
    if release_scope not in {"proof", "production"}:
        raise RegistryIntegrityError("release scope must be proof or production")
    raw = f"dtl-signal:{edition_number:04d}:{edition_type}:{release_scope}:{recipient_hash}"
    return sha256_text(raw)


def _freeze_recipients(
    *,
    edition_number: int,
    edition_type: str,
    release_scope: str,
    recipients: Iterable[dict[str, Any]],
) -> tuple[tuple[FrozenRecipient, ...], str]:
    frozen: list[FrozenRecipient] = []
    seen: set[str] = set()
    for recipient in recipients:
        email = normalise_email(recipient.get("email", ""))
        if email in seen:
            raise RegistryIntegrityError(f"duplicate recipient in frozen audience: {email}")
        seen.add(email)
        html_body = str(recipient.get("html_body", ""))
        if "<html" not in html_body.lower() and "<!doctype" not in html_body.lower():
            raise RegistryIntegrityError(f"recipient HTML is incomplete for {email}")
        recipient_hash = sha256_text(email)
        html_sha256 = sha256_text(html_body)
        frozen.append(
            FrozenRecipient(
                subscriber_id=(
                    int(recipient["subscriber_id"])
                    if recipient.get("subscriber_id") is not None
                    else int(recipient["id"]) if recipient.get("id") is not None else None
                ),
                email=email,
                first_name=str(recipient.get("first_name") or recipient.get("firstName") or ""),
                unsubscribe_token=str(recipient.get("unsubscribe_token") or ""),
                html_body=html_body,
                recipient_hash=recipient_hash,
                html_sha256=html_sha256,
                idempotency_key=recipient_idempotency_key(
                    edition_number=edition_number,
                    edition_type=edition_type,
                    release_scope=release_scope,
                    recipient_hash=recipient_hash,
                ),
            )
        )
    if not frozen:
        raise RegistryIntegrityError("a locked release requires at least one recipient")
    if len(frozen) > 500:
        raise RegistryIntegrityError("frozen audience exceeds the 500-recipient safety limit")
    frozen.sort(key=lambda item: item.recipient_hash)
    audience_payload = [
        {
            "subscriber_id": item.subscriber_id,
            "recipient_hash": item.recipient_hash,
            "first_name": item.first_name,
            "unsubscribe_token_sha256": sha256_text(item.unsubscribe_token),
            "recipient_html_sha256": item.html_sha256,
        }
        for item in frozen
    ]
    audience_sha256 = sha256_text(
        json.dumps(audience_payload, sort_keys=True, separators=(",", ":"))
    )
    return tuple(frozen), audience_sha256


def build_frozen_release(
    *,
    edition_number: int,
    issue_date: date,
    edition_type: str,
    release_scope: str,
    editorial_revision: str,
    renderer: str,
    release_id: str,
    git_commit: str,
    subject: str,
    html_body: str,
    image_id: str | None,
    image_sha256: str | None,
    scheduled_for: datetime,
    window_start: datetime,
    window_end: datetime,
    recipients: Iterable[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
    registry_id: str | None = None,
) -> FrozenRelease:
    if edition_number <= 0:
        raise RegistryIntegrityError("edition number must be positive")
    if edition_type not in {"daily", "weekly_wrap"}:
        raise RegistryIntegrityError("edition type must be daily or weekly_wrap")
    if release_scope not in {"proof", "production"}:
        raise RegistryIntegrityError("release scope must be proof or production")
    if not editorial_revision or not renderer or not release_id or not subject:
        raise RegistryIntegrityError("release identity and subject are required")
    commit = str(git_commit or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RegistryIntegrityError("git commit must be a full 40-character SHA")
    normalised_html = html_body.lower()
    has_document_wrapper = "<html" in normalised_html or "<!doctype" in normalised_html
    has_complete_email_fragment = (
        len(html_body) >= 1000
        and "<table" in normalised_html
        and "</table>" in normalised_html
    )
    if not has_document_wrapper and not has_complete_email_fragment:
        raise RegistryIntegrityError("release HTML is incomplete")
    if scheduled_for.tzinfo is None or window_start.tzinfo is None or window_end.tzinfo is None:
        raise RegistryIntegrityError("scheduled delivery timestamps must be timezone-aware")
    if not (window_start <= scheduled_for <= window_end):
        raise RegistryIntegrityError("scheduled time must fall inside the delivery window")
    if edition_type == "daily" and (not image_id or not image_sha256):
        raise RegistryIntegrityError("v4 daily releases require a governed image identity")
    normalised_image_sha = (
        validate_sha256(image_sha256 or "", "image SHA-256") if image_id else None
    )
    frozen_recipients, audience_sha256 = _freeze_recipients(
        edition_number=edition_number,
        edition_type=edition_type,
        release_scope=release_scope,
        recipients=recipients,
    )
    return FrozenRelease(
        id=registry_id or str(uuid.uuid4()),
        edition_number=edition_number,
        issue_date=issue_date,
        edition_type=edition_type,
        release_scope=release_scope,
        editorial_revision=editorial_revision,
        renderer=renderer,
        release_id=release_id,
        git_commit=commit,
        subject=subject,
        html_body=html_body,
        html_sha256=sha256_text(html_body),
        image_id=image_id,
        image_sha256=normalised_image_sha,
        audience_sha256=audience_sha256,
        audience_count=len(frozen_recipients),
        metadata=dict(metadata or {}),
        scheduled_for=scheduled_for,
        window_start=window_start,
        window_end=window_end,
        recipients=frozen_recipients,
    )


def verify_frozen_release(release: FrozenRelease) -> None:
    if release.edition_number <= 0:
        raise RegistryIntegrityError("edition number must be positive")
    if release.edition_type not in {"daily", "weekly_wrap"}:
        raise RegistryIntegrityError("edition type must be daily or weekly_wrap")
    if release.release_scope not in {"proof", "production"}:
        raise RegistryIntegrityError("release scope must be proof or production")
    if not release.editorial_revision or not release.renderer or not release.release_id:
        raise RegistryIntegrityError("release identity is incomplete")
    if not release.subject:
        raise RegistryIntegrityError("release subject is missing")
    if not re.fullmatch(r"[0-9a-f]{40}", release.git_commit):
        raise RegistryIntegrityError("release git commit is invalid")
    if "<html" not in release.html_body.lower() and "<!doctype" not in release.html_body.lower():
        raise RegistryIntegrityError("release HTML is incomplete")
    if (
        release.scheduled_for.tzinfo is None
        or release.window_start.tzinfo is None
        or release.window_end.tzinfo is None
    ):
        raise RegistryIntegrityError("release delivery timestamps must be timezone-aware")
    if not (release.window_start <= release.scheduled_for <= release.window_end):
        raise RegistryIntegrityError("release scheduled time is outside its delivery window")
    if release.edition_type == "daily" and (not release.image_id or not release.image_sha256):
        raise RegistryIntegrityError("daily release governed image identity is missing")
    if release.image_id:
        validate_sha256(release.image_sha256 or "", "image SHA-256")
    validate_sha256(release.html_sha256, "release HTML SHA-256")
    validate_sha256(release.audience_sha256, "audience SHA-256")
    if sha256_text(release.html_body) != release.html_sha256:
        raise RegistryIntegrityError("release HTML checksum mismatch")
    if release.audience_count != len(release.recipients):
        raise RegistryIntegrityError("release audience count mismatch")
    expected_recipients, expected_audience_sha = _freeze_recipients(
        edition_number=release.edition_number,
        edition_type=release.edition_type,
        release_scope=release.release_scope,
        recipients=[
            {
                "email": recipient.email,
                "subscriber_id": recipient.subscriber_id,
                "first_name": recipient.first_name,
                "unsubscribe_token": recipient.unsubscribe_token,
                "html_body": recipient.html_body,
            }
            for recipient in release.recipients
        ],
    )
    if expected_audience_sha != release.audience_sha256:
        raise RegistryIntegrityError("release audience checksum mismatch")
    expected_by_hash = {item.recipient_hash: item for item in expected_recipients}
    for recipient in release.recipients:
        expected = expected_by_hash.get(recipient.recipient_hash)
        if expected is None or expected.html_sha256 != recipient.html_sha256:
            raise RegistryIntegrityError("recipient HTML checksum mismatch")
        if expected.idempotency_key != recipient.idempotency_key:
            raise RegistryIntegrityError("recipient idempotency key mismatch")


def stored_release_matches(existing: dict[str, Any], release: FrozenRelease) -> bool:
    metadata = existing.get("metadata")
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    expected = {
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
    actual = {key: existing.get(key) for key in expected}
    actual["metadata"] = dict(metadata or {})
    return actual == expected


class ReleaseRegistry:
    def __init__(self, database_url: str):
        self.database_url = str(database_url or "").strip()
        if not self.database_url:
            raise RegistryConfigurationError("SIGNAL_REGISTRY_DATABASE_URL is not configured")

    @classmethod
    def from_env(cls) -> "ReleaseRegistry":
        return cls(os.environ.get("SIGNAL_REGISTRY_DATABASE_URL", ""))

    def _connect(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RegistryConfigurationError("psycopg is required for the release registry") from exc
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def store_locked_release(self, release: FrozenRelease) -> str:
        verify_frozen_release(release)
        with self._connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT *
                        FROM signal_releases
                        WHERE edition_number = %s AND edition_type = %s AND release_scope = %s
                        FOR UPDATE
                        """,
                        (release.edition_number, release.edition_type, release.release_scope),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        if existing["state"] in {"LOCKED", "SCHEDULED"} and stored_release_matches(
                            existing, release
                        ):
                            return str(existing["id"])
                        raise RegistryIntegrityError(
                            "edition already exists with different identity or non-reusable state"
                        )

                    cursor.execute(
                        """
                        INSERT INTO signal_releases (
                            id, edition_number, issue_date, edition_type, release_scope, state,
                            editorial_revision, renderer, release_id, git_commit,
                            subject, html_body, html_sha256, image_id, image_sha256,
                            audience_sha256, audience_count, metadata, scheduled_for,
                            window_start, window_end
                        ) VALUES (
                            %s, %s, %s, %s, %s, 'PREPARING',
                            %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            release.id,
                            release.edition_number,
                            release.issue_date,
                            release.edition_type,
                            release.release_scope,
                            release.editorial_revision,
                            release.renderer,
                            release.release_id,
                            release.git_commit,
                            release.subject,
                            release.html_body,
                            release.html_sha256,
                            release.image_id,
                            release.image_sha256,
                            release.audience_sha256,
                            release.audience_count,
                            json.dumps(release.metadata),
                            release.scheduled_for,
                            release.window_start,
                            release.window_end,
                        ),
                    )
                    for recipient in release.recipients:
                        cursor.execute(
                            """
                            INSERT INTO signal_release_recipients (
                                release_id, subscriber_id, recipient_email, recipient_hash, first_name,
                                unsubscribe_token, recipient_html_body,
                                recipient_html_sha256, idempotency_key
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                release.id,
                                recipient.subscriber_id,
                                recipient.email,
                                recipient.recipient_hash,
                                recipient.first_name,
                                recipient.unsubscribe_token,
                                recipient.html_body,
                                recipient.html_sha256,
                                recipient.idempotency_key,
                            ),
                        )
                    self._event(
                        cursor,
                        release_id=release.id,
                        event_type="release_prepared",
                        from_state=None,
                        to_state="PREPARING",
                        payload={"audience_count": release.audience_count},
                    )
                    cursor.execute(
                        """
                        UPDATE signal_releases
                        SET state = 'LOCKED', locked_at = NOW()
                        WHERE id = %s AND state = 'PREPARING'
                        """,
                        (release.id,),
                    )
                    self._event(
                        cursor,
                        release_id=release.id,
                        event_type="release_locked",
                        from_state="PREPARING",
                        to_state="LOCKED",
                        payload={"html_sha256": release.html_sha256},
                    )
                    cursor.execute(
                        """
                        UPDATE signal_releases
                        SET state = 'SCHEDULED'
                        WHERE id = %s AND state = 'LOCKED'
                        """,
                        (release.id,),
                    )
                    self._event(
                        cursor,
                        release_id=release.id,
                        event_type="release_scheduled",
                        from_state="LOCKED",
                        to_state="SCHEDULED",
                        payload={"scheduled_for": release.scheduled_for.isoformat()},
                    )
        return release.id

    def claim_scheduled_release(
        self, *, issue_date: date, edition_type: str, release_scope: str, now: datetime
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT * FROM signal_releases
                        WHERE issue_date = %s AND edition_type = %s AND release_scope = %s
                        FOR UPDATE
                        """,
                        (issue_date, edition_type, release_scope),
                    )
                    release = cursor.fetchone()
                    if not release:
                        return None
                    if release["state"] == "DELIVERING":
                        if release["claim_expires_at"] and release["claim_expires_at"] > now:
                            return None
                        if classify_delivery_window(
                            now, release["window_start"], release["window_end"]
                        ) == "LATE":
                            cursor.execute(
                                "UPDATE signal_releases SET state = 'FAILED' WHERE id = %s",
                                (release["id"],),
                            )
                            self._event(
                                cursor,
                                release_id=str(release["id"]),
                                event_type="release_resume_expired",
                                from_state="DELIVERING",
                                to_state="FAILED",
                                payload={"observed_at": now.isoformat()},
                            )
                            return None
                        claim_token = str(uuid.uuid4())
                        cursor.execute(
                            """
                            UPDATE signal_releases
                            SET claim_token = %s, claim_expires_at = %s
                            WHERE id = %s AND state = 'DELIVERING'
                            RETURNING *
                            """,
                            (
                                claim_token,
                                now + timedelta(minutes=CLAIM_LEASE_MINUTES),
                                release["id"],
                            ),
                        )
                        resumed = cursor.fetchone()
                        self._event(
                            cursor,
                            release_id=str(release["id"]),
                            event_type="release_resumed",
                            from_state="DELIVERING",
                            to_state="DELIVERING",
                            payload={"observed_at": now.isoformat()},
                        )
                        return resumed
                    if release["state"] != "SCHEDULED":
                        raise RegistryTransitionError(
                            f"release is {release['state']}, not SCHEDULED"
                        )
                    window_state = classify_delivery_window(
                        now, release["window_start"], release["window_end"]
                    )
                    if window_state == "EARLY":
                        raise RegistryTransitionError("delivery window has not opened")
                    if window_state == "LATE":
                        cursor.execute(
                            "UPDATE signal_releases SET state = 'EXPIRED' WHERE id = %s",
                            (release["id"],),
                        )
                        self._event(
                            cursor,
                            release_id=str(release["id"]),
                            event_type="release_expired",
                            from_state="SCHEDULED",
                            to_state="EXPIRED",
                            payload={"observed_at": now.isoformat()},
                        )
                        return None
                    claim_token = str(uuid.uuid4())
                    cursor.execute(
                        """
                        UPDATE signal_releases
                        SET state = 'DELIVERING', claim_token = %s, claim_expires_at = %s
                        WHERE id = %s AND state = 'SCHEDULED'
                        RETURNING *
                        """,
                        (
                            claim_token,
                            now + timedelta(minutes=CLAIM_LEASE_MINUTES),
                            release["id"],
                        ),
                    )
                    claimed = cursor.fetchone()
                    self._event(
                        cursor,
                        release_id=str(release["id"]),
                        event_type="release_claimed",
                        from_state="SCHEDULED",
                        to_state="DELIVERING",
                        payload={"observed_at": now.isoformat()},
                    )
                    return claimed

    def load_delivery_recipients(self, release_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM signal_release_recipients
                    WHERE release_id = %s AND delivery_state IN ('PENDING', 'SENDING')
                    ORDER BY recipient_hash
                    """,
                    (release_id,),
                )
                return list(cursor.fetchall())

    def load_frozen_release(self, release_id: str) -> FrozenRelease:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM signal_releases WHERE id = %s", (release_id,))
                release = cursor.fetchone()
                if not release:
                    raise RegistryIntegrityError("release not found")
                cursor.execute(
                    """
                    SELECT * FROM signal_release_recipients
                    WHERE release_id = %s ORDER BY recipient_hash
                    """,
                    (release_id,),
                )
                recipient_rows = list(cursor.fetchall())
        recipients = tuple(
            FrozenRecipient(
                subscriber_id=row["subscriber_id"],
                email=row["recipient_email"],
                first_name=row["first_name"] or "",
                unsubscribe_token=row["unsubscribe_token"] or "",
                html_body=row["recipient_html_body"],
                recipient_hash=row["recipient_hash"],
                html_sha256=row["recipient_html_sha256"],
                idempotency_key=row["idempotency_key"],
            )
            for row in recipient_rows
        )
        metadata = release["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        return FrozenRelease(
            id=str(release["id"]),
            edition_number=release["edition_number"],
            issue_date=release["issue_date"],
            edition_type=release["edition_type"],
            release_scope=release["release_scope"],
            editorial_revision=release["editorial_revision"],
            renderer=release["renderer"],
            release_id=release["release_id"],
            git_commit=release["git_commit"],
            subject=release["subject"],
            html_body=release["html_body"],
            html_sha256=release["html_sha256"],
            image_id=release["image_id"],
            image_sha256=release["image_sha256"],
            audience_sha256=release["audience_sha256"],
            audience_count=release["audience_count"],
            metadata=dict(metadata or {}),
            scheduled_for=release["scheduled_for"],
            window_start=release["window_start"],
            window_end=release["window_end"],
            recipients=recipients,
        )

    def claim_next_recipient(
        self, *, release_id: str, claim_token: str, now: datetime
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id FROM signal_releases
                        WHERE id = %s AND state = 'DELIVERING'
                          AND claim_token = %s AND claim_expires_at >= %s
                        FOR UPDATE
                        """,
                        (release_id, claim_token, now),
                    )
                    if not cursor.fetchone():
                        raise RegistryTransitionError("delivery claim is missing or expired")
                    cursor.execute(
                        """
                        SELECT * FROM signal_release_recipients
                        WHERE release_id = %s AND delivery_state IN ('PENDING', 'SENDING')
                        ORDER BY CASE WHEN delivery_state = 'SENDING' THEN 0 ELSE 1 END,
                                 recipient_hash
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                        """,
                        (release_id,),
                    )
                    recipient = cursor.fetchone()
                    if not recipient:
                        return None
                    if recipient["delivery_state"] == "SENDING":
                        validate_uncertain_send_retry(
                            now=now, last_updated=recipient["updated_at"]
                        )
                    cursor.execute(
                        """
                        UPDATE signal_release_recipients
                        SET delivery_state = 'SENDING', attempt_count = attempt_count + 1,
                            last_error = NULL
                        WHERE id = %s
                        RETURNING *
                        """,
                        (recipient["id"],),
                    )
                    claimed = cursor.fetchone()
                    self._event(
                        cursor,
                        release_id=release_id,
                        recipient_id=int(recipient["id"]),
                        event_type="recipient_send_claimed",
                        from_state=recipient["delivery_state"],
                        to_state="SENDING",
                        payload={"attempt_count": claimed["attempt_count"]},
                    )
                    return claimed

    def mark_recipient_sent(
        self,
        *,
        release_id: str,
        claim_token: str,
        recipient_id: int,
        provider_message_id: str,
    ) -> None:
        if not provider_message_id:
            raise RegistryIntegrityError("provider message ID is required")
        with self._connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE signal_release_recipients
                        SET delivery_state = 'SENT', provider_message_id = %s,
                            sent_at = NOW(), last_error = NULL
                        WHERE id = %s AND release_id = %s AND delivery_state = 'SENDING'
                          AND EXISTS (
                              SELECT 1 FROM signal_releases
                              WHERE id = %s AND state = 'DELIVERING' AND claim_token = %s
                          )
                        """,
                        (provider_message_id, recipient_id, release_id, release_id, claim_token),
                    )
                    if cursor.rowcount != 1:
                        raise RegistryTransitionError("recipient is not in SENDING state")
                    self._event(
                        cursor,
                        release_id=release_id,
                        recipient_id=recipient_id,
                        event_type="recipient_sent",
                        from_state="SENDING",
                        to_state="SENT",
                        payload={"provider_message_id": provider_message_id},
                    )

    def mark_recipient_failed(
        self, *, release_id: str, claim_token: str, recipient_id: int, error: str
    ) -> None:
        sanitised = str(error or "provider error")[:500]
        with self._connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE signal_release_recipients
                        SET delivery_state = 'FAILED', last_error = %s
                        WHERE id = %s AND release_id = %s AND delivery_state = 'SENDING'
                          AND EXISTS (
                              SELECT 1 FROM signal_releases
                              WHERE id = %s AND state = 'DELIVERING' AND claim_token = %s
                          )
                        """,
                        (sanitised, recipient_id, release_id, release_id, claim_token),
                    )
                    if cursor.rowcount != 1:
                        raise RegistryTransitionError("recipient is not in SENDING state")
                    self._event(
                        cursor,
                        release_id=release_id,
                        recipient_id=recipient_id,
                        event_type="recipient_failed",
                        from_state="SENDING",
                        to_state="FAILED",
                        payload={"reason": sanitised},
                    )

    def complete_release(self, *, release_id: str, claim_token: str) -> str:
        with self._connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id FROM signal_release_recipients
                        WHERE release_id = %s
                        FOR UPDATE
                        """,
                        (release_id,),
                    )
                    cursor.fetchall()
                    cursor.execute(
                        """
                        SELECT
                            COUNT(*) FILTER (
                                WHERE delivery_state IN ('SENT', 'DELIVERED', 'BOUNCED')
                            ) AS sent,
                            COUNT(*) FILTER (WHERE delivery_state = 'FAILED') AS failed,
                            COUNT(*) AS total
                        FROM signal_release_recipients WHERE release_id = %s
                        """,
                        (release_id,),
                    )
                    counts = cursor.fetchone()
                    target = (
                        "DELIVERED"
                        if counts["total"] > 0 and counts["sent"] == counts["total"]
                        else "FAILED"
                    )
                    cursor.execute(
                        """
                        UPDATE signal_releases
                        SET state = %s, delivered_at = CASE WHEN %s = 'DELIVERED' THEN NOW() ELSE delivered_at END
                        WHERE id = %s AND state = 'DELIVERING' AND claim_token = %s
                        """,
                        (target, target, release_id, claim_token),
                    )
                    if cursor.rowcount != 1:
                        raise RegistryTransitionError("release is not in DELIVERING state")
                    self._event(
                        cursor,
                        release_id=release_id,
                        event_type="release_completed" if target == "DELIVERED" else "release_failed",
                        from_state="DELIVERING",
                        to_state=target,
                        payload=dict(counts),
                    )
                    return target

    def fail_claimed_release(
        self, *, release_id: str, claim_token: str, reason: str
    ) -> None:
        sanitised = str(reason or "registry delivery failure")[:500]
        with self._connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE signal_releases
                        SET state = 'FAILED'
                        WHERE id = %s AND state = 'DELIVERING' AND claim_token = %s
                        """,
                        (release_id, claim_token),
                    )
                    if cursor.rowcount != 1:
                        raise RegistryTransitionError("release claim is no longer active")
                    self._event(
                        cursor,
                        release_id=release_id,
                        event_type="release_failed",
                        from_state="DELIVERING",
                        to_state="FAILED",
                        payload={"reason": sanitised},
                    )

    def _event(
        self,
        cursor,
        *,
        release_id: str,
        recipient_id: int | None = None,
        event_type: str,
        from_state: str | None,
        to_state: str | None,
        payload: dict[str, Any],
    ) -> None:
        cursor.execute(
            """
            INSERT INTO signal_release_events (
                release_id, recipient_id, event_type, from_state, to_state, payload
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                release_id,
                recipient_id,
                event_type,
                from_state,
                to_state,
                json.dumps(payload),
            ),
        )
