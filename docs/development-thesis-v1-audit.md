# DTL Signal — Development Thesis V1 Architecture Audit

**Baseline:** Edition 0038 Current  
**Production posture:** unchanged until Fordy approves the 0038 comparison  
**North star:** DTL Signal does not compete on more information. It competes on better judgement.

## Executive finding

Signal already contains early versions of three thesis ideas: a top-level thesis sentence, a three-part item structure, and a personality layer through the Founder’s Note. The gap is not basic capability. It is **explicit judgement architecture**: Signal does not yet store positions, classify new evidence against them, expose fact-versus-reasoning boundaries clearly enough, test its own conclusion, or compress a pattern into a governed visual object.

The smallest responsible enhancement is an **optional judgement-planning stage between scoring and synthesis**. It produces a structured, testable editorial plan. The existing synthesis, delivery, subscriber, QA, attribution and visual systems remain intact.

| Principle | What exists now | Gap | Smallest compatible change |
|---|---|---|---|
| **THE ONE THING** | “Today’s Signal” provides one thesis sentence near the top. | It is generated inside the same free-form HTML call as everything else and has no explicit evidence basis or prioritisation record. | Generate a structured `one_thing` object before HTML synthesis, including conclusion, evidence references, confidence and business implication. Render it first. |
| **Evidence / Interpretation / DTL View** | Each item uses “What happened / Why it matters / Signal.” | The boundaries are implied, not governed. “What happened” can still absorb interpretation, and no structured provenance connects the conclusion to source items. | Replace the visible labels with **EVIDENCE / INTERPRETATION / DTL VIEW** in the enhanced prompt. The planning object records source URL(s), evidence summary, interpretation and DTL judgement separately. |
| **WHAT CHANGED?** | `history.py` suppresses repeated URLs for 72 hours. | This is deduplication, not memory. Signal stores no durable positions or evidence movement. | Add a portable Signal Memory store containing positions and evidence events. Classify each edition-level update as Strengthens, Weakens, Confirms, Challenges or No Material Change. Persist only after successful delivery. |
| **VISUAL SIGNAL** | The Signal Strength Gauge is an optional post-synthesis visual interaction object. | It measures reader feedback rather than compressing intelligence. | Reuse the same feature-flag and deterministic-injection pattern. A planner may propose one governed visual specification; a renderer creates a compact table/tension/trend object. No eligible evidence means no visual. |
| **COUNTER-SIGNAL** | “What to Watch” identifies developments to monitor. | It does not deliberately challenge the principal conclusion or state what would falsify it. | Add one structured counter-signal with alternative explanation, evidence to watch and effect on confidence. Render after the visual/interpretation. |
| **HUMAN SIGNAL** | A generated Founder’s Note adds operator voice and a fallback library prevents hard failure. | There is no small, deliberately light footer-level human moment; generated personality can compete with the intelligence. | Add a sibling post-synthesis Dad Joke stage using a governed library, rotation history and repetition protection. No joke generation. Place near the bottom after substantive intelligence. |

## Proposed enhanced intelligence sequence

1. Existing source fetch and scoring remain unchanged.
2. **Judgement Planner** receives scored items plus prior Signal Memory and returns structured JSON.
3. Existing synthesis receives the scored items plus the validated judgement plan and renders the enhanced email.
4. Deterministic post-processors inject an eligible Visual Signal and one governed Dad Joke.
5. Existing QA gains checks for the required intelligence boundaries and governance rules.
6. Existing delivery, DTL PL attribution and receipts remain unchanged.
7. Signal Memory updates only after at least one successful production delivery.

## Portable intelligence object

The planning object will contain:

- `one_thing`: conclusion, evidence references, implication and confidence;
- `evidence_items`: source-backed evidence, interpretation and DTL view kept separately;
- `what_changed`: prior position, movement classification and explanation;
- `visual_signal`: eligibility, type, title and bounded rows;
- `counter_signal`: alternative explanation, evidence to watch and confidence effect;
- `executive_actions`: no more than three;
- `memory_update`: position ID, current thesis, confidence and supporting evidence IDs.

The object is framework-independent JSON. It does not know about Resend, Render, subscriber APIs or HTML components.

## Edition 0038 acceptance method

The current delivered/proof HTML remains the control. The seven selected Edition 0038 source signals become a fixed evidence fixture. The enhanced path runs that same intelligence through the structured judgement architecture. Production remains off through a default-disabled feature flag.

The comparison will test whether the enhanced edition is:

| Test | Acceptance question |
|---|---|
| Faster | Can the reader identify the one important conclusion in 20 seconds? |
| Clearer | Are sourced facts visibly distinct from interpretation and DTL judgement? |
| Connected | Does the edition explain whether evidence changes an existing position? |
| Rigorous | Does it state a credible counter-signal and confidence implication? |
| Compressed | Does any visual object replace explanation rather than decorate it? |
| Memorable | Is the core judgement easier to recall than a list of stories? |
| Human | Does the ending produce the intended eye roll and slight smile without weakening trust? |

## Non-goals for this release

The work will not rebuild source ingestion, scoring, delivery, subscribers, DTL PL, the current production prompt or email identity. It will not introduce a database, dashboard, real-time trend engine, personalised editions or an ungoverned humour generator. Durable production memory can later move from the portable JSON contract to persistent storage without changing the judgement model.
