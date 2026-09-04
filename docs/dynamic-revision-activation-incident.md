# DTL Signal Dynamic Revision — Live Activation Incident

**Incident date:** 2 September 2026
**Approved proof:** `[PROOF] DTL Signal v4 | Complete Revision + Remember The World`
**Approved proof SHA-256:** `56226e2f1f955cc137d9b621b07504732390924d25dcc1cada87797e91744f35`
**Approved GitHub master:** `345c20be56d653261c0cd6503dc6151a857abf01`
**Subscriber-visible production commit:** `6c39f001c256c8d401f34cfbbdaa23ce5041b24a`

## Confirmed facts

Fordy approved the complete dynamic-headline and Quang Phu Cau proof as `100% perfect`. The approved code was subsequently committed to GitHub production master, but the guarded Render build and live canary were not completed after Render authentication was lost during the sandbox reset.

The Wednesday Edition 0045 operational receipt confirms that the live service remained on commit `6c39f001c256c8d401f34cfbbdaa23ce5041b24a`, renderer `enhanced-v4`, branch `master`, service `crn-d8ouk0bsq97s73fgc36g` and HTML SHA-256 `e34ba6083ca88e34391cbbff703e9acfdf2f6af368ecee7f2c7fc87c14dee616`. It delivered 33/33 subscribers and reported release identity `MATCH`.

The subscriber email proves that `MATCH` referred to the previous v4 release, not the newly approved revision. It still contained `VISUAL SIGNAL`, `EXECUTIVE READ`, `INTERPRETATION`, `WHAT CHANGED?`, `EXECUTIVE ACTION / WATCH`, reader-facing `S01 / S02 / S03` evidence codes and the repeated Moorea whale photograph. It did not contain the approved dynamic middle or the Quang Phu Cau image.

| Commitment state | Evidence-backed status |
|---|---|
| Proof approved | **YES** |
| Revision built and tested | **YES** |
| Revision committed to GitHub master | **YES — `345c20b`** |
| Revision deployed to Render | **NO** |
| Revision canary verified | **NO** |
| Revision subscriber-visible | **NO** |

## Root cause

The direct technical cause was that Render continued running the prior deployed commit while GitHub master moved ahead. The direct process cause was that the release was described as confirmed after approval, test and commit, even though live deployment and canary verification remained incomplete.

The release-identity control also had a governance weakness: it correctly matched the commit configured in the existing Render environment, but that expected commit was not advanced to the newly approved revision. It therefore proved internal consistency for the old release while failing to detect an unfulfilled newer commitment.

## Subscriber impact

No duplicate edition has been sent. Edition 0045 delivered successfully to 33/33 subscribers, but it used the previous v4 middle and repeated whale image rather than the approved revision. Recovery must activate the approved code for the next scheduled edition; it must not resend Edition 0045.

## Current operating status

The approved revision is **COMMITTED / NOT DEPLOYED / NOT LIVE**. No further editorial approval is required. The next permitted status is DEPLOYED, and that status requires direct Render evidence tied to commit `345c20b` or a documented descendant containing only release records.

## Edition 0046 recurrence — 3 September 2026

The later founder-led 60/40 release was approved, built and committed to GitHub master at `5b83752deafb7dca394c27bc2533e829d04144c7`. Its exact approved proof SHA-256 is `7ff05b54870a4ed4e2db737752380bb3d1ae5da915c9f8d3c5b0c9cc67b606e3`. The release was not deployed after the Render session expired, and the scheduled run was not held.

The subscriber-visible Edition 0046 PDF confirms the old release sent again. It contains `THE ONE THING`, a long Founder’s Note after that section, `THE EVIDENCE`, `VISUAL SIGNAL`, `EXECUTIVE READ`, `INTERPRETATION`, `WHAT CHANGED?`, `EXECUTIVE ACTION / WATCH`, reader-facing `S01 / S07 / S26 / S33` codes, `COUNTER-SIGNAL`, `WHAT TO WATCH` and the repeated Moorea whale photograph. It does not contain `DTL SIGNAL NEWSROOM — READ THIS` or `FOCUS ON THE NUMBERS`.

