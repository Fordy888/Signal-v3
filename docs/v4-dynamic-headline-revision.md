# DTL Signal v4 — Dynamic Headline Revision

**Starting production commit:** `6c39f001c256c8d401f34cfbbdaa23ce5041b24a`
**Context read before work:** `AGENTS.md`, `SIGNAL_CONTEXT.md`, `CONNECTOR_MANIFEST.md`, `EDITORIAL.md`
**Status:** Design and proof work only; live v4 remains unchanged

## The problem

The current middle of v4 exposes the structure of Signal’s reasoning rather than the result of that reasoning. Labels such as `VISUAL SIGNAL`, `EXECUTIVE READ`, `INTERPRETATION`, `WHAT CHANGED?`, `EXECUTIVE ACTION / WATCH` and `COUNTER-SIGNAL` tell the reader which internal method is being used. They do not tell the reader what is changing in business.

The affected example also relies on technical shorthand—CRM, UI, SoR, agentic security architecture and production-data measurements—before the commercial point becomes clear. Evidence may be technical, but Signal’s perspective must be understandable without technical expertise.

## Locked editorial test

Every visible section must be:

| Test | Requirement |
|---|---|
| **Clear** | The business point is understood on the first pass. |
| **Clever** | The framing helps the reader see the issue differently without forced wordplay. |
| **Balanced** | The opportunity, limitation and evidence that could change the view remain visible. |
| **Commercial** | Technical developments are translated into consequences for decisions, customers, people, operations, risk or value. |

> **Say something. Illuminate something. Challenge something.**

## Reader-facing architecture

Quiet utility labels may remain as wayfinding, but the dynamic headline immediately beneath each label must carry the business judgement.

| Current treatment | Revised utility label | Dynamic headline job |
|---|---|---|
| VISUAL SIGNAL | **THE SHIFT** | State the pattern compressed by the visual evidence. |
| EXECUTIVE READ / INTERPRETATION | **WHY IT MATTERS** | Translate the evidence into plain commercial meaning. |
| WHAT CHANGED? | **WHAT CHANGED** | State how the position moved in reader language, not methodology language. |
| EXECUTIVE ACTION / WATCH | **WHAT TO DO NOW** | Introduce one to three active, separately headlined responses. |
| COUNTER-SIGNAL | **THE OTHER SIDE** | State the strongest credible limitation or opposing explanation. |
| What to Watch | **WATCH FOR THIS** | Name the observable developments that would confirm or weaken the view. |

## Non-negotiable reader rules

Internal source IDs such as `S01`, `S02` and `S03` must never appear in reader-facing copy. Acronyms and specialist terms must be removed, expanded or translated when they are not essential. Source traceability stays in the structured plan and linked evidence, not in the prose.

The revision must preserve the existing FOUNDER’S NOTE, evidence links, action colours, REMEMBER THE WORLD, Daily Dad Joke, counter-evidence, memory and production release gates. It is a change to reader clarity—not a reduction in editorial rigour.

## Structured headline contract

The judgement plan will carry the following reader-facing fields so the renderer never has to invent a generic headline:

| Section | Structured field | Limit | Requirement |
|---|---|---:|---|
| WHY IT MATTERS | `interpretation_headline` | 10 words | State the commercial consequence of the collective evidence. |
| WHAT CHANGED | `what_changed.headline` | 10 words | State how the position moved; never describe the methodology. |
| WHAT TO DO NOW | `executive_actions[].headline` | 6 words | Use an active, specific response—not ACT, WATCH or OPPORTUNITY alone. |
| Action body | `executive_actions[].instruction` | 20 words | Explain the practical move or watch condition in plain language. |
| THE OTHER SIDE | `counter_signal.headline` | 10 words | State the strongest credible constraint or alternative explanation. |
| WATCH FOR THIS | `executive_read.watch_headline` | 10 words | Name the observable proof point that matters next. |

The Visual Signal already has a dynamic `title`; its utility label changes from `VISUAL SIGNAL` to `THE SHIFT`, and the planner must write the title as a business change rather than a chart description.

## Plain-business-language gate

