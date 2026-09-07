from __future__ import annotations

import hashlib
import logging
import time
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .attribution import report_send_results
from .delivery import (
    INTER_SEND_DELAY_S,
    DeliveryRejectedError,
    DeliveryUncertainError,
    send_brief,
)
from .release_registry import (
    FrozenRelease,
    RegistryError,
    RegistryIntegrityError,
    RegistryProviderUncertainError,
    ReleaseRegistry,
    build_frozen_release,
    verify_frozen_release,
)
from .share_block import personalise_share_for_subscriber
from .signal_gauge import personalise_gauge_for_subscriber


log = logging.getLogger(__name__)
BRISBANE = ZoneInfo("Australia/Brisbane")


def subject_for_release(
    *, edition_number: int, edition_type: str, issue_date: datetime, scope: str
) -> str:
    prefix = "[PROOF] " if scope == "proof" else ""
    if edition_type == "weekly_wrap":
        return f"{prefix}DTL Signal Weekly Wrap | Week Ending {issue_date.strftime('%d %B %Y')}"
    if scope == "proof":
        return f"[PROOF] DTL Signal | Final Founder-Led Format | Edition {edition_number:04d}"
    return f"DTL Signal | Edition {edition_number:04d} | {issue_date.strftime('%A %d %B %Y')}"


def release_window(
    *, issue_date: datetime, scope: str
) -> tuple[datetime, datetime, datetime]:
    if issue_date.tzinfo is None:
        raise RegistryIntegrityError("release issue time must be timezone-aware")
    if scope == "proof":
        return (
            issue_date,
            issue_date - timedelta(minutes=5),
            issue_date + timedelta(minutes=60),
        )
    scheduled = issue_date.replace(hour=6, minute=0, second=0, microsecond=0)
    return scheduled, scheduled - timedelta(minutes=5), scheduled + timedelta(minutes=20)


def freeze_recipient_html(
    *, html: str, recipient_email: str, delivery_memory: dict[str, Any] | None = None
) -> str:
    from .signal_memory import embed_delivery_memory

    personalised = personalise_gauge_for_subscriber(html, recipient_email)
    subscriber_token = hashlib.sha256(
        recipient_email.lower().strip().encode("utf-8")
    ).hexdigest()[:12]
    personalised = personalise_share_for_subscriber(personalised, subscriber_token)
    if delivery_memory is not None:
        personalised = embed_delivery_memory(personalised, delivery_memory)
    return personalised


def prepare_release(
    *,
    registry: ReleaseRegistry,
    edition_number: int,
    issue_time: datetime,
    delivery_time: datetime | None,
    edition_type: str,
    release_scope: str,
    editorial_revision: str,
    renderer: str,
    release_id: str,
    git_commit: str,
    html: str,
    recipients: list[dict[str, Any]],
    image: dict[str, Any] | None,
    delivery_memory: dict[str, Any] | None,
    metadata: dict[str, Any] | None = None,
) -> FrozenRelease:
    if not recipients:
        raise RegistryIntegrityError("release preparation requires a frozen audience")
    subject = subject_for_release(
        edition_number=edition_number,
        edition_type=edition_type,
        issue_date=issue_time,
        scope=release_scope,
    )
    scheduled_for, window_start, window_end = release_window(
        issue_date=delivery_time or issue_time, scope=release_scope
    )
    frozen_recipients: list[dict[str, Any]] = []
    for recipient in recipients:
        email = str(recipient.get("email") or "").strip().lower()
        frozen_recipients.append(
            {
                "subscriber_id": recipient.get("id") or recipient.get("subscriber_id"),
                "email": email,
                "first_name": recipient.get("firstName") or recipient.get("first_name") or "",
                "unsubscribe_token": recipient.get("unsubscribe_token") or "",
                "html_body": freeze_recipient_html(
                    html=html,
                    recipient_email=email,
                    delivery_memory=delivery_memory,
                ),
            }
        )
    image_id = str(image.get("id") or "").strip() if image else None
    image_sha256 = str(image.get("image_sha256") or "").strip() if image else None
    frozen = build_frozen_release(
        edition_number=edition_number,
        issue_date=issue_time.date(),
        edition_type=edition_type,
        release_scope=release_scope,
        editorial_revision=editorial_revision,
        renderer=renderer,
        release_id=release_id,
        git_commit=git_commit,
        subject=subject,
        html_body=html,
        image_id=image_id,
        image_sha256=image_sha256,
        scheduled_for=scheduled_for,
        window_start=window_start,
        window_end=window_end,
        recipients=frozen_recipients,
        metadata=metadata,
    )
    registry.store_locked_release(frozen)
    persisted = registry.load_frozen_release(frozen.id)
    if persisted != frozen:
        raise RegistryIntegrityError(
            "persisted release does not match the immutable preflight candidate"
        )
    return persisted


