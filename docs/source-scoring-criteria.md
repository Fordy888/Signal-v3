# Signal Source Quality Scoring Criteria

**Version:** 1.0  
**Created:** 9 July 2026  
**Purpose:** A repeatable framework for evaluating, scoring, and curating content sources for the DTL Signal pipeline. Any source — existing or candidate — can be assessed against these criteria to determine whether it earns a place in `sources.yaml`.

---

## How It Works

Every source is scored across **6 dimensions** on a 1–5 scale. The total possible score is **30 points**. Sources are then classified into tiers that determine their `status` field in `sources.yaml`:

| Tier | Score Range | Status in YAML | Action |
|------|-------------|----------------|--------|
| **Gold** | 25–30 | `active` | Core source. No review needed unless it degrades. |
| **Silver** | 19–24 | `active` | Solid contributor. Review annually. |
| **Bronze** | 13–18 | `probation` | Marginal. Monitor for 2 weeks. Replace if better option exists. |
| **Below threshold** | 1–12 | `disabled` | Do not fetch. Replace immediately. |

---

## The 6 Scoring Dimensions

### 1. Technical Reliability (1–5)

> Can we actually fetch content from this source consistently?

| Score | Criteria |
|-------|----------|
| 5 | 100% uptime over 30 days. Fast response (<3s). Standard RSS/Atom format. |
| 4 | Occasional slow responses but no failures. Minor format quirks. |
| 3 | Intermittent timeouts (1–2 per week). Requires retry logic. |
| 2 | Frequent failures (403, timeouts, rate limiting). Unreliable but sometimes works. |
| 1 | Dead URL (404), permanent block (403), or requires authentication we cannot provide. |

**Red flags (auto-score 1):**
- Returns 404 Not Found
- Returns 403 Forbidden consistently
- Requires login/paywall for RSS access
- Domain has changed and old URL is not redirected

---

### 2. Content Relevance (1–5)

> Does this source produce content that fits Signal's editorial mission?

| Score | Criteria |
|-------|----------|
| 5 | Every item is directly relevant to AI, business transformation, or executive decision-making. |
| 4 | 70%+ of items are relevant. Occasional off-topic items easily filtered by scoring. |
| 3 | 40–70% relevant. Requires heavy LLM filtering. Some noise. |
| 2 | <40% relevant. Mostly off-topic with occasional useful items. |
| 1 | No relevance to Signal's audience. Wrong domain entirely. |

**For Policy Signal (Section 8) specifically:**
- Must produce content about Australian Federal Government policy, regulation, or legislation
- Must affect business leaders (not internal government operations)
- Must be actionable (WATCH or ACT worthy)

---

### 3. Update Frequency (1–5)

> Does this source publish often enough to be worth monitoring?

| Score | Criteria |
|-------|----------|
| 5 | Daily or multiple times per day. Always fresh content. |
| 4 | 3–5 times per week. Reliable cadence. |
| 3 | Weekly. Useful but not daily-relevant. |
| 2 | Monthly or irregular. May go weeks without publishing. |
| 1 | Dormant. Last published 3+ months ago. |

**Note:** For Policy Signal, lower frequency is acceptable (score 3 is fine) because government announcements are event-driven, not scheduled.

---

### 4. Authority & Credibility (1–5)

> Is this a trusted, authoritative voice that Signal's audience would respect?

| Score | Criteria |
|-------|----------|
| 5 | Primary source (the organisation making the announcement). Official government body. Tier-1 institution. |
| 4 | Recognised expert, established publication, or well-known analyst with track record. |
| 3 | Credible trade publication or specialist outlet. Known in the industry. |
| 2 | Aggregator or secondary source. Reposts others' content. Limited original analysis. |
| 1 | Unknown provenance. Blog with no track record. Potential misinformation risk. |

**For Policy Signal:** Primary sources (the actual government department/regulator) score 5. Media reporting on government policy scores 3–4.

---

### 5. Signal-to-Noise Ratio (1–5)

> How much useful content vs filler does this source produce?

| Score | Criteria |
|-------|----------|
| 5 | Every item is substantive. No fluff, no filler, no routine announcements. |
| 4 | Mostly substantive. Occasional routine items easily filtered. |
| 3 | Mixed. Substantive items buried among routine announcements, appointments, generic speeches. |
| 2 | Mostly noise. Routine ministerial statements, generic press releases, ceremonial content. |
| 1 | All noise. No actionable intelligence for business leaders. |

