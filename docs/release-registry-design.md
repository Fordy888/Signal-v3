# DTL Signal Durable Release Registry

**Status:** Architecture approved; implementation audited locally; production schema pending
**Decision:** Option B selected by Paul Ford
**Author:** Manus AI
**Subscriber state:** Dry-run containment

## Purpose

The release registry makes the **edition**, rather than the Render command or an email receipt, the source of truth. It separates content preparation from delivery and makes the morning job deterministic.

> The 06:00 AEST job may deliver one already-locked, date-matched edition. It may not fetch sources, call an editorial model, change a source, select an image, rebuild HTML or reinterpret a release manifest.

## Proposed infrastructure

Use a dedicated **Render Postgres** database named `dtl-signal-registry` in the Singapore region. A read-only review of the current Render project shows one resource—the `dtl-signal` cron service—and no database or persistent key-value store to reuse.

Render provides an internal database URL for services in the same account and region. Using that URL keeps the cron-to-database connection on Render’s private network.[1] Paid Render Postgres instances provide point-in-time recovery and logical exports; the available recovery window depends on the workspace plan.[2]

The approved initial plan is **Basic-256mb** at **US$6 per month** plus the minimum 1 GB storage at **US$0.30 per month**, for an actual live-form total of **US$6.30 per month**. The free database is unsuitable because it has a 30-day limit and does not provide the paid-plan logical backup capability.[2] [6] The release registry’s expected volume is small—one release row and approximately one recipient row per active subscriber per edition—so no larger compute plan is justified initially.

Render created service `dpg-daeupc8u01pc738492kg-a`, named `dtl-signal-registry`, in the current project’s Production environment and Singapore region, with PostgreSQL 18, plan `0.1c-256mb`, **1 GB storage**, storage autoscaling disabled and high availability disabled. A fresh service read reports status `available`. The contained Signal service now has the managed internal connection under a masked environment key; no production schema or registry release data has yet been applied.

The initial default database credential was rotated after Render's dashboard automation unexpectedly surfaced it. Replacement default username `signal_registry_v2` was created with zero open connections, and the original `signal_registry` credential was permanently deleted before any application link, schema or registry data existed. A later managed-reference attempt unexpectedly rendered the replacement connection string before save, so that unsaved edit was cancelled, default credential `signal_registry_v3` was created, and `signal_registry_v2` was permanently deleted with zero open connections before any application or schema use. Only `signal_registry_v3` remains. The contained cron now has the managed internal connection under masked key `SIGNAL_REGISTRY_DATABASE_URL`; no secret value was written to source, logs or local files. No schema or registry release data has yet been applied.

The registry stores HTML as text, not as a local file. The REMEMBER THE WORLD image remains in durable object storage; the registry stores its approved identity, URL, source, creator, licence and checksum. This removes any dependency on Render’s ephemeral filesystem.

## Data model

### `signal_releases`

| Field | Type | Integrity rule |
|---|---|---|
| `id` | UUID | Application-generated immutable identifier |
| `edition_number` | Integer | Positive; unique with edition type because Saturday retains Friday’s number |
| `issue_date` | Date | Unique with edition type |
| `edition_type` | Text | `daily` or `weekly_wrap` |
| `release_scope` | Text | `proof` or `production`; permits an isolated canary and subscriber release for the same edition |
| `state` | Text | Guarded state machine below |
| `editorial_revision` | Text | Versioned policy identifier |
| `renderer` | Text | Exact renderer contract |
| `release_id` | Text | Versioned release contract |
| `git_commit` | Character(40) | Exact deployed source identity |
| `subject` | Text | Locked before delivery |
| `html_body` | Text | Immutable after `LOCKED` |
| `html_sha256` | Character(64) | Verified on every retrieval |
| `image_id` | Text | Mandatory for v4 daily editions |
| `image_sha256` | Character(64) | Stable prepared-image identity |
| `audience_sha256` | Character(64) | Hash of sorted eligible recipient identities |
| `audience_count` | Integer | Must equal recipient-row count |
| `metadata` | JSONB | Immutable source URLs, joke ID, memory update and release diagnostics needed after delivery |
| `scheduled_for` | Timestamp with timezone | Intended delivery time |
| `window_start` / `window_end` | Timestamp with timezone | Only permitted delivery interval |
| `locked_at` / `delivered_at` | Timestamp with timezone | Audit timestamps |
| `created_at` / `updated_at` | Timestamp with timezone | Registry timestamps |

