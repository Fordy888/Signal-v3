# DTL Signal Planner — Final-Attempt Normalisation Policy

**Introduced:** 3 September 2026

The live release canary exposed three serial final-attempt failures: an overlong Focus defining figure, a zero-action plan and an overlong AI-in-business connection. All three runs correctly aborted at 0/0 delivery, but the pattern showed that bounded output needed one coherent final safety layer rather than individual reactive patches.

## Safe repair boundary

The third and final planner attempt may deterministically shorten presentation copy that already contains the required substance. This applies to Newsroom headlines and evidence, AI-business connection explanations, Focus entities, defining-figure labels, Focus meanings, interpretation, Founder’s Note maximum length, counter-position copy, executive-action copy and watch copy. More than three otherwise valid executive actions may be reduced to the first three.

A missing Focus defining figure is handled separately. The final attempt may recover one only from the single source ID already selected for that Focus item, using an explicit numeric expression in that source’s evidence, title or scoring reason. The source ID and classification cannot change, and the recovered label records its source ID. If the selected source has no eligible figure—or the item cites multiple or ambiguous source records—the edition remains held.

| Invariant | Rule |
|---|---|
| Source identity | Source IDs are never added, removed or changed by word-bound normalisation. |
| Defining figure | Focus-number trimming must retain a numeric token and its nearby unit. |
| Missing figure | Recovery is allowed only from the same unambiguous source record; no cross-source search or invented number. |
| Content mix | `AI_BUSINESS` and `MAJOR_BUSINESS` classifications are never changed. |
| Business meaning | AI-business connections and other copy are trimmed from the end; the substantive point must lead. |
| Action integrity | Existing valid actions are preserved; a zero-action fallback is bound to selected source evidence. |
| Reader language | Internal codes and unexplained technical shorthand remain hard failures. |
| AI Focus completion | Visible AI subject and business consequence may be copied only from the same selected source; no cross-source or invented wording. |

## Failures that remain hard holds

The safety layer must not invent missing evidence, numeric figures, classifications, source links, internal position movement, minimum-length Founder’s Note content or required sections. Unknown sources, any deviation from the preallocated exact 3/2 section mix, Newsroom/Focus overlap, missing AI-business connections, non-numeric Focus figures without eligible same-source evidence and other semantic failures continue to abort the edition.

The purpose of normalisation is to prevent valid substance from failing on superficial length—not to convert an incomplete plan into a publishable one.

## Upstream numeric eligibility

Focus-number safety begins before the model is called. Each supplied evidence record is scanned deterministically for an explicit business figure such as currency, percentage, rate, multiple, jobs, roles, workers, employees, customers, firms, companies or points. A bare year or an unquantified claim does not qualify.

Eligible records are annotated with `focus_number_eligible: true` and a compact `focus_number_candidate` copied from that same source. The planner receives the complete eligible source-ID list and may cite only those IDs in `focus_numbers`. If fewer than five distinct eligible records exist, Signal holds before model generation. Validation independently rejects any Focus source outside the verified pool, even if generated copy happens to contain a digit.

Same-source final-attempt recovery remains a secondary safeguard. It cannot make an ineligible source eligible and cannot transfer a figure between sources.

## Same-source AI Focus copy completion

An independently verified `AI_BUSINESS` Focus source can still be written too vaguely by the model, leaving the visible entity, figure and meaning without both an explicit AI subject and a concrete business consequence. On the third and final attempt only, Signal may replace that item’s `meaning` with one concise sentence copied from the same selected source record when the sentence itself contains both requirements.

The repair does not change the source ID, defining figure, classification or source link. It rejects internal source IDs, never searches another source, never touches `MAJOR_BUSINESS` items and remains a hard hold when the selected source contains no clean qualifying sentence.

## Independent content-mix classification

The planner’s own `mix_classification` is descriptive, not authoritative. Before the model is called, Signal classifies each evidence record from its supplied title, evidence and scoring reason.

| Verified class | Evidence requirement |
|---|---|
| `AI_BUSINESS` | An explicit AI subject plus a concrete commercial, customer, workforce, operating, financial, risk or value connection. |
| `MAJOR_BUSINESS` | Commercially material non-AI evidence with no AI-led subject. |

The pipeline allocates source IDs to sections before the model is called. Focus receives three independently verified `AI_BUSINESS` sources and two independently verified `MAJOR_BUSINESS` sources that also contain pre-verified numeric evidence. Newsroom receives three remaining AI-business and two remaining major-business sources. The model may write only from its preallocated section IDs; validation rejects substitution, cross-section movement or relabelling. The pre-planning gate therefore requires at least six AI-business and four major-business sources, including three AI-business and two major-business numeric candidates for Focus.
