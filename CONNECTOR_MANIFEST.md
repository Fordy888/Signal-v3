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

| Field | Value |
|-------|-------|
| Service name | `dtl-signal` |
| Service type | Cron job |
| Schedule | `0 20 * * *` UTC (6:00 AM AEST) |
| Runtime | Python 3.11.9 |
| Region | Singapore |
| Plan | Standard |
| Deploy method | Auto-deploy from GitHub `master` |

**Permissions available:** Environment variable management, manual deploys, log access, service restart.

**Environment variables on Render:**

| Variable | Purpose | Sensitive |
|----------|---------|-----------|
| `ANTHROPIC_API_KEY` | Claude API access for scoring/synthesis | Yes |
| `RESEND_API_KEY` | Email delivery authentication | Yes |
| `RESEND_FROM_EMAIL` | Sender address (`signal@dtlc.ai`) | No |
| `RECIPIENT_EMAIL` | Legacy fallback (not used when API active) | Yes |
| `BETTERSTACK_HEARTBEAT_URL` | Monitoring ping endpoint | Yes |
| `WEBSITE_BASE_URL` | DTLC.ai website for subscriber API | No |
| `SIGNAL_PIPELINE_API_KEY` | Authentication to subscriber API | Yes |
| `MODEL_SCORING` | Scoring model identifier | No |
| `MODEL_SYNTHESIS` | Synthesis model identifier | No |
| `TZ` | Timezone (`Australia/Brisbane`) | No |

**Rules:**
- Do not change the cron schedule without Paul's approval.
- Do not change the region without testing delivery latency.
- Model selection changes require approval.

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
| Scoring model | `claude-haiku-4-5-20251001` |
| Synthesis model | `claude-sonnet-4-6` |
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
