# DTL Signal — Founder-Led Focus on the Numbers Revision

**Status:** APPROVED FOR BUILD

## Reader-facing sequence

The daily edition will retain the four-colour `THINK. DECIDE. LOOK UP. SMILE.` signature and then use this sequence:

| Order | Reader-facing element | Contract |
|---|---|---|
| 1 | **FOUNDER’S NOTE** | First substantive section; direct headline; approximately half the previous body length; inline `— Paul`. |
| 2 | **DTL SIGNAL NEWSROOM — READ THIS** | Exactly five big stories, each with a short lead-in, large headline, concise context and one source link. |
| 3 | **FOCUS ON THE NUMBERS** | Exactly five compact entries drawn from five different sources. |
| 4 | **WHY IT MATTERS** | One declarative commercial headline and concise interpretation. |
| 5 | **WHAT TO DO NOW** | One to three active, individually headlined responses. |
| 6 | **THE OTHER SIDE** | Credible constraint or counter-position. |
| 7 | **WATCH FOR THIS** | Observable proof points. |
| 8 | **REMEMBER THE WORLD** | Optional governed photograph; naturally brand-harmonious when an exceptional qualifying image allows it. |
| 9 | **DAD JOKE OF THE DAY** | Mandatory final content beat before the minimal footer. |

`THE ONE THING` and reader-facing `WHAT CHANGED` are removed completely. Position movement remains an internal Signal Memory input and must never be rendered as a reader section.

The ten Newsroom and Focus items must use ten distinct source records. The earlier `focus-on-the-numbers-v1` proof used exactly three `AI_BUSINESS` and two `MAJOR_BUSINESS` items per section; that 60/40 artefact remains frozen historical evidence and is not the current selection rule.

The current `ai-adoption-v1` contract requires every one of the ten core items to be about AI. Real-world `AI_ADOPTION` must dominate; `AI_INDUSTRY_IMPACT` is secondary and qualifies only when an industry development creates a direct practical business consequence. General business-only stories, passing AI mentions, hypothetical adoption, model gossip and technical theatre are excluded. The implementation currently requires at least eight adoption items and no more than two industry-impact items, with at least four adoption items in each section. That threshold is a conservative implementation interpretation to be tested in the fresh proof, not a claim of separate quota approval.

Newsroom `category` remains internal planning metadata. Machine keys such as `venture_capital`, `opportunity_radar` and `ai_market_signals` must never be shown to readers. A quiet action lead-in may be followed by a human editorial label, but machine-style underscore keys are omitted.

Every reader-facing headline must finish as a complete phrase. Final-attempt shortening may remove trailing words, but it must also remove dangling articles, prepositions, conjunctions, possessives or qualifiers such as `a`, `the`, `in`, `not`, `just`, `your` and `with`.

## Focus on the Numbers contract

Each of the five entries contains a company, organisation or named market; one defining number; and one short sentence explaining what changed and why it matters commercially.

| Field | Rule |
|---|---|
| `entity` | Recognisable company, organisation, person or market; maximum six words. |
| `number` | Exact defining figure containing at least one digit; maximum ten words. |
| `meaning` | Factual change plus plain commercial meaning; maximum 26 words. |
| `source_ids` | One or more valid supplied source IDs supporting the figure. |

The five entries must be current, verifiable, prominent and collectively varied. Decorative statistics, unsupported comparisons, technical benchmarks with no commercial meaning and invented denominators are prohibited.

## Founder’s Note contract

The established founder format remains: `FOUNDER’S NOTE`, a direct headline, concise substantive commentary and an inline `— Paul`. The new body range is **45–90 words**, targeting approximately 60–80 words. The shorter note must still express judgement rather than summarise headlines.

## Photography colour-harmony contract

Signal’s four colours become a final selection preference for REMEMBER THE WORLD, never an alteration instruction. A qualifying original photograph may be tagged with a natural dominant colour family: `coral`, `amber`, `aqua`, `deep_teal` or `neutral`.

Artistic power, authenticity, commercial-use rights, exact provenance, subject/place alignment, issue-date validity and non-repetition remain hard gates. When several photographs pass those gates, Signal should prefer one that naturally harmonises with the brand and rotates the recently used dominant colour where practical. It must never tint, recolour or otherwise manipulate a photograph to force a match.

## Implementation boundary

| Layer | Change |
|---|---|
| Planner schema | Add `focus_numbers`; make `one_thing` and `visual_signal` unnecessary for the new revision; retain internal movement for memory. |
| Planner prompt | Require exactly five sourced business figures and the 45–90 word Founder’s Note. |
| Renderer | Lead with Founder’s Note; remove THE ONE THING and WHAT CHANGED; render the compact five-number block. |
| Production gate | Require new section markers and explicitly reject removed markers for the new revision. |
| Signal Memory | Continue recording position movement internally after successful subscriber delivery. |
| Photography governance | Validate and record the natural dominant colour family without modifying the image. |
| Weekly Wrap | No change; it remains on its separately approved route. |

## Release boundary

The new format must be built as a complete no-send proof, tested, and delivered only to `paul.ford@gmail.com` before production commit or Render activation. Edition 0045 must not be resent.
