# Permanent Signal Release Architecture — Decision Record

**Status:** Option B approved; implementation in proof-only containment
**Scope:** Daily Signal first; Weekly Wrap migration remains paused
**Author:** Manus AI

## Problem to solve

Signal currently discovers sources, scores evidence, writes the edition, validates imagery and sends email inside one scheduled morning process. That makes the subscriber commitment depend on every upstream service completing correctly at 06:00 AEST. Friday’s late recovery and Monday’s abort show that this is structurally fragile: failures are discovered at the moment readers expect delivery.

> **Permanent operating principle:** prepare and validate the edition before the delivery window; deliver only an immutable, date-matched artefact that has already passed every content, image, audience and release check.

## Viable approaches

| Approach | How it works | Trade-offs | Cost | Setup complexity |
|---|---|---|---|---|
| **A. Provider-held scheduled edition** | A prior-evening Render preflight generates the complete edition, validates it, freezes the recipient list, and schedules each exact message with Resend for 06:00 AEST. Resend becomes the durable hand-off; there is no content-generation job at 06:00. | Fastest route using the present stack. It removes same-morning generation risk and supports cancellation. The audience is frozen at preflight, operational history is distributed across receipts and provider records, and idempotency protection is provider-limited to 24 hours. | Low incremental cost; existing Render and Resend services. | Medium |
| **B. Durable release registry plus scheduled delivery** | A small release registry stores edition state, immutable HTML checksum, image identity, audience snapshot, provider IDs and timestamps. The prior-evening preflight writes a `LOCKED` release. A separate deterministic delivery stage can consume only that record; webhooks update delivery status. | Strongest auditability and safest long-term control. Supports cancellation, retries, duplicate prevention beyond 24 hours, a clear management view and future Signal/DTL PL integration. It introduces a database and a second managed component that must itself be monitored. | Moderate; an additional managed service/database may incur provider costs. | High |

Resend can schedule individual or batch emails up to 30 days ahead, accepts ISO 8601 delivery timestamps and allows scheduled messages to be cancelled before delivery.[1] [2] Resend also supports idempotency keys on individual and batch send endpoints, but retains those keys for 24 hours; permanent duplicate protection therefore requires Signal’s own edition identity when a release can be retried outside that window.[3] Resend delivery webhooks are at-least-once and may arrive out of order, so any registry must deduplicate by webhook ID and order state by event timestamp.[4]

## Controls required in either approach

| Control | Required behaviour |
|---|---|
| **Edition identity** | One immutable key: edition number + issue date + renderer + HTML checksum. |
| **Content readiness** | Ten distinct AI sources; adoption majority; at least three adoption items per section; five independently numeric Focus sources. |
| **Image readiness** | Date-matched, rights-cleared, non-repeating REMEMBER THE WORLD record must exist before lock. |
| **Audience readiness** | Snapshot only active subscribers; record count and stable recipient identity before scheduling. |
| **Idempotency** | A recipient cannot be scheduled or sent twice for the same edition, even after retries or manual triggers. |
| **Timing state** | A delivery outside the approved morning window is `LATE_RECOVERY`, never normal success. |
| **Failure state** | Any failed preflight creates `HELD` and alerts Paul before the delivery window; it creates no scheduled subscriber messages. |
| **Immutability** | The delivery stage cannot regenerate copy, change source links, choose another image or alter the audience. |
| **Verification** | Provider status and at least one actual mailbox copy must match the locked checksum before `SUBSCRIBER VERIFIED`. |

## Decision

Fordy selected **Approach B**. The dedicated registry database and deterministic preflight-to-delivery implementation are being introduced under dry-run containment. Subscriber activation remains prohibited until the Edition 0048 proof and a controlled one-recipient canary pass against the exact deployed commit.

## References

[1]: https://resend.com/docs/dashboard/emails/schedule-email "Resend — Schedule Email"
[2]: https://resend.com/docs/api-reference/emails/cancel-email "Resend — Cancel Email"
[3]: https://resend.com/docs/dashboard/emails/idempotency-keys "Resend — Idempotency Keys"
[4]: https://resend.com/docs/webhooks/introduction "Resend — Managing Webhooks"