The database has unique constraints on `(edition_number, edition_type, release_scope)` and `(issue_date, edition_type, release_scope)`. This preserves the existing calendar rule in which Saturday’s Weekly Wrap retains Friday’s edition number while allowing one one-recipient proof and one production audience for the same edition. Once a release enters `LOCKED`, a database trigger rejects changes to content identity, subject, HTML, checksums, image, audience and delivery window.

### `signal_release_recipients`

| Field | Type | Integrity rule |
|---|---|---|
| `release_id` | UUID | Foreign key to `signal_releases` |
| `subscriber_id` | Big integer | Frozen DTL PL identity from the source-of-truth audience response |
| `recipient_email` | Text | Frozen audience destination |
| `recipient_hash` | Character(64) | Normalised-email SHA-256 |
| `first_name` | Text | Optional frozen personalisation |
| `unsubscribe_token` | Text | Frozen token used for deterministic final HTML |
| `recipient_html_body` | Text | Exact final recipient HTML; immutable once the release is locked |
| `recipient_html_sha256` | Character(64) | Verifies recipient-specific unsubscribe rendering |
| `delivery_state` | Text | `PENDING`, `SENDING`, `SENT`, `DELIVERED`, `BOUNCED`, `FAILED` |
| `idempotency_key` | Text | Unique permanent Signal identity |
| `provider_message_id` | Text | Unique when Resend accepts the message |
| `attempt_count` | Integer | Monotonic |
| `last_error` | Text | Sanitised; no credentials |
| `sent_at` / `delivered_at` | Timestamp with timezone | Provider lifecycle |

A unique constraint on `(release_id, recipient_hash)` prevents a duplicate audience row. A second unique constraint on `idempotency_key` prevents a second logical send from being created by application retries or manual triggers. The key includes edition number, edition type, release scope and recipient hash, so a proof cannot block the separately approved production release. Resend idempotency remains a second line of defence, but Resend retains provider keys for 24 hours, so the registry is the permanent control.[3]

### `signal_release_events`

This append-only table records release transitions, recipient send claims, confirmed provider acceptance and definitive provider rejection. PostgreSQL rejects any event update or deletion. The schema reserves a unique event key for future idempotent webhook ingestion, but webhook processing is not part of the current activation scope and must not be represented as live.

## Release state machine

| State | Meaning | Permitted next states |
|---|---|---|
| `PREPARING` | Source, plan, image and audience assembly in progress | `HELD`, `LOCKED` |
| `HELD` | A mandatory preflight check failed | `PREPARING`, `EXPIRED` |
| `LOCKED` | Complete immutable edition and audience passed all gates | `SCHEDULED`, `EXPIRED` |
| `SCHEDULED` | Delivery time and recipient rows committed | `DELIVERING`, `EXPIRED` |
| `DELIVERING` | Morning worker owns the release transaction | `DELIVERED`, `FAILED`, `LATE_RECOVERY` |
| `DELIVERED` | Every recipient call accepted; provider verification remains separate | Terminal |
| `LATE_RECOVERY` | Delivery occurred outside the approved window | Terminal |
| `FAILED` | Delivery began but the complete audience was not accepted | Terminal; a new explicit recovery release is required |
| `EXPIRED` | Delivery window passed without eligible execution | Terminal |

State changes use a row lock and a compare-and-set update. A manual trigger racing the scheduled job can acquire only one `SCHEDULED` release; the other process exits without sending.

The delivery claim carries a 30-minute database lease. A competing trigger during that lease is a no-op. If the worker crashes, a later worker may reclaim the `DELIVERING` release only after the lease expires; any recipient left in `SENDING` is retried with the same permanent registry and Resend idempotency key. This closes the crash-after-provider-acceptance gap without permitting concurrent send loops.

An uncertain `SENDING` recipient may be retried only while the provider idempotency key is safely inside a 23-hour boundary. After that point the release fails closed for manual reconciliation rather than risk a duplicate after Resend’s 24-hour idempotency window expires.

The provider boundary requires a real Resend message ID. A transport exception or missing ID is treated as uncertain rather than failed: the database retains `DELIVERING` / `SENDING` and retries only after the lease with the same key. Recipient-state transitions are also guarded in PostgreSQL, preventing a terminal row from being reset to `PENDING` or resent. DTL PL attribution occurs only after registry delivery is complete; an attribution outage is recorded as a warning and cannot rewrite a confirmed provider delivery as failed.

