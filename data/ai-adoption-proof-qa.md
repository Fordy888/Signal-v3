# DTL Signal All-AI Adoption-First Candidate — QA Record

**State:** APPROVED and DEPLOYED proof-only; first production canary failed safely; repair not yet deployed or verified.

## Deterministic build evidence

| Field | Evidence |
|---|---|
| Candidate edition | 0047 |
| Editorial revision | `ai-adoption-v1` |
| Reader renderer | `enhanced-v4-focus-numbers` contract |
| Newsroom source IDs | `S03, S04, S06, S07, S10` |
| Focus source IDs | `S01, S02, S05, S08, S09` |
| Distinct sources | 10 |
| Verified AI adoption items | 8 |
| Verified AI-industry-impact items | 2 |
| Focus-number eligible source pool | 7 |
| REMEMBER THE WORLD | Norderney, Germany — Dietmar Rabich / Wikimedia Commons / CC BY-SA 4.0 |
| Governed image identity | `REMEMBER-0047-NORDERNEY-MARIENHOEHE` |
| Candidate HTML SHA-256 | `c43ec4b92fa8bc815ff09538b38e5ee5e32a3882586f90195d6166247c408a06` |

The production classifier and semantic validator passed every selected source and every reader-visible adoption item before the locked founder-led renderer produced `data/ai-adoption-proof-0047.html`.

## Browser inspection note

The first local browser load exposed exactly ten source links plus the DTLC.ai footer link, with the Newsroom sources appearing before the five Focus sources. The screenshot upload failed, and the browser then reset to a blank page. This is not visual proof. Independent rendering and image inspection remain required before the candidate can be presented as reader-verified.

## Independent render and test evidence

Chromium rendered the corrected candidate to a 1000 × 3900 full-page image. Visual inspection confirmed the locked order, clear headline hierarchy, five distinct Newsroom stories, five compact Focus entries, complete lower sequence, full-width REMEMBER THE WORLD photograph with caption and attribution, final Dad Joke and minimal footer. No clipping or machine classification labels were visible.

The corrected image contract passed **48/48 focused tests** covering the proof, image validator, date-resolved path, daily success path, missing-record hold, wrong-date hold, repetition hold, renderer order and proof-only Render blueprint. All eight test modules then passed independently in both the integration checkout and a fresh detached worktree: **116/116 tests** in each environment.

## Disqualified one-recipient image-less proof — 4 September 2026

| Field | Evidence |
|---|---|
| Recipient | `paul.ford@gmail.com` only |
| Sender | `Signal <signal@signal.dtlc.ai>` |
| Reply-to | `paul.ford@gmail.com` |
| Subject | `[PROOF] DTL Signal \| All-AI Adoption-First \| Edition 0047` |
| Resend email ID | `b5156907-d8fc-4c44-a05a-43f22e2c0801` |
| Provider message ID | `<010601a06a9b4ad7-fea6a6d4-7c72-487a-b3c4-9241bbe98e23-000000@email.amazonses.com>` |
| Provider status at verification | `opened` |
| Gmail message/thread ID | `1a06a9b4e6ffb3b1` |

The Gmail copy independently confirms Edition 0047, the exact sender and recipient, the complete Founder’s Note, five Newsroom stories, five Focus entries, interpretation, actions, counter-position, watch items and Dad Joke. It contains the same ten source names in the same section allocation. This establishes **proof delivered and reader-visible Gmail content verified**. It does not establish editorial approval, COMMITTED, DEPLOYED, CANARY VERIFIED, LIVE or SUBSCRIBER VERIFIED.

This delivery omitted the mandatory REMEMBER THE WORLD section. Its checksum `861fae29a53a54a20b745ad24d4bca0d86eec7c7c0ba5b60955d21938c472b2a` is **disqualified** and must never be approved, committed as the target proof, deployed or canaried.

## Corrected proof delivery

The corrected checksum `c43ec4b92fa8bc815ff09538b38e5ee5e32a3882586f90195d6166247c408a06` was sent only to `paul.ford@gmail.com` with subject `[CORRECTED PROOF] DTL Signal | All-AI + Remember The World | Edition 0047`.

| Field | Evidence |
|---|---|
| Resend email ID | `182384b7-5a4c-4e4d-a71a-8c561fe8facd` |
| Provider message ID | `<010601a06aafc221-c9adc023-02ac-4c45-b41c-70b774f0a3fa-000000@email.amazonses.com>` |
| Provider status at verification | `opened` |
| Gmail message/thread ID | `1a06aafc436693d4` |

The actual Gmail copy independently contains `REMEMBER THE WORLD`, `Norderney, Germany`, the full image, Dietmar Rabich attribution, Wikimedia Commons source, CC BY-SA 4.0 licence link and the Dad Joke after the image section. This establishes **corrected proof delivered and Gmail reader-visible image contract verified**. It does not establish editorial approval, COMMITTED, DEPLOYED, CANARY VERIFIED, LIVE or SUBSCRIBER VERIFIED.

