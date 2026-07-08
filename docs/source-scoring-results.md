# Source Scoring Results — 9 July 2026

Applying the Signal Source Quality Scoring Criteria to replacement candidates for the broken government policy feeds.

---

## NEW CANDIDATES (Scored)

### 1. Tech Council of Australia

```
Source: Tech Council of Australia
URL: https://techcouncil.com.au/feed/
Category: government_policy (tech policy advocacy)
Date Tested: 2026-07-09

1. Technical Reliability:  5/5  [200 OK, fast response, standard WordPress RSS]
2. Content Relevance:      4/5  [Tech policy, workforce, regulation — directly relevant to AI/business leaders]
3. Update Frequency:       3/5  [Weekly-ish. Last build 2 Jul 2026. Event-driven.]
4. Authority & Credibility:4/5  [Peak industry body. Advises government on tech policy. Well-known.]
5. Signal-to-Noise Ratio:  4/5  [Mostly policy positions, research reports, submissions. Low filler.]
6. Uniqueness:             4/5  [Only source for industry body perspective on AU tech policy.]

TOTAL:                     24/30
TIER:                      Silver
RECOMMENDATION:            ADD as active
```

---

### 2. Government News

```
Source: Government News
URL: https://www.governmentnews.com.au/feed/
Category: government_policy (public sector digital transformation)
Date Tested: 2026-07-09

1. Technical Reliability:  5/5  [200 OK, fast response, standard WordPress RSS]
2. Content Relevance:      3/5  [Covers digital government, procurement, policy — ~50% relevant to business leaders]
3. Update Frequency:       5/5  [Daily. Last build 8 Jul 2026. Very active.]
4. Authority & Credibility:3/5  [Established trade publication for public sector. Known in gov circles.]
5. Signal-to-Noise Ratio:  3/5  [Mixed — some internal gov operations, some policy with business impact]
6. Uniqueness:             4/5  [Fills the DTA/digital government gap. No other source covers this niche.]

TOTAL:                     23/30
TIER:                      Silver
RECOMMENDATION:            ADD as active
```

---

### 3. The Conversation AU — Politics

```
Source: The Conversation AU — Politics
URL: https://theconversation.com/au/politics/articles.atom
Category: government_policy (academic policy analysis)
Date Tested: 2026-07-09

1. Technical Reliability:  5/5  [200 OK, fast response, standard Atom feed]
2. Content Relevance:      3/5  [Broad politics — some policy/regulation relevant, some electoral/social]
3. Update Frequency:       5/5  [Multiple times daily. Very active.]
4. Authority & Credibility:4/5  [Academic experts writing for general audience. Peer-reviewed institution.]
5. Signal-to-Noise Ratio:  3/5  [Mixed — need LLM scoring to filter. Electoral politics vs business-relevant policy.]
6. Uniqueness:             3/5  [Provides analytical depth that news sources lack. Complements The Mandarin.]

TOTAL:                     23/30
TIER:                      Silver
RECOMMENDATION:            ADD as active
```

---

### 4. Parliament — Joint Inquiries (House)

```
Source: Parliament — Joint Inquiries (House)
URL: https://www.aph.gov.au/house/rss/joint_inquiries
Category: government_policy (parliamentary inquiries)
Date Tested: 2026-07-09

1. Technical Reliability:  5/5  [200 OK, valid RSS, accessible from US infrastructure]
2. Content Relevance:      5/5  [Joint committee inquiries — directly affects business regulation]
3. Update Frequency:       3/5  [Event-driven. New inquiry Jul 5 2026. Acceptable for policy.]
4. Authority & Credibility:5/5  [Primary source — Parliament of Australia itself.]
5. Signal-to-Noise Ratio:  5/5  [Every item is a new inquiry. Zero filler.]
6. Uniqueness:             5/5  [Only source for this information. Irreplaceable.]

TOTAL:                     28/30
TIER:                      Gold
RECOMMENDATION:            ADD as active (REPLACES broken old URL)
```

---

### 5. APRA (corrected URL)

```
Source: APRA — Australian Prudential Regulation Authority
URL: https://www.apra.gov.au/rss.xml
Category: government_policy (financial regulation)
Date Tested: 2026-07-09

1. Technical Reliability:  5/5  [200 OK, valid RSS, accessible from US infrastructure]
2. Content Relevance:      4/5  [Financial regulation, prudential standards — relevant to business leaders in finance/insurance]
3. Update Frequency:       3/5  [Event-driven. Statistical publications, policy papers.]
4. Authority & Credibility:5/5  [Primary source — the actual regulator.]
5. Signal-to-Noise Ratio:  3/5  [Mix of statistical data releases and policy. Some routine data.]
6. Uniqueness:             5/5  [Only source for APRA announcements.]

TOTAL:                     25/30
TIER:                      Gold
RECOMMENDATION:            ADD as active (REPLACES broken /news-and-publications/rss URL)
```