The matching Gmail operational receipt has message ID `1a063c07171fe39d` and subject `✓ DTL Signal 0046 — Delivered (33/33)`. It records:

| Field | Edition 0046 actual evidence |
|---|---|
| Delivery | `33/33` |
| Live commit | `6c39f001c256c8d401f34cfbbdaa23ce5041b24a` |
| Renderer | `enhanced-v4` |
| Expected renderer in old environment | `enhanced-v4` |
| Receipt identity | `MATCH` |
| Actual HTML SHA-256 | `61c6dca5b914a459a977b55292fccf683c9cbefd1db576f9aae658fd85033caa` |
| Approved target commit | `5b83752deafb7dca394c27bc2533e829d04144c7` |
| Approved target proof SHA-256 | `7ff05b54870a4ed4e2db737752380bb3d1ae5da915c9f8d3c5b0c9cc67b606e3` |

The receipt’s `MATCH` proves only that the old runtime matched its stale environment. It does not prove the approved release went live. The commitment result is therefore: **DELIVERY SUCCEEDED / TARGET RELEASE FAILED**.

No duplicate Edition 0046 will be sent. Recovery targets the next available scheduled edition only after the approved commit is deployed and a one-recipient canary proves the target release.

## Recovery deployment evidence — 3 September 2026

Render environment controls were aligned with target release `focus-numbers-60-40-v1`, expected commit `cd73df99af5f7a896e13d997974315e312e00c62`, renderer `enhanced-v4-focus-numbers`, approved proof SHA-256 `7ff05b54870a4ed4e2db737752380bb3d1ae5da915c9f8d3c5b0c9cc67b606e3`, manifest `data/release_manifest.json` and image identity `REMEMBER-0046-QUANG-PHU-CAU-INCENSE`.

Manual Render build `bld-dacc4t3m8hqs73aengt0` checked out the exact target commit, ran all **67 tests successfully**, and completed successfully. Render’s build history then identified `cd73df9` as the **last successfully deployed commit**.

This establishes **DEPLOYED**. It does not yet establish CANARY VERIFIED, LIVE or SUBSCRIBER VERIFIED.

## Live canary in progress — 3 September 2026

The production cron command was temporarily changed from subscriber mode to `python -m src.main --proof --release-canary --enhanced --alive-moment --as-of 2026-09-03T06:00:00+10:00 --save-html /tmp/deployed-canary-0046.html` before the manual run was triggered.

Render checked out commit `cd73df99af5f7a896e13d997974315e312e00c62`. The live log confirms `mode=proof`, `PROOF MODE: sending to paul.ford@gmail.com only` and `FAIL-SAFE: Recipient integrity verified — 1 unique valid emails`. The canary is still processing the live source and scoring pipeline. CANARY VERIFIED is not yet true.

The canary completed with a safe abort. Gmail receipt `1a064c8a2e33b0a6` reports `[ABORTED] DTL Signal 0046 — Not sent`, `0/0 delivered`, target and actual commit both `cd73df99af5f7a896e13d997974315e312e00c62`, matching renderer, release ID, proof checksum and Quang Phu Cau image identity, but no generated HTML.

The specific synthesis hold was: `Judgement planning failed after three attempts: Focus number 4 must contain a defining figure in no more than 10 words`.

This proves the deployment and release-identity controls are active and the one-recipient boundary held. It does **not** establish CANARY VERIFIED. The service remains on the proof-only command while the planner’s final-attempt normalisation is corrected and the canary is rerun.

The Focus-number correction was committed as `9862fbab0898bf5ad6012e91fd93cca6918caec6`, passed 69/69 local, isolated and Render build tests, and was deployed in build `bld-dacckobm8hqs73agdjbg`.

The second proof-only canary again held safely. Gmail receipt `1a064e63b95531f8` reports `0/0 delivered`, target and actual commit both `9862fbab0898bf5ad6012e91fd93cca6918caec6`, and the full renderer, release, proof and image contract matched. The new synthesis hold was: `Judgement planning failed after three attempts: Edition requires 1-3 executive actions`.

This second result confirms the first correction worked and exposed a separate final-attempt structural edge case: the model returned zero actions. The release remains DEPLOYED but not CANARY VERIFIED or LIVE.

