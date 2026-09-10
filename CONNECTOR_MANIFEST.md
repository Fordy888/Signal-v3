# Signal Connector Manifest

**This document lists every external service Signal depends on, what it does, what permissions are available, and what must not be changed without approval.**

Read this alongside `SIGNAL_CONTEXT.md` before starting any Signal work.

---

## Connected Services

| # | Service | Purpose | Status |
|---|---------|---------|--------|
| 1 | GitHub | Code repository and version control | Connected |
| 2 | Render | Deployment, hosting, and cron scheduling | Connected |
| 3 | Resend | Email delivery (editions + operational alerts) | Connected |
| 4 | Anthropic (Claude) | AI scoring and synthesis models | Connected |
| 5 | DTLC.ai Website API | Subscriber source of truth | Connected |
| 6 | BetterStack | Uptime monitoring and heartbeat | Connected |
| 7 | Google (Gmail) | Operational receipts and alert destination | Connected |
| 8 | GoDaddy | Domain/DNS management for signal.dtlc.ai | Connected |

---

## 1. GitHub

| Field | Value |
|-------|-------|
| Repository | `Fordy888/Signal-v3` |
| Branch | `master` (production) |
| Access | Read/write via personal access token |
| Role | **Source of truth for all Signal code** |
| Auto-deploy trigger | Push to `master` triggers Render deploy |

**Permissions available:** Full repository access (push, pull, branch management, releases).

**Rules:**
- All code changes must be committed and pushed to `master` to take effect.
- Do not force-push or rewrite history on `master`.
- Commit messages must be descriptive and reference what was changed and why.

---

## 2. Render

Render hosts Signal as **three cron services**, all defined in `render.yaml` and
auto-deployed from GitHub `master`. All three share: Python 3.11.9, Singapore
region, Standard plan, `maxShutdownDelaySeconds: 30`, and
`TZ=Australia/Brisbane`.

| Service | Schedule (UTC) | Start command | Purpose |
|---------|----------------|---------------|---------|
| `dtl-signal` | `0 20 * * *` (6:00 AM AEST daily) | `python -m src.main --send` | **Production.** Daily edition to all subscribers. |
| `dtl-signal-subscriber-update` | `0 5 14 7 *` (3:00 PM AEST, 14 July) | `python send_subscriber_update.py --send` | One-off subscriber announcement. **Spent — see rules below.** |
| `dtl-signal-proof` | `0 0 1 1 *` (parked) | `python -m src.main --proof` | Manual trigger only. Sends to Paul alone. |

A schedule of `0 0 1 1 *` is the parked/disabled convention: it means "1 January",
so the service effectively only ever runs when triggered manually from the Render
dashboard.

**Permissions available:** Environment variable management, manual deploys, log access, service restart.

**Note on "Connected":** this refers to the *hosting* relationship — GitHub
`master` pushes auto-deploy to Render. There is **no Render MCP connector
installed on the Claude side**, so an AI session cannot read Render logs, list
deploys, or check service status on its own. Log inspection is manual via the
Render dashboard. The official Render connector exists in the Claude connector
directory and can be added under claude.ai → Settings → Connectors if that
changes.

**Environment variables on Render:**

Sensitive values use `sync: false` (set in the Render dashboard, never committed).
Non-sensitive values are committed in `render.yaml`.

| Variable | Purpose | Sensitive | Services |
|----------|---------|-----------|----------|
| `ANTHROPIC_API_KEY` | Claude API access for scoring/synthesis | Yes | signal, proof |
| `RESEND_API_KEY` | Email delivery authentication | Yes | all three |
| `RESEND_FROM_EMAIL` | Sender address (`signal@signal.dtlc.ai`; `paul@signal.dtlc.ai` on subscriber-update) | No | all three |
| `PROOF_RECIPIENT_EMAIL` | Proof/alert destination (`paul.ford@gmail.com`) | Yes | signal, proof |
| `BETTERSTACK_HEARTBEAT_URL` | Monitoring ping endpoint | Yes | signal only |
| `WEBSITE_BASE_URL` | DTLC.ai website for subscriber API | No | all three |
| `SIGNAL_PIPELINE_API_KEY` | Authentication to subscriber API | Yes | all three |
| `MODEL_SCORING` | Scoring model identifier | No | signal, proof |
| `MODEL_SYNTHESIS` | Synthesis model identifier | No | signal, proof |
| `MODEL_FOUNDERS_NOTE` | Founder's note model identifier | No | signal, proof |
| `ENABLE_GAUGE` | Signal Strength Gauge mode (`off` in prod, `proof` in proof) | No | signal, proof |
| `GAUGE_BASE_URL` | Gauge click-through endpoint | No | signal, proof |
| `TZ` | Timezone (`Australia/Brisbane`) | No | all three |
| `PYTHON_VERSION` | Runtime pin (`3.11.9`) | No | all three |

**Read by the code but not set in `render.yaml`** (defaults apply — set only if needed):

| Variable | Purpose |
|----------|---------|
| `RECIPIENT_EMAIL` | Legacy fallback recipient. `src/main.py` falls back to it when `PROOF_RECIPIENT_EMAIL` is unset; `src/delivery.py` uses it when no explicit recipient is passed. Not used when the subscriber API is active. |
| `GAUGE_MODE` | Gauge click behaviour (`static` default, or `interactive`) |
| `GAUGE_EDITIONS` | Comma-separated edition list when `ENABLE_GAUGE=selected` |

