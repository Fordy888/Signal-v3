# DTL Signal Pipeline — v3.0

**Daily AI intelligence brief for business executives.**

Signal fetches 103 RSS sources, scores them through Claude Haiku, synthesises a personalised 9-section brief via Claude Sonnet, and delivers it by email at 6:00am AEST.

---

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   FETCH      │ ──▶ │    SCORE     │ ──▶ │  SYNTHESISE  │ ──▶ │   DELIVER    │
│ src/sources  │     │ src/scoring  │     │ src/synthesis │     │ src/delivery │
│              │     │              │     │              │     │              │
│ 103 RSS +    │     │ Claude Haiku │     │ Claude Sonnet│     │ Resend API   │
│ HackerNews   │     │ Threshold:20 │     │ 9 sections   │     │ Per subscriber│
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

---

## The 9 Sections

| # | Section | Max Items | Notes |
|---|---------|-----------|-------|
| 1 | What's Lighting Up in AI | 3 | Direction changes, not product updates |
| 2 | Opportunity Radar | 3 | Specific buyer profile + specific pain |
| 3 | Products & Suppliers | 2 | Concrete tools worth evaluating |
| 4 | Threat Detection & Security | 2 | Often quiet |
| 5 | People in AI — Who's Shaking It Up? | 2 | Specific people, specific reasons |
| 6 | Tactical AI Stack — Agentic | 2 | Tools worth testing within 30 days |
| 7 | Cultural Shifts — Global Thinking | 2 | Shifts that create/remove buyers |
| 8 | **Policy Signal** | 2 | Australian Federal Government only. WATCH/ACT indicators. Default: quiet. |
| 9 | DTLc.ai's Take | 1 | Strategic interpretation — the capstone. Always real insight, never placeholder. |

**Total ceiling:** 14-18 items, 700-1200 words.

---

## Source Categories (103 feeds)

| Category | Count | Purpose |
|----------|-------|---------|
| AI Market Signals | 28 | Core AI industry intelligence |
| Australian Government Policy | 19 | Federal departments/regulators affecting business |
| Strategy & Decision Making | 12 | Executive-level thinking |
| Australian Business | 9 | Local market context |
| Geopolitics | 8 | International dynamics |
| Venture Capital | 8 | Funding signals |
| Opportunity Radar | 7 | Business opportunity sources |
| Cultural & Economic Shifts | 7 | Macro trends |
| Tactical AI Stack | 4 | Tools and agentic platforms |
| Threat Detection | 2 | Security and disruption |

Sources are defined in `config/sources.yaml`.

---

## Subscriber Model

Subscribers are defined in `config/subscribers.yaml`:

```yaml
subscribers:
  - id: paul_ford
    name: Paul Ford
    email: paul.ford@gmail.com
    context_file: config/context.yaml
    edition_prefix: PF
    active: true
```

Each subscriber gets:
- Their own context model (editorial voice, section caps, profile)
- A unique edition stamp (e.g., `PF::SIGNAL-042`)
- Independent delivery via Resend

---

## Key Files

```
config/
  sources.yaml          ← RSS feed definitions (103 sources)
  context.yaml          ← Subscriber context model (Paul)
  context_holly.yaml    ← Subscriber context model (Holly)
  subscribers.yaml      ← Subscriber registry

prompts/
  scoring_prompt.md     ← Haiku scoring criteria (5 dimensions, 0-50)
  synthesis_prompt.md   ← Editorial brain — section structure, voice, HTML templates

src/
  main.py              ← Orchestrator — fetch → score → synthesise → deliver
  sources.py           ← RSS fetcher + HackerNews + deduplication
  scoring.py           ← Claude Haiku batch scoring
  synthesis.py         ← Claude Sonnet synthesis + retry logic + QA
  delivery.py          ← Resend email delivery

render.yaml            ← Render cron job configuration
```

---

## Running Locally

### Prerequisites

- Python 3.11+
- Anthropic API key
- Resend API key

### Setup

```bash
cp .env.template .env
# Fill in your API keys
pip install -r requirements.txt
```

### Dry Run (no email sent)

```bash
python -m src.main --dry-run --save-html test-output.html
```