### Third canary — comprehensive normalisation trigger

The third proof-only canary ran on deployed commit `eb5a1bcf36f6232c2582db509a0dc95855924486`. Target and actual commit, renderer, release ID, approved proof checksum and Quang Phu Cau image identity all matched. Gmail receipt `1a064faa89eba821` records `0/0 delivered` and an abort after 738 seconds.

The exact hold was: `AI-in-business Newsroom story requires a substantive connection in no more than 28 words`.

Because this was the third distinct presentation-bound miss after three model attempts, recovery moved from one-field fixes to a comprehensive final-attempt normalisation policy. Semantic, evidence, source, 60/40, digit and reader-language failures remain hard holds.

The comprehensive correction was committed to GitHub master as `71ea338870471b553735e878b0a5ba05b91fc02c`. Local and isolated worktrees each passed 74/74 tests and reproduced approved proof SHA-256 `7ff05b54870a4ed4e2db737752380bb3d1ae5da915c9f8d3c5b0c9cc67b606e3`.

Render build `bld-dacdc3qfngtc73d1v7d0` checked out that exact commit, passed all 74 tests and completed successfully. The service remained on the proof-only command pending another canary.

### Fourth canary — missing defining figure

The fourth proof-only canary ran on deployed commit `71ea338870471b553735e878b0a5ba05b91fc02c`. Gmail receipt `1a065131da16eadd` records `0/0 delivered` after 738 seconds. Target and actual commit, renderer, release ID, approved proof checksum and Quang Phu Cau image identity all matched.

The exact hold was: `Focus number 1 must contain a defining figure in no more than 10 words`. Unlike an overlong field, the generated value did not contain the required numeric evidence. Trimming cannot repair that condition.

Recovery must remain evidence-bound: a missing Focus figure may be recovered only from the same selected source record, and only when that source contains an explicit eligible numeric figure. If no such figure exists, the edition must continue to hold. The service remains proof-only.

### Fifth canary — selection must move upstream

The fifth proof-only canary ran on deployed commit `53a8f7a26adbdb19abe95d2d53717999e8935412`. Render build `bld-dacdomgae00c73f08bvg` passed all 78 tests and completed successfully. The canary ran manually from 02:36:05 to 02:48:25 UTC and sent no subscriber email.

Attempts one and two were rejected for presentation-bound issues and correctly retried. The final attempt normalised all eligible bounded fields but still failed with `Focus number 5 must contain a defining figure in no more than 10 words`. The selected fifth source contained no eligible numeric evidence, so same-source recovery correctly refused to invent a figure. The run receipt was saved as `Edition NOT sent`, and the receipt email was sent to Paul.

The root control must therefore move before planning: Focus on the Numbers may select only from a pre-verified pool of source records containing an explicit eligible figure. Final-attempt recovery remains a secondary safeguard, not the selection mechanism.

The upstream eligibility control was committed to GitHub master as `6f7ee932bd76d20c5d9a6db9d32e261d7de3649a`. Local and isolated worktrees each passed 82/82 tests and reproduced approved proof SHA-256 `7ff05b54870a4ed4e2db737752380bb3d1ae5da915c9f8d3c5b0c9cc67b606e3`.

Render build `bld-dace6ign74is73cs1dn0` checked out that exact commit, passed all 82 tests and completed successfully. The service remained proof-only pending the next canary.

### Sixth canary — technical match, editorial hold

The sixth proof-only canary ran on deployed commit `6f7ee932bd76d20c5d9a6db9d32e261d7de3649a` and delivered one proof to `paul.ford@gmail.com`. Gmail proof ID is `1a065469e122a552`. Gmail receipt ID is `1a06546ad6ed3e04`, subject `[CANARY] DTL Signal 0046 — Target release matched`.

The receipt records 1/1 delivered, 100/111 sources succeeded, 180 items scored, eight of eight categories covered and a 727-second duration. Target and actual commit, renderer `enhanced-v4-focus-numbers`, release `focus-numbers-60-40-v1`, approved proof SHA-256 and Quang Phu Cau image identity all matched. Actual generated HTML SHA-256 was `52a782e3d1dc604e75164c7537ae4c2030ca27aaf96ef8214953d75d1b4a53f4`.