Paul Ford approved the exact corrected Edition 0047 proof after receipt. Approval binds checksum `c43ec4b92fa8bc815ff09538b38e5ee5e32a3882586f90195d6166247c408a06`, editorial revision `ai-adoption-v1` and image identity `REMEMBER-0047-NORDERNEY-MARIENHOEHE`. This establishes **APPROVED** only; deployment and canary evidence remain outstanding.

## Render deployment evidence — 4 September 2026

| Field | Evidence |
|---|---|
| GitHub master commit | `132be3af8cf0dcd0096d72b7e50f800b6da01a61` |
| Render build ID | `bld-dad5258ae00c738uaf50` |
| Render build status | Build succeeded; latest |
| Render build tests | 116 tests passed |
| Last successfully deployed commit | `132be3af8cf0dcd0096d72b7e50f800b6da01a61` |

The code deployment is present, but the dashboard command override remained pinned to expected commit `da960197447b7ba87f08457b67dffdd3ced33e2a` and Edition 0046. This is a critical deployment-configuration mismatch. The canary must not run until the proof-only command is updated and independently re-read from the saved Render settings.

The replacement command was entered with expected commit `132be3af8cf0dcd0096d72b7e50f800b6da01a61`, release ID `ai-adoption-v1-proof-0047`, approved checksum `c43ec4b92fa8bc815ff09538b38e5ee5e32a3882586f90195d6166247c408a06`, versioned manifest, dated image record and no `--send`. The dashboard had not yet returned to a read-only saved state, so this entry is not evidence that the configuration is active. Canary remains blocked pending a fresh settings read.

A fresh read-only Render settings view then confirmed the saved command contains expected commit `132be3af8cf0dcd0096d72b7e50f800b6da01a61`, release ID `ai-adoption-v1-proof-0047`, approved checksum `c43ec4b92fa8bc815ff09538b38e5ee5e32a3882586f90195d6166247c408a06`, `data/release_manifest_ai_adoption.json`, the date-resolved image path, the guarded renderer and service ID, `--proof --release-canary --enhanced --alive-moment`, and no `--send`. This establishes **DEPLOYED proof-only**. It does not establish CANARY VERIFIED.

## Render canary run — started 4 September 2026

The manual cron run started at `2026-09-04T05:18:31Z` and executed the saved Edition 0047 proof-only command. Initial log evidence records mode `proof`, code version `132be3af8cf0dcd0096d72b7e50f800b6da01a61`, weekday Daily Signal, 111 active sources, recipient `paul.ford@gmail.com only`, recipient integrity `1 unique valid emails` and next edition `0047`. Source fetching then began. Delivery, receipt compliance and Gmail content were not yet established at this checkpoint.

The run remained active at 2 minutes 18 seconds. No terminal status, provider receipt or Gmail delivery had appeared, so CANARY VERIFIED remained false.

The run ended failed after 9 minutes 38 seconds. It fetched and scored 425 items, with 194 above the scoring threshold, then failed while building the structured judgement plan: `FOCUS ON THE NUMBERS requires at least 4 numeric evidence sources; received 2`. The pipeline saved an `ABORTED` run receipt, sent that receipt only to `paul.ford@gmail.com`, logged `Edition NOT sent`, and exited with status 1. No Signal canary email was delivered. This is a correct safety hold, not CANARY VERIFIED.

## Numeric evidence attrition diagnosis and repair

Root-cause reproduction against current feeds found 478 raw items and 102 numeric records, but only 9 independently classifiable AI-adoption records and 2 numeric AI-adoption records when the pipeline retained only the short RSS summary. The repaired no-send diagnostic retained publisher-supplied RSS/Atom content from the same entries and found 477 raw items, 149 numeric records, 18 AI-adoption records and 10 numeric AI-adoption records. The quality threshold was not lowered; the repair preserves source text that ingestion previously discarded.

The approved Edition 0047 plan, evidence, Dad Joke, governed image and exact checksum are now represented by `data/locked_editions/0047.json`. Focused regressions prove that the locked path revalidates all-AI classifications, numeric evidence and image date, then reproduces checksum `c43ec4b92fa8bc815ff09538b38e5ee5e32a3882586f90195d6166247c408a06`. This repair is local only until a new commit, Render build and fresh one-recipient canary complete.

All nine test modules passed independently in the integration checkout and a fresh detached worktree: **121/121 tests** in each environment. This includes the exact locked-canary simulation, the realistic short-summary attrition regression, publisher-feed evidence sanitisation, prompt allocation boundary and unchanged frozen-proof checks. No production deployment or rerun is established by these local results.