**Why `BETTERSTACK_HEARTBEAT_URL` is on one service only:** the heartbeat must
fire only on a successful production delivery. Proof runs and subscriber updates
must never ping it, or a missed real edition would go unnoticed. This matches the
BetterStack rules in section 6 — do not add it to the other two services.

**Rules:**
- Do not change the cron schedule without Paul's approval.
- Do not change the region without testing delivery latency.
- Model selection changes require approval.
- `dtl-signal-subscriber-update` is a **spent one-off**. It fired on Tue 14 Jul
  2026 but its schedule was never parked, so it will re-fire on 14 Jul 2027 and
  re-send the announcement to the live subscriber list. It needs its schedule set
  to `0 0 1 1 *` or the service removed — **requires Paul's approval**, as it
  touches subscriber delivery.

---

## 3. Resend

| Field | Value |
|-------|-------|
| From address | `Signal <signal@signal.dtlc.ai>` |
| Reply-to | `paul.ford@gmail.com` |
| Domain | `signal.dtlc.ai` (verified) |
| Rate limit | 2 requests/second (current plan) |
| Role | **Delivers Signal editions and operational alerts** |

**Permissions available:** Send emails, manage domains, view delivery logs.

**What it sends:**

| Email type | Recipients | Frequency |
|-----------|-----------|-----------|
| Signal edition | All active subscribers (currently 15) | Daily |
| Run receipt | paul.ford@gmail.com | After every run |
| QA failure alert | paul.ford@gmail.com | When edition is held |
| Early warning | paul.ford@gmail.com | When source health degrades |

**Rules:**
- From address and reply-to must not be changed without approval.
- Rate limiting (700ms between sends) must remain in place.
- Domain DNS records (SPF, DKIM, DMARC) must not be modified without approval.

---

## 4. Anthropic (Claude)

| Field | Value |
|-------|-------|
| Scoring model | `claude-haiku-4-5-20251001` (`MODEL_SCORING`) |
| Synthesis model | `claude-sonnet-4-6` (`MODEL_SYNTHESIS`) |
| Founder's note model | `claude-sonnet-4-6` (`MODEL_FOUNDERS_NOTE`) |
| Role | AI scoring of source items + edition generation |
| Authentication | API key on Render |

**Permissions available:** Model invocation only.

**Rules:**
- Model changes require Paul's approval (affects editorial quality and cost).
- Prompt changes to `prompts/synthesis_prompt.md` affect editorial output — treat as editorial decisions.

---

## 5. DTLC.ai Website API

| Field | Value |
|-------|-------|
| Endpoint | `{WEBSITE_BASE_URL}/api/trpc/signal.getActiveSubscribers` |
| Authentication | `SIGNAL_PIPELINE_API_KEY` in header |
| Role | **Source of truth for active subscribers** |
| Behaviour | Returns list of active subscribers with name and email |

**Permissions available:** Read-only access to active subscriber list.

**Rules:**
- The subscriber API is the **only** source of truth for who receives Signal.
- Never send from a cached list, static file, or assumed count.
- Double-fetch verification must remain in place (two calls, compare results).
- The website may cold-start (autoscale) — warm-up retry logic handles this.

---

## 6. BetterStack

| Field | Value |
|-------|-------|
| Type | Heartbeat monitor |
| Ping | Sent on successful pipeline completion |
| Alert | Triggers if heartbeat is missed (pipeline didn't complete) |

**Permissions available:** Heartbeat ping only.

**Rules:**
- Heartbeat must only fire after successful delivery, not after a hold.
- If the QA gate holds an edition, BetterStack should NOT receive a ping (this triggers an alert, which is correct behaviour — it means "something needs attention").

---

## 7. Google (Gmail)

| Field | Value |
|-------|-------|
| Address | `paul.ford@gmail.com` |
| Role | Receives operational alerts, run receipts, and subscriber replies |

**Permissions available:** Destination only (no API integration).

**Rules:**
- All operational communications go to paul.ford@gmail.com.
- This may change to a dedicated ops inbox in future — but only with Paul's approval.

---

## 8. GoDaddy

| Field | Value |
|-------|-------|
| Domain | `dtlc.ai` (and subdomains including `signal.dtlc.ai`) |
| Role | DNS management for email delivery (MX, SPF, DKIM, DMARC) |

**Permissions available:** DNS record management.

**Rules:**
- Do not modify DNS records without Paul's approval.
- Changes to email-related DNS (SPF, DKIM, DMARC) can break delivery immediately.
- Any domain work must be documented and reversible.

---

## Source of Truth Summary

| Function | Source of Truth | Not This |
|----------|----------------|----------|
| Code | GitHub (`master` branch) | Local files, other branches |
| Subscribers | DTLC.ai website API | Static files, cached lists, env vars |
| Email delivery | Resend | Direct SMTP, other providers |
| Deployment | Render (auto-deploy from GitHub) | Manual deploys, other hosts |
| Configuration | `config/sources.yaml` + Render env vars | Hardcoded values in code |
| Editorial standards | `EDITORIAL.md` | Ad hoc decisions |
| Source quality | `docs/source-scoring-criteria.md` | Gut feel |

---

## Adding or Changing Connectors

Before adding a new service or changing an existing connector:

1. Document the change in this manifest.
2. Get Paul's approval if it affects delivery, subscribers, or editorial output.
3. Test in isolation before deploying to production.
4. Update `SIGNAL_CONTEXT.md` if the change affects operating procedures.

---

## The Rule

> Every connected service has a defined role. If you're unsure whether a connector is available or how it's configured, check this manifest first. Do not guess. Do not assume. Do not ask Paul to repeat what's already documented here.