def deliver_release(
    *,
    registry: ReleaseRegistry,
    issue_time: datetime,
    release_issue_date: date | None,
    edition_type: str,
    release_scope: str,
    actual_git_commit: str,
) -> dict[str, Any]:
    if issue_time.tzinfo is None:
        raise RegistryIntegrityError("delivery time must be timezone-aware")
    issue_time = issue_time.astimezone(BRISBANE)
    claimed = registry.claim_scheduled_release(
        issue_date=release_issue_date or issue_time.date(),
        edition_type=edition_type,
        release_scope=release_scope,
        now=issue_time,
    )
    if not claimed:
        raise RegistryIntegrityError("no claimable scheduled release for this date and scope")
    release_id = str(claimed["id"])
    claim_token = str(claimed["claim_token"])
    try:
        frozen = registry.load_frozen_release(release_id)
        verify_frozen_release(frozen)
        if frozen.git_commit != actual_git_commit:
            raise RegistryIntegrityError(
                f"release commit {frozen.git_commit} does not match deployed commit {actual_git_commit}"
            )
        if release_scope == "proof" and frozen.audience_count != 1:
            raise RegistryIntegrityError("proof release must contain exactly one recipient")

        sent = 0
        failed = 0
        attribution_rows: list[dict[str, Any]] = []
        while True:
            recipient = registry.claim_next_recipient(
                release_id=release_id,
                claim_token=claim_token,
                now=datetime.now(issue_time.tzinfo),
            )
            if not recipient:
                break
            if sent + failed > 0:
                time.sleep(INTER_SEND_DELAY_S)
            try:
                provider_id = send_brief(
                    html_body=recipient["recipient_html_body"],
                    recipient_email=recipient["recipient_email"],
                    subject_override=frozen.subject,
                    edition_number=frozen.edition_number,
                    tags=[
                        {"name": "message_type", "value": "signal"},
                        {"name": "edition", "value": f"{frozen.edition_number:04d}"},
                        {"name": "edition_type", "value": frozen.edition_type},
                        {"name": "release_scope", "value": frozen.release_scope},
                        {"name": "registry_release", "value": frozen.id},
                    ],
                    idempotency_key=recipient["idempotency_key"],
                    require_message_id=True,
                    raise_on_failure=True,
                )
            except DeliveryRejectedError as exc:
                registry.mark_recipient_failed(
                    release_id=release_id,
                    claim_token=claim_token,
                    recipient_id=recipient["id"],
                    error=str(exc),
                )
                failed += 1
                continue
            except DeliveryUncertainError as exc:
                log.error(
                    "Provider outcome is uncertain; preserving DELIVERING/SENDING state for idempotent resume"
                )
                raise RegistryProviderUncertainError(str(exc)) from exc
            except Exception as exc:
                log.exception(
                    "Unexpected provider exception; preserving DELIVERING/SENDING state for idempotent resume"
                )
                raise RegistryProviderUncertainError(str(exc)) from exc
            if provider_id:
                registry.mark_recipient_sent(
                    release_id=release_id,
                    claim_token=claim_token,
                    recipient_id=recipient["id"],
                    provider_message_id=str(provider_id),
                )
                sent += 1
                if recipient.get("subscriber_id"):
                    attribution_rows.append(
                        {
                            "subscriberId": int(recipient["subscriber_id"]),
                            "resendMessageId": str(provider_id),
                        }
                    )
            else:
                registry.mark_recipient_failed(
                    release_id=release_id,
                    claim_token=claim_token,
                    recipient_id=recipient["id"],
                    error="provider returned no message ID",
                )
                failed += 1

        final_state = registry.complete_release(
            release_id=release_id, claim_token=claim_token
        )
        attribution_warning = None
        if attribution_rows:
            try:
                report_send_results(frozen.edition_number, attribution_rows)
            except Exception as exc:
                attribution_warning = str(exc)[:500]
                log.exception(
                    "Registry delivery completed, but DTL PL attribution reporting failed"
                )
        return {
            "release_id": release_id,
            "edition_number": frozen.edition_number,
            "scope": frozen.release_scope,
            "state": final_state,
            "sent": sent,
            "failed": failed,
            "total": frozen.audience_count,
            "html_sha256": frozen.html_sha256,
            "audience_sha256": frozen.audience_sha256,
            "attribution_warning": attribution_warning,
        }
    except RegistryProviderUncertainError:
        raise
    except Exception as exc:
        try:
            registry.fail_claimed_release(
                release_id=release_id, claim_token=claim_token, reason=str(exc)
            )
        except Exception:
            log.exception("Unable to mark claimed release failed")
        raise