Reader-facing judgement fields will fail validation if they contain internal source IDs or unexplained implementation shorthand. The first blocked terms are `S01`-style evidence IDs, `SoR`, `CRM`, `UI`, `API`, `LLM`, `RAG`, `MCP`, `GPU`, `ERP`, `SaaS` and `agentic`. `AI` remains permitted because it is the product’s established lens; every other necessary specialist term must be written out and explained through its business consequence.

This gate applies to dynamic headlines, interpretation, What Changed explanation, action headlines and instructions, Counter-Signal, What to Watch and the FOUNDER’S NOTE. Evidence rows may retain an essential technical fact, but their headline must remain commercially clear and the surrounding judgement must translate it.

## Example translation of the rejected section

| Utility label | Dynamic headline | Reader job |
|---|---|---|
| **THE SHIFT** | **AI is moving from the screen into the work** | Compress the four technical data points into one understandable pattern. |
| **WHY IT MATTERS** | **The advantage now comes from redesigning the work** | Explain that access is common; workflow judgement is becoming scarce. |
| **WHAT CHANGED** | **This is no longer a pilot story** | Show that independent production evidence has moved the position forward without exposing `S01 / S02 / S03`. |
| **WHAT TO DO NOW** | **Map the work AI can already touch** | Turn the insight into a bounded executive response. |
| **THE OTHER SIDE** | **The software giants still control the gates** | Preserve the commercial constraint and avoid overclaiming displacement. |
| **WATCH FOR THIS** | **Look for proof beyond developer teams** | State the observable test that would strengthen the view. |

This is the target tone: direct enough to scan, intelligent enough to reward attention and balanced enough to trust.

## Exact proof and desktop review — 1 September 2026

The deterministic Edition 0044 proof renders the new middle hierarchy without changing THE ONE THING, FOUNDER'S NOTE, evidence links, colour navigation, Daily Dad Joke or footer. The visible sequence is now THE SHIFT → WHY IT MATTERS → WHAT CHANGED → WHAT TO DO NOW → THE OTHER SIDE → WATCH FOR THIS.

Desktop inspection confirms that every utility label is immediately followed by a larger declarative headline. The three actions are independently scannable, each with a colour direction, active headline and one-sentence instruction. No `S01`-style source IDs appear in reader-facing prose, and the interpretation explains the commercial point without requiring knowledge of system architecture or software shorthand.

The deliberately retired Moorea candidate does not render. This is the correct failure posture: REMEMBER THE WORLD is omitted rather than repeating yesterday's photograph.

The exact no-send proof is `data/v4-dynamic-headline-proof.html`. All 56 Signal tests pass, including reader-language rejection, image-identity repetition, edition/date approval, provider-backed image-memory recovery and proof exclusion. Desktop rendering is internally approved for the next proof stage; email-client approval remains outstanding.

At 390 pixels, the masthead, four-colour rhythm, THE ONE THING, FOUNDER'S NOTE, three-part colour navigation and evidence cards remain within the viewport with no horizontal overflow. The lower dynamic sections use the same table-safe column geometry verified on desktop. The proof SHA-256 is `b7699cb766896c363c487dcb9a9b635684a28be16803c1393883dab2100611d3`; `git diff --check` is clean.

The current live v4 renderer has not been changed. This proof is ready for one-recipient delivery to Fordy only.

## Proof delivery

The checksum-locked proof was sent only to `paul.ford@gmail.com` from `DTL Signal <signal@signal.dtlc.ai>` with subject `[PROOF] DTL Signal v4 | Dynamic Headline Revision`. Resend ID: `3c3d64b1-9189-423d-b0cc-7bf59535636c`. Provider status reached `opened`.

This delivery is a reader-experience proof, not a production activation. The live renderer remains unchanged pending Fordy's explicit approval of the revised middle section and the omit-rather-than-repeat photography behaviour.

## New REMEMBER THE WORLD candidate

The replacement candidate is `Incense in Vietnam` by Trần Tuấn Việt (`Trantuanviet`), photographed on 14 September 2022 in Quang Phu Cau village outside Hanoi, Vietnam. It shows rose-coloured incense sticks set out to dry around a working farmer. Wikimedia Commons awarded it first place in Picture of the Year 2023 and records it as the photographer's own work.[1]