## Two-stage operation

```mermaid
flowchart LR
    A[Prior preflight] --> B{All editorial, image, audience and release gates pass?}
    B -- No --> C[HELD + alert Paul]
    B -- Yes --> D[LOCKED registry artefact]
    D --> E[SCHEDULED for 06:00 AEST]
    E --> F{Morning job inside delivery window?}
    F -- No --> G[EXPIRED or LATE_RECOVERY approval required]
    F -- Yes --> H[Atomic claim: DELIVERING]
    H --> I[Retrieve HTML and verify checksum]
    I --> J[Send idempotently per recipient]
    J --> K[DELIVERED + receipt]
```

The preflight performs all existing source, scoring, planner, reader-copy, image, release-identity, recipient-integrity and HTML checks. It writes the release and recipient snapshot in one transaction only after every gate passes. Failure produces `HELD` and no `SCHEDULED` record.

The morning command reads only the release for the current Brisbane issue date. It verifies state, commit, renderer, checksums, image identity, audience count and delivery window. It never calls the source fetcher, scorer, editorial model or image selector.

## Failure behaviour

| Failure | Required response |
|---|---|
| Registry unavailable | Exit non-zero; send no email; alert through the independent operations channel |
| No date-matched `SCHEDULED` release | Exit non-zero; no generation fallback |
| HTML or image checksum mismatch | Transition to `FAILED`; send nothing |
| Audience checksum or count mismatch | Transition to `FAILED`; send nothing |
| Duplicate scheduled/manual execution | Only one process can claim; the duplicate sends nothing and exits non-zero because no claimable release remains |
| Provider rate limit | Retry with bounded backoff and the same idempotency key |
| Crash after provider acceptance | Retry resolves through registry row plus Resend idempotency; never create a new logical recipient send |
| Run outside the delivery window | Do not send automatically; require explicit `LATE_RECOVERY` approval |

## Migration and rollback

The migration is additive. The existing direct-send code remains present but the production command stays in dry-run containment. New tables are created without modifying subscriber data or historical release artefacts.

Rollback means setting both registry commands to dry-run and leaving subscriber delivery disabled. A registry failure never falls back to the old direct-send path. Database rollback uses point-in-time recovery or a logical export on a paid Render Postgres plan; a recovered instance is validated separately before reconnecting the cron service.[2]

## Deployment shape

| Component | Command | Subscriber effect |
|---|---|---|
| Preflight cron | `python -m src.main --prepare-release --release-scope production --release-date YYYY-MM-DD --enhanced --alive-moment --force-type daily` | Never sends subscriber email |
| Delivery cron | `python -m src.main --deliver-release --release-scope production --release-date YYYY-MM-DD --force-type daily` | Sends only a date-matched `SCHEDULED` registry artefact |
| Existing direct path | `python -m src.main --dry-run ...` | Contained during migration; not a production fallback |

Both cron jobs connect to Postgres through the same-region internal URL. Render cron jobs can initiate private-network connections to Render Postgres but cannot receive inbound private-network traffic.[5]

## Acceptance boundary

No subscriber reactivation occurs until the registry passes source-scarcity, missing-image, checksum-corruption, audience-drift, duplicate-trigger, crash-after-provider-acceptance, late-run and database-unavailable simulations. It must then produce a scheduled one-recipient canary whose registry state, Resend record, receipt and actual Gmail copy all match.

The local acceptance gate currently comprises **168 passing tests across 15 independently bounded modules** in both the integration checkout and a fresh detached worktree. That gate includes a real PostgreSQL rehearsal of the migration, guarded transitions, locked release and recipient immutability, duplicate claims and append-only events. The migration applied once and then returned an idempotent no-op with the same source checksum. These are build-quality facts only; they are not production-schema, email-delivery or scheduled-time evidence.

## References

[1]: https://render.com/docs/postgresql-creating-connecting "Render — Create and Connect to Render Postgres"
[2]: https://render.com/docs/postgresql-backups "Render — Postgres Recovery and Backups"
[3]: https://resend.com/docs/dashboard/emails/idempotency-keys "Resend — Idempotency Keys"
[4]: https://resend.com/docs/webhooks/introduction "Resend — Managing Webhooks"
[5]: https://render.com/docs/private-network "Render — Private Network"
[6]: https://render.com/pricing "Render — Pricing"