### Full Run (sends email)

```bash
python -m src.main --save-html output.html
```

### Single Subscriber

```bash
python -m src.main --subscriber paul_ford --save-html paul-test.html --dry-run
```

---

## Deployment (Render)

The pipeline runs as a **Render cron job** (see `render.yaml`):

| Setting | Value |
|---------|-------|
| Service name | `dtl-signal` |
| Schedule | `0 20 * * *` UTC (= 06:00 AEST) |
| Region | Singapore |
| Runtime | Python 3.11.9 |
| Plan | Standard |

### Environment Variables (Render)

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Claude API access |
| `RESEND_API_KEY` | Email delivery |
| `RESEND_FROM_EMAIL` | Sender address |
| `RECIPIENT_EMAIL` | Fallback recipient (legacy mode) |
| `BETTERSTACK_HEARTBEAT_URL` | Uptime monitoring |
| `MODEL_SCORING` | Scoring model override |
| `MODEL_SYNTHESIS` | Synthesis model override |
| `TZ` | Timezone (`Australia/Brisbane`) |

---

## Quality Gates

The pipeline will **not send** an edition unless:

1. Section 9 (DTLc.ai's Take) contains `KEY INSIGHT`, `STRATEGIC IMPLICATION`, and `WATCH FOR`
2. The HTML is valid and complete (auto-repairs truncated output)
3. No double-footer (checked before delivery)

If synthesis fails quality checks, it retries up to 2 times with explicit instructions to complete Section 9.

---

## Monitoring

- **BetterStack heartbeat:** Pinged on every successful run. Alerts if pipeline fails to complete within 24 hours.
- **Logs:** Written to `logs/signal_YYYYMMDD.log` (local) or Render Dashboard → Logs tab (production).

---

## Policy Signal Rules (Section 8)

- Maximum 2 items per edition
- Australian Federal Government only
- Default state is **quiet** — most days have no relevant policy movement
- Only items that directly affect business leaders within 90 days
- Status indicators: **WATCH** (monitor) or **ACT** (deadline/enforcement/compliance)
- No routine ministerial fluff, appointments, or generic speeches
- Empty state: *"Policy Signal: Quiet today — no Australian federal policy or regulatory movement requiring business leader attention."*

---

## Manual Approval Workflow (Beta)

Until the pipeline is fully reliable, editions follow a proof-before-send process:

1. Pipeline generates the edition with `--proof` flag
2. Proof copy sent only to Paul for review
3. Paul reviews and triggers full send manually
4. No auto-send to beta subscribers without human QA

This prevents placeholder leaks, hallucinated content, or formatting issues from reaching subscribers.

---

## Known Gaps (as of v3.0)

| Gap | Status | Resolution Path |
|-----|--------|-----------------|
| Subscriber list divergence | Manual sync acceptable for first 10 | Pipeline to consume `/api/pipeline/subscribers` before expanding to 40 |
| Click tracking | Not wired | Add tracking pixels + link wrapping before 40-subscriber milestone |
| Sender address consistency | Under review | Align welcome email + daily edition to single verified sender |
| Hardcoded base URLs | Fixed in website | Pipeline uses env var for unsubscribe links |
| Feedback tokens | Not implemented | Wire into editions before 40-subscriber milestone |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v3.0 | Jul 2026 | 103 sources, 9-section architecture, Policy Signal (Section 8), double-footer fix, subscriber registry |
| v2.0 | Jun 2026 | 55 sources, 8-section architecture, Resend delivery, Render cron, BetterStack monitoring |
| v1.0 | May 2026 | Initial pipeline — local cron, Gmail SMTP, single recipient |

---

## Related Systems

| System | Owns | Location |
|--------|------|----------|
| **This pipeline** (Render cron) | Daily Signal generation + delivery | `Fordy888/Signal` on GitHub |
| **Website/App** (Manus webdev) | Subscribe flow, welcome email, subscriber DB, /ops dashboard, unsubscribe | Manus platform |
| **Technical Operating Map** | Single source of truth for all system boundaries | Shared document |

For full system architecture, refer to the **DTLC.ai / Signal Technical Operating Map**.
