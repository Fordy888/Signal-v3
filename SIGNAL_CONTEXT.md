# Signal Operating Context

**This document must be read before any Signal work begins.**

It defines what Signal is, how it operates, what systems it depends on, and what rules are non-negotiable. If you are an AI agent, developer, or operator working on Signal, this is your starting point.

---

## What Signal Is

Signal is a **live beta product** — not a prototype, not an experiment, not a side project.

It is an executive intelligence brief delivered daily to paying-calibre subscribers. Its purpose is to improve executive judgment by surfacing the developments, patterns, and strategic implications that matter most to business leaders navigating AI-driven change.

Signal is part of the DTLC.ai product ecosystem. It creates awareness, trust, and daily relevance. It is the front door.

**Owner:** Paul Ford, CEO, DTL Group
**Brand:** DTL Signal (branded as "Signal" in editions)
**Domain:** signal.dtlc.ai
**Audience:** CEOs, founders, and senior leaders in Australia and globally

---

## Operating Principles

1. **Signal must not send anything that damages trust.** Metadata errors, wrong dates, broken formatting, or delivery to the wrong people are all trust-damaging events.

2. **Critical failures hold the edition.** If the QA gate identifies a critical issue, the edition does not send. No exceptions.

3. **The system catches problems before subscribers do.** Monitoring, alerts, and receipts exist so that Paul is never surprised by a failure that a subscriber noticed first.

4. **Source quality is governed by the scoring framework.** Sources are evaluated, scored, and assigned status (active/probation/disabled). The pipeline respects these statuses. See `docs/source-scoring-criteria.md`.

5. **The subscriber API is the source of truth for recipients.** Never send from a static list, cached file, or assumed count. Always fetch live.

6. **Every run produces a receipt.** After every pipeline execution, a plain-English run receipt is emailed to paul.ford@gmail.com summarising what happened.

7. **Signal is executive intelligence, not generic AI news.** Editorial quality is governed by `EDITORIAL.md`. Every item must pass the test: "Does this improve executive judgment?"

---

## Architecture (How It Runs)

| Component | System | Details |
|-----------|--------|---------|
| Code repository | GitHub | `Fordy888/Signal-v3` on `master` branch |
| Deployment | Render | Cron job, auto-deploys from `master` |
| Schedule | Daily | `0 20 * * *` UTC = 6:00 AM AEST (Brisbane) |
| Runtime | Python 3.11 | Render Standard plan, Singapore region |
| AI Models | Anthropic Claude | Scoring: `claude-haiku-4-5`, Synthesis: `claude-sonnet-4-6` |
| Email delivery | Resend | From: `signal@signal.dtlc.ai`, Reply-to: `paul.ford@gmail.com` |
| Subscriber source | DTLC.ai website API | Live fetch with double-verification |
| Monitoring | BetterStack | Heartbeat URL pinged on successful completion |
| Alerts | Email (Resend) | Sent to paul.ford@gmail.com on failure or hold |

---

## Pre-Send QA Gate (7 Checks)

Every edition must pass these checks before sending. Critical failures = hold.

| # | Check | Severity | What It Catches |
|---|-------|----------|-----------------|
| 1 | Edition Number | CRITICAL | Corrupted counter, out-of-sequence |
| 2 | Date Integrity | CRITICAL | Date/weekday/timestamp misalignment |
| 3 | Subject/Body Alignment | CRITICAL | Edition number or date missing from body |
| 4 | Content Minimum | CRITICAL | Empty or too-short generation |
| 5 | Source Health | CRITICAL | 50%+ sources down |
| 6 | Recipient Count | CRITICAL | Zero subscribers, count mismatch, email-set mismatch |
| 7 | Reply-To Validation | CRITICAL | Missing/invalid from address, reply-to, or API key |

---

## Source Governance

Sources are managed in `config/sources.yaml` and governed by the scoring framework in `docs/source-scoring-criteria.md`.

**Status field controls fetching:**
- `active` — fetched every run
- `probation` — fetched but flagged; under review
- `disabled` — skipped entirely; not fetched

**Adding or removing sources requires:**
1. Scoring against the 6-dimension rubric (30 points max)
2. Technical verification (feed returns 200 OK with valid content)
3. Assignment of appropriate status
4. Documentation in the `notes` field

---

## Run Receipt Format

After every run, paul.ford@gmail.com receives a receipt. Format:

**Success:**
> Edition 0014: QA passed. Delivered to 15/15 active subscribers. Sources fetched: 95. Failed sources: 2. Disabled sources skipped: 13. Delivery failures: 0. Status: Safe.

**Hold:**
> Edition 0014: QA failed. Send held. Reason: [plain English explanation]. Action required: [what to do].

**Partial failure:**
> Edition 0014: Sent with issues. Delivered to 13/15 subscribers. 2 delivery failure(s): [emails]. Status: Edition delivered but needs attention.

---

## What Must Not Be Changed Without Paul's Approval

- Subscriber list or API endpoint
- From address or reply-to routing
- Cron schedule (send time)
- Editorial structure (9 sections)
- QA gate severity levels (critical checks must remain critical)
- Scoring/synthesis model selection
- Domain/DNS configuration

---

## Current State (as of 9 July 2026)

- **Edition count:** 0013 delivered (0014 next)
- **Active subscribers:** Fetched live from API (do not hardcode — count changes as subscribers join/leave)
- **Active sources:** 95 RSS feeds + HackerNews
- **Disabled sources:** 13 (broken government feeds)
- **Known gaps:** Section 4 (Threat Detection) thin, Sections 3 & 5 have no dedicated sources
- **Recent fixes:** Rate limiting, TypeError crash, source governance, QA gate

---

## File Map

```
SIGNAL_CONTEXT.md          ← You are here. Read this first.
CONNECTOR_MANIFEST.md      ← Connected services and permissions.
EDITORIAL.md               ← Editorial philosophy and principles.
config/sources.yaml        ← All RSS sources with metadata and status.
docs/source-scoring-criteria.md  ← How to evaluate sources.
docs/source-scoring-results.md   ← Scored evaluations of current sources.
docs/product-direction.md        ← Product roadmap and direction.
src/main.py                ← Pipeline orchestrator (QA gate integrated).
src/qa_gate.py             ← Pre-send checks and run receipts.
src/delivery.py            ← Email delivery via Resend.
src/subscribers.py         ← Subscriber API integration.
src/sources.py             ← Source fetching with status enforcement.
src/scoring.py             ← AI scoring of items.
src/synthesis.py           ← Edition generation.
src/edition_counter.py     ← Edition numbering.
render.yaml                ← Render deployment configuration.
```

---

## Keeping This Document Current

Any material change to Signal — QA gate logic, subscriber handling, source governance, domains, delivery, alerts, or editorial rules — must update the relevant context file (`SIGNAL_CONTEXT.md`, `CONNECTOR_MANIFEST.md`, or `EDITORIAL.md`) in the same commit as the code change.

When starting work on Signal, confirm:
1. Which context documents were read.
2. Which commit/version is the starting point.

---

## The Rule

> If Signal depends on it, check it before acting. If it's documented here, don't ask Paul to repeat it.
