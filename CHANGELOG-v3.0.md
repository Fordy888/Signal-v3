# Signal v3.0 — Changelog

**Date:** 4 July 2026  
**Summary:** Expanded to 100+ sources, added Section 8 (Policy Signal), moved DTLc.ai's Take to Section 9, fixed double-footer bug.

---

## 1. Sources Expanded: 55 → 103 RSS Feeds + HackerNews

**File:** `config/sources.yaml`

### New Category: `australian_government_policy` (19 feeds)

These are the departments and agencies that directly make or enforce legislation affecting business leaders:

| # | Source | What They Control |
|---|--------|-------------------|
| 1 | DISR — Dept of Industry, Science & Resources | National AI Centre, Safe & Responsible AI framework, digital economy strategy |
| 2 | Treasury Ministers | Tax policy, economic regulation, fintech, digital assets |
| 3 | Attorney-General's Dept (Ministers) | Privacy Act reform, AI liability, data protection, digital identity |
| 4 | ACCC | Digital platform regulation, merger reform, AI in advertising |
| 5 | ASIC | AI in financial services, crypto regulation, corporate governance |
| 6 | DTA — Digital Transformation Agency | Government AI adoption, digital identity, tech standards |
| 7 | OAIC — Privacy Commissioner | Privacy regulation, data breach notification, AI & personal info |
| 8 | eSafety Commissioner | Online safety regulation, AI-generated content, deepfakes |
| 9 | RBA — Media Releases | Monetary policy, CBDC, payments system regulation |
| 10 | RBA — Speeches | Forward guidance on fintech, digital payments |
| 11 | APRA | AI risk in banking/insurance, operational resilience |
| 12 | Productivity Commission | AI & workforce productivity reviews, regulation reform |
| 13 | Parliament — Senate New Inquiries | New committee inquiries into AI, tech, business regulation |
| 14 | Parliament — Senate Reports Tabled | Final reports — the actual recommendations that become policy |
| 15 | Parliament — Joint Committee Inquiries | Joint inquiries (often where AI/tech regulation starts) |
| 16 | ASD/ACSC — Cyber Security Centre | Cyber threat alerts, critical infrastructure, AI security |
| 17 | Dept of Employment & Workplace Relations | AI & workforce legislation, skills policy, Fair Work |
| 18 | Dept of Finance (Ministers) | Government procurement (AI contracts), digital investment |
| 19 | The Mandarin | Public sector + policy analysis — catches regulatory intent early |

### Additional International Sources Added

- Anthropic News
- Apple Machine Learning Research
- Microsoft AI Blog
- Nvidia AI Blog
- Meta AI Blog
- Google Cloud Blog
- a16z (Andreessen Horowitz)
- Latent Space (AI Engineering)
- Lenny's Newsletter
- Ben's Bites
- VentureBeat
- Deloitte Insights
- Bain & Company Insights
- AWS Enterprise Strategy Blog
- CIO Dive
- InnovationAus (moved to AU Gov Policy)

### Category Distribution (103 feeds)

| Category | Count |
|----------|-------|
| ai_market_signals | 28 |
| australian_government_policy | 19 |
| strategy_decision_making | 12 |
| australian_business | 9 |
| geopolitics | 8 |
| venture_capital | 8 |
| opportunity_radar | 7 |
| cultural_economic_shifts | 7 |
| tactical_ai_stack | 4 |
| threat_detection | 2 |

---

## 2. Section 8: Policy Signal (NEW)

**Files:** `prompts/synthesis_prompt.md`, `config/context.yaml`

### Architecture Change

Signal now has **9 sections** (was 8):

1. What's Lighting Up in AI
2. Opportunity Radar
3. Products & Suppliers
4. Threat Detection & Security
5. People in AI — Who's Shaking It Up?
6. Tactical AI Stack — Agentic
7. Cultural Shifts — Global Thinking
8. **Policy Signal** ← NEW
9. DTLc.ai's Take ← moved from Section 8

### Section 8 Rules (hard-coded in prompt + context.yaml)

- **Max 2 items per edition** — hard cap, no exceptions
- **Default is quiet** — most days Canberra isn't doing anything a CEO needs to act on
- **Australian Federal Government only** — no state/territory
- **Only items that directly affect business leaders**
- **No routine ministerial fluff**
- **No appointments**
- **No generic speeches** unless they signal real policy direction
- **No filler** just to populate the section

### Status Indicators

- **WATCH** = worth monitoring — policy in development or consultation phase
- **ACT** = deadline, legislation, enforcement, compliance issue or imminent business impact

### Empty State

> Policy Signal: Quiet today — no Australian federal policy or regulatory movement requiring business leader attention.

### Format

Same structured format as other sections:
- Headline
- What happened
- Why it matters
- Signal

---

## 3. Section 9: DTLc.ai's Take

Moved from Section 8 to Section 9. Remains the capstone — strategic interpretation that ties everything together. Added explicit rule: **must always contain a real strategic interpretation, not placeholder/template language.**

---

## 4. Bug Fixes

### Double-Footer Bug (FIXED)

**File:** `src/synthesis.py`

**Root cause:** When the LLM successfully generated the full email including footer, but the `has_closing` check failed (e.g., the closing `</table>` wasn't in the last 200 chars), the auto-repair code would append a second footer on top of the one the LLM already generated.

**Fix:** Added `if "Signal learns" not in html:` check before appending the fallback footer. The footer is only appended if it doesn't already exist in the output.

### "// reply to refine" Hallucination (FIXED)

**File:** `src/synthesis.py`

**Fix:** Added `html = html.replace("// reply to refine", "")` as a safety strip before returning the final HTML.

### Quality Gate Updated

**File:** `src/main.py`

Updated the delivery quality gate to check for Section 9 (DTLc.ai's Take) instead of Section 8, matching the new architecture.

---

## 5. Files Changed

| File | Change |
|------|--------|
| `config/sources.yaml` | Rewritten — 103 RSS feeds (was 55) |
| `config/context.yaml` | Added `policy_signal` cap + `policy_signal_rules` block |
| `prompts/synthesis_prompt.md` | v3.0 — 9 sections, Policy Signal added, numbering updated |
| `src/synthesis.py` | Double-footer fix, Section 9 references, "reply to refine" strip |
| `src/main.py` | Quality gate updated to Section 9 |

---

## 6. Deployment

To deploy these changes:

```bash
cd Signal-main
git add -A
git commit -m "v3.0: 100+ sources, Section 8 Policy Signal, double-footer fix"
git push origin main
```

The next scheduled run will automatically pick up the new sources and section architecture.

---

## 7. What to Watch

- **First few editions:** Monitor that Policy Signal defaults to "Quiet today" on most days. If it's firing every day, the scoring threshold may need tightening for `australian_government_policy` category items.
- **Feed validation:** Some government RSS URLs may need verification on first fetch (particularly eSafety, ASIC, APRA). The pipeline will log warnings for any 404/403 responses.
- **Holly's context:** `config/context_holly.yaml` still uses the older section map in `section_caps`. This won't break anything (the synthesis prompt is authoritative), but should be aligned when convenient.