The original file page publishes the photograph under Creative Commons Attribution-ShareAlike 4.0, which permits commercial sharing with attribution, a licence link and disclosure of modifications.[1] Signal will use an unaltered 1,280-pixel derivative, credit the photographer, link to the original file page and link to the licence.

Visually, the image provides the required grounding through art and human craft: a real person, a living cultural practice, an immediately legible composition and strong colour without relying on nature spectacle. It is not the Moorea whale and does not match any existing delivered image identity.

The complete Edition 0044 proof now includes this image at the full Signal text-column width. Desktop inspection confirms the strong magenta composition aligns with the surrounding copy, the farmer remains the clear human focal point, and the quiet caption/attribution sits directly underneath without disturbing the final Daily Dad Joke and footer sequence. The approved dynamic-headline middle is unchanged.

The complete proof SHA-256 is `56226e2f1f955cc137d9b621b07504732390924d25dcc1cada87797e91744f35`. All 57 Signal tests pass, including the new human-craft category, exact edition/date approval and validation against the prior Moorea history.

Mobile tiles 1–2 at 390 pixels confirm the masthead, four-colour rhythm, THE ONE THING and FOUNDER'S NOTE retain hierarchy without overflow. The three-part YOUR SIGNAL AT A GLANCE panel remains one compact row; each colour block carries a text label and meaning, so navigation does not depend on colour alone.

Mobile tiles 3–4 confirm action labels, pillar names, dynamic evidence headlines, facts and source links wrap cleanly. The hierarchy remains legible without requiring the reader to decode specialist terminology; long source names and commercial metrics stay within the text column.

Mobile tiles 5–6 confirm THE SHIFT table remains readable at 390 pixels and the declarative headline carries the pattern before the data. WHY IT MATTERS follows as one clear heading and plain commercial interpretation, with no stacked EXECUTIVE READ / INTERPRETATION labels or horizontal overflow.

Mobile tiles 7–8 confirm WHAT CHANGED leads with the reader-relevant headline rather than source codes, and WHAT TO DO NOW separates three active responses into scannable headline/instruction pairs. THE OTHER SIDE begins with the actual balancing argument, preserving challenge without exposing methodology language.

Mobile tiles 9–10 confirm WATCH FOR THIS remains clear and the new Quang Phu Cau photograph scales to the full mobile text column without crop distortion or overflow. The human focal point remains visible; photographer, Wikimedia source and CC BY-SA 4.0 attribution stay legible and quiet. The Daily Dad Joke and minimal footer retain their locked final order.

Mobile tile 11 is empty trailing viewport only, confirming no hidden content, overflow or duplicate footer follows the intended close. The complete proof is ready for one-recipient inbox delivery.

The checksum-locked complete proof was sent only to `paul.ford@gmail.com` from `DTL Signal <signal@signal.dtlc.ai>` with subject `[PROOF] DTL Signal v4 | Complete Revision + Remember The World`. Resend ID: `f1bb18a2-f30f-4f5c-b0ab-56b43a9d7fe4`. The provider record confirms the intended sender and sole recipient; status reached `opened`.

Production remains unchanged. Fordy's explicit approval of the Quang Phu Cau image is the final proof gate before the revision can enter the guarded release path.

## Final approval and release freeze

Fordy approved the complete proof as `100% perfect` on 1 September 2026. The approved editorial and visual system is now frozen: dynamic section headlines, plain commercial language, structured action headlines, provider-backed non-repetition and the Quang Phu Cau REMEMBER THE WORLD photograph. No further editorial or visual changes are authorised within this release.

The frozen HTML SHA-256 remains `56226e2f1f955cc137d9b621b07504732390924d25dcc1cada87797e91744f35`. The complete suite passes 57 tests. Clean-diff, credential-pattern, required-fixture and reader-visible legacy-label gates pass. The proof contains Quang Phu Cau and no Moorea reference.

An isolated worktree created from production commit `6c39f001c256c8d401f34cfbbdaa23ce5041b24a` plus only the staged release patch reproduced the same proof checksum and passed all 57 tests. This confirms the approved result depends only on Git-contained files, not local ignored artefacts.

## References

[1]: https://commons.wikimedia.org/wiki/File:Incense_in_Vietnam.jpg "Wikimedia Commons — Incense in Vietnam by Trantuanviet"