**Red flags for Policy Signal:**
- Routine ministerial photo ops
- Generic "Minister visits X" announcements
- Appointment notices
- Speeches that repeat existing policy without new direction

---

### 6. Uniqueness of Contribution (1–5)

> Does this source provide information we cannot get elsewhere?

| Score | Criteria |
|-------|----------|
| 5 | Only source for this information. Irreplaceable. |
| 4 | Best source for this niche. Others cover it but less well. |
| 3 | One of several equivalent sources. Adds diversity but is replaceable. |
| 2 | Duplicates content available from better-scoring sources. |
| 1 | Completely redundant. Everything here appears in other active sources first. |

---

## Quick Decision Matrix

Before scoring in detail, apply these **instant disqualifiers** (move on immediately):

| Red Flag | Action |
|----------|--------|
| URL returns 404 | Move on. Source is dead. |
| URL returns 403 consistently | Move on. Source blocks automated access. |
| Requires authentication/login | Move on. Unless we can implement OAuth. |
| Last published 6+ months ago | Move on. Source is dormant. |
| Content is entirely irrelevant to Signal | Move on. Wrong domain. |
| Source is behind a hard paywall with no RSS summary | Move on. No content accessible. |

And these **instant qualifiers** (fast-track to scoring):

| Green Flag | Action |
|------------|--------|
| Official government RSS feed that returns 200 | Score immediately — likely Gold/Silver. |
| Established publication with working RSS | Score immediately. |
| Primary source (the org making announcements) | Score immediately — high authority. |

---

## Scoring Template

Use this template when evaluating a source:

```
Source: [Name]
URL: [RSS/Feed URL]
Category: [Signal section]
Date Tested: [YYYY-MM-DD]

1. Technical Reliability:  /5  [Notes: HTTP status, response time, format]
2. Content Relevance:      /5  [Notes: % relevant to Signal audience]
3. Update Frequency:       /5  [Notes: Publishing cadence]
4. Authority & Credibility:/5  [Notes: Source type, reputation]
5. Signal-to-Noise Ratio:  /5  [Notes: Substantive vs filler content]
6. Uniqueness:             /5  [Notes: What does this add that others don't?]

TOTAL:                     /30
TIER:                      [Gold/Silver/Bronze/Below threshold]
RECOMMENDATION:            [Add/Keep/Probation/Replace/Disable]
```

---

## Status Field Behaviour in Pipeline

The `status` field in `sources.yaml` now controls whether a feed is fetched:

| Status | Pipeline Behaviour |
|--------|-------------------|
| `active` | Fetched every run. Full participation. |
| `probation` | Fetched every run but flagged in logs. Reviewed after 14 days. |
| `disabled` | **Skipped entirely.** Not fetched. Zero resource cost. |

This means:
- Broken feeds should be set to `status: disabled` (not deleted) so we retain the metadata for future reference
- Replacement feeds are added as new entries with `status: active`
- The `notes` field should document why a source was disabled and when

---

## Review Cadence

| Trigger | Action |
|---------|--------|
| New source candidate identified | Score against rubric before adding |
| Source fails 3 consecutive runs | Move to `probation`, investigate |
| Source fails 7 consecutive runs | Move to `disabled`, find replacement |
| Monthly review (1st of month) | Check all `probation` sources, promote or disable |
| Quarterly review | Re-score all sources, prune redundancy |

---

## Applying to Policy Signal (Section 8)

For the Australian Government Policy section specifically, ideal sources must:

1. **Be official** — direct from the government body, not media interpretation
2. **Publish policy/regulatory content** — not internal operations or HR
3. **Affect business leaders** — regulation, legislation, compliance, incentives
4. **Have working RSS** — many government sites have broken or removed feeds
5. **Update when there's news** — event-driven is fine; dormancy is not

When a government RSS feed dies, the replacement search order is:
1. Check if the department has a new RSS URL (site redesigns often move feeds)
2. Check if there's an alternative official feed (e.g., minister's site vs department site)
3. Check if a credible policy publication covers the same ground (e.g., The Mandarin, InnovationAus)
4. Consider web scraping as last resort (adds maintenance burden — score accordingly)

---

*This document is the single source of truth for source curation decisions in the Signal pipeline.*
