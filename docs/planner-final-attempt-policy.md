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

## Failures that remain hard holds

The safety layer must not invent missing evidence, numeric figures, classifications, source links, internal position movement, minimum-length Founder’s Note content or required sections. Unknown sources, Newsroom/Focus overlap, fewer than six AI-in-business items, missing AI-business connections, non-numeric Focus figures without eligible same-source evidence and other semantic failures continue to abort the edition.

The purpose of normalisation is to prevent valid substance from failing on superficial length—not to convert an incomplete plan into a publishable one.