---

### 6. Parliament — House Inquiries

```
Source: Parliament — House Inquiries
URL: https://www.aph.gov.au/house/rss/house_inquiries
Category: government_policy (parliamentary inquiries)
Date Tested: 2026-07-09

1. Technical Reliability:  5/5  [200 OK, valid RSS structure]
2. Content Relevance:      5/5  [House committee inquiries — regulation, legislation]
3. Update Frequency:       2/5  [Currently empty channel. May be seasonal/event-driven.]
4. Authority & Credibility:5/5  [Primary source — Parliament of Australia.]
5. Signal-to-Noise Ratio:  5/5  [When items appear, they are all inquiries. Zero filler.]
6. Uniqueness:             4/5  [Complements Joint Inquiries feed. Some overlap with Senate inquiries.]

TOTAL:                     26/30
TIER:                      Gold
RECOMMENDATION:            ADD as active (new source, complements existing Senate feeds)
```

---

## BROKEN SOURCES (Scored for record)

### InnovationAus (existing — now broken)

```
Source: InnovationAus
URL: https://www.innovationaus.com/feed/
Category: government_policy
Date Tested: 2026-07-09

1. Technical Reliability:  1/5  [403 Forbidden — blocks all automated access including browser UA]
2. Content Relevance:      5/5  [Was excellent — AU tech policy, regulation, innovation]
3. Update Frequency:       N/A  [Cannot access]
4. Authority & Credibility:4/5  [Established specialist publication]
5. Signal-to-Noise Ratio:  N/A  [Cannot access]
6. Uniqueness:             3/5  [Tech Council + The Mandarin now cover similar ground]

TOTAL:                     N/A (auto-disqualified — Technical Reliability = 1)
TIER:                      Below threshold
RECOMMENDATION:            DISABLE — blocks all automated access
```

---

### DISR / Department of Industry

```
Source: DISR — Department of Industry, Science and Resources
URL: https://www.industry.gov.au/news.xml
Category: government_policy
Date Tested: 2026-07-09

1. Technical Reliability:  1/5  [Timeout/000 — geo-blocks non-AU IP addresses]
2-6: N/A (auto-disqualified)

TOTAL:                     N/A
TIER:                      Below threshold
RECOMMENDATION:            DISABLE — inaccessible from Render (US-hosted)
```

---

## SUMMARY TABLE

| Source | Score | Tier | Action |
|--------|-------|------|--------|
| Parliament — Joint Inquiries | 28/30 | Gold | ADD (replaces broken URL) |
| Parliament — House Inquiries | 26/30 | Gold | ADD (new) |
| APRA (corrected URL) | 25/30 | Gold | ADD (replaces broken URL) |
| Tech Council of Australia | 24/30 | Silver | ADD (new) |
| Government News | 23/30 | Silver | ADD (new) |
| The Conversation AU — Politics | 23/30 | Silver | ADD (new) |
| InnovationAus | Disqualified | Below threshold | DISABLE |
| DISR | Disqualified | Below threshold | DISABLE |
| Treasury Ministers | Disqualified | Below threshold | DISABLE |
| Attorney-General's Dept | Disqualified | Below threshold | DISABLE |
| ACCC | Disqualified | Below threshold | DISABLE |
| ASIC | Disqualified | Below threshold | DISABLE |
| DTA | Disqualified | Below threshold | DISABLE |
| OAIC | Disqualified | Below threshold | DISABLE |
| eSafety | Disqualified | Below threshold | DISABLE |
| Productivity Commission | Disqualified | Below threshold | DISABLE |

---

## COVERAGE ANALYSIS

After applying these changes, the Policy Signal section will be fed by:

**Retained (already working):**
- The Mandarin (government news/policy)
- Parliament — Senate New Inquiries
- Parliament — Senate Reports Tabled
- RBA — Media Releases
- RBA — Speeches

**Fixed (URL corrected):**
- APRA (new URL: /rss.xml)
- Parliament — Joint Inquiries (new URL: /house/rss/joint_inquiries)

**Added (new sources):**
- Tech Council of Australia
- Government News
- The Conversation AU — Politics
- Parliament — House Inquiries

**Disabled (broken, no fix available):**
- InnovationAus, DISR, Treasury Ministers, AG Dept, ACCC, ASIC, DTA, OAIC, eSafety, Productivity Commission

**Net result:** 11 active policy sources (up from ~5 working + 12 broken = 5 effective). This is a significant improvement in both reliability and coverage breadth.