Technical release identity therefore passed. Reader-visible review identified three blockers before subscriber mode can be restored:

1. Newsroom lead-ins exposed internal category keys such as `venture_capital`, `opportunity_radar` and `ai_market_signals`.
2. Several bounded headlines ended as clipped fragments, including `AI renewal agent covers every account, not just`, `AI governance gap is now a commercial liability, not a` and `Track AI correction time in your`.
3. The canary mix was nine AI-business items and one major-business item. This exceeded the minimum AI threshold but did not match the approved six-AI/four-major-business balance.

The canary is **technically matched but editorially held**. CANARY VERIFIED and LIVE are not yet true. The service remains proof-only.

The reader-visible correction was committed to GitHub master as `4d5dba838a951700fc1135ee526636f798db294d`. Local and isolated worktrees each passed 83/83 tests and reproduced approved proof SHA-256 `7ff05b54870a4ed4e2db737752380bb3d1ae5da915c9f8d3c5b0c9cc67b606e3`.

Render build `bld-daceneijnfac73c9sgcg` checked out that exact commit, passed all 83 tests and completed successfully. The service remained proof-only pending a fresh technical and reader-visible canary.

The next proof-only canary delivered Gmail proof `1a0656846f561dbe` and receipt `1a0656850d471bd8`. The receipt records 1/1 delivery, 102/111 successful sources, 190 scored items, target and actual commit `4d5dba838a951700fc1135ee526636f798db294d`, matched renderer, release, approved proof checksum and Quang Phu Cau image identity. Actual generated HTML SHA-256 was `707c75dcf523ed8c8a143248db86effb11e7fcc80e50253c9555e3b36345c766`.

The internal category keys were no longer visible and all previously clipped headlines ended cleanly. However, the reader-visible edition still contained approximately nine AI stories and one broader business story while the planner’s self-reported classifications satisfied the 6/4 gate. This proves model-assigned labels cannot be the source of truth for the content-mix commitment.

The release remains **technical canary matched / editorial canary held / not live**. Source substance must be classified before planning, and planner selections must be checked against those independently established source pools.

The classification-integrity control was committed to GitHub master as `ee4de7d629af0a6f1226fb568856fe1519d48bf5`. Local and isolated worktrees each passed 86/86 tests and reproduced approved proof SHA-256 `7ff05b54870a4ed4e2db737752380bb3d1ae5da915c9f8d3c5b0c9cc67b606e3`.

Render build `bld-dacf6hoae00c73f4284g` checked out that exact commit, passed all 86 tests and completed successfully. The service remained proof-only pending independent technical and reader-visible 6/4 canary verification.

The subsequent proof-only canary delivered Gmail proof `1a065849544df77a` and receipt `1a06584a0305a80c`. Target and actual commit `ee4de7d629af0a6f1226fb568856fe1519d48bf5`, renderer, release, approved proof checksum and image identity matched at 1/1 delivery.

Independent review of the actual Gmail body confirmed that Newsroom contained three AI-business and two major-business stories. Focus on the Numbers did not: two independently major-business source records were rewritten with AI-led reader copy. The proof also contained the incomplete watch headline `Enterprise AI scaling success rate moving above`.

The release remains **technical canary matched / editorial canary held / not live**. The next gate validates the actual reader fields against the independently verified source class and rejects incomplete directional or comparative headline endings. Subscriber mode remains disabled.

During GitHub recovery, remote master was found to contain two newer deterministic section-allocation commits (`ccd1334` and `8ff20e0`). They were preserved. Reader-visible semantic enforcement was integrated on top as combined commit `b772eb7`, retaining both preallocated three-plus-two source selection and validation of the actual copy readers see. The combined detached worktree passed 95/95 tests and reproduced approved proof SHA-256 `7ff05b54870a4ed4e2db737752380bb3d1ae5da915c9f8d3c5b0c9cc67b606e3`.

The release remains **technical canary matched / editorial canary held / not live**. The next gate validates the actual reader fields against the independently verified source class and rejects incomplete directional or comparative headline endings. Subscriber mode remains disabled.
