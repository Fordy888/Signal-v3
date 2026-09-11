# DTL Signal Edition 0042 Format Incident Report

**Incident date:** Friday 28 August 2026

**Prepared for:** Paul Ford, CEO, DTL Group
**Status:** Confirmed production release-control failure; no recovery broadcast sent

## Executive summary

Edition 0042 delivered successfully to **32/32 active subscribers**, but it used the existing legacy Signal format rather than the locked Enhanced v4 format Fordy had approved. The content pipeline, subscriber API and email delivery system operated; the product release did not.

> **Root cause:** the approved Enhanced v4 work never reached the production branch or production start command before the scheduled run. It remained on a feature branch with further uncommitted local changes. Render therefore executed the unchanged `master` branch and legacy command.

This was not a renderer defect or an email-client failure. It was a **release-control and communication failure**. Extensive tests proved that the proposed code and proof were internally consistent, but no test can make undeployed code run. The final operational gates—commit, merge, deploy, live command verification and production-version receipt—were not completed. I should have reported that as a hard blocker and stated plainly that the scheduled run would remain legacy. Instead, “locked,” “ready” and “tested” were allowed to sound like “deployed.” That was wrong.

## What subscribers received

The live Edition 0042 message was sent at approximately **06:09 AEST** with the legacy opening `Today's Signal`, legacy `TOP SIGNALS`, ACT/WATCH/NOTE labels, gauge links, the old `EXECUTIVE READ` structure, the share block and `Signal learns` footer. It did not contain the four-colour `THINK. DECIDE. LOOK UP. SMILE.` signature, `YOUR SIGNAL AT A GLANCE`, THE ONE THING, the approved Enhanced evidence/interpretation rhythm, REMEMBER THE WORLD or the Daily Dad Joke.[1]

| Live result | Confirmed evidence |
|---|---|
| Edition | 0042 |
| Delivery | 32/32 subscribers |
| Sources | 101/111 succeeded; 10 failed |
| Items scored | 200 |
| Category coverage | 8/8 |
| Runtime | 688 seconds |
| Subscriber-visible renderer | Legacy daily Signal |
| Enhanced v4 deployed | No |
| Duplicate correction sent | No |

The approved proof had a different subject and unmistakable Enhanced markers. It was sent only to `paul.ford@gmail.com` before release and was never the production artefact.[2]

## Confirmed repository and deployment facts

At incident time, GitHub production `master` remained at commit `7ae66b2b9a5864bdb9e2ca5cfc57cd9c175644c7`, dated 24 August 2026. The Enhanced feature branch was five commits ahead at `89a02100ace73082cdb379f5028351c5b5c5a327`, with the final Edition 0042 design and release-hardening changes still uncommitted in the local working tree.[3] [4]

| Release control | Required state | Actual state before 06:00 AEST |
|---|---|---|
| Approved artefact | Exact Enhanced v4 Edition 0042 checksum | Existed locally and as a one-recipient proof |
| Source commit | Final format committed | **Not completed** |
| Production branch | Enhanced work merged to `master` | **Not completed** |
| Remote repository | Final work pushed | **Not completed** |
| Render deploy | New commit built and activated | **Not completed** |
| Production command | `python -m src.main --send --enhanced --locked-edition 42` | Remained `python -m src.main --send` |
| Live verification | Render job confirmed expected commit and command | **Not completed** |
| Subscriber release | Send exact approved artefact | Legacy pipeline ran |

The source-controlled Render specification itself still declared the legacy start command. The last verified live Render audit also showed the service following `master`, with dashboard-only build shims and the same legacy start command. A fresh authenticated Render read was attempted before the run, but access was not obtained. That unresolved gate should have stopped any assurance that the new format would go out.[5]

## Timeline

| Time | Event | Release meaning |
|---|---|---|
| 24 August | Production `master` remained on recovery commit `7ae66b2` | Stable legacy production |
| 24–27 August | Enhanced v4 developed and refined on `feature/development-thesis-v1` | Production deliberately untouched |
| 27 August | Exact Enhanced Edition 0042 proof sent to Fordy and approved | Design/content approval only |
| 27 August | Fordy asked for every available test and confirmation of Friday and Saturday | Required transition from proof work to production release |
| 27 August | Local production hardening, Friday/Saturday simulations and 41 automated tests completed | Proposed release package validated locally |
| 27 August | Live Render configuration remained unverified; no commit, merge, push or deployment occurred | **Hard blocker not escalated clearly** |
| 28 August, 06:09–06:11 AEST | Existing Render job ran the legacy command | Wrong format generated and delivered |
| 28 August, 06:11 AEST | Receipt declared 32/32 delivered and “Tomorrow's edition is safe” | Delivery success incorrectly presented as overall release safety |

## Root-cause analysis

### Primary technical cause

The production scheduler continued to execute the old branch and old command. The Enhanced renderer was CLI-gated and required explicit activation. Because neither the branch nor the command changed, the scheduler had no path to the locked format.

### Primary process cause

The release was treated as though proof approval plus local test completion equalled production readiness. They are different states. The required state progression was not enforced:

> **Draft → proof approved → committed → merged → deployed → live config verified → canary verified → subscriber send**

The process stopped between proof approval and commit. There was no release manifest in production, no deployed-commit receipt and no final go/no-go statement tied to the live service.

### Communication failure

I repeatedly said production remained untouched during development, but after Fordy asked whether the new format would go out, I did not convert that fact into a direct warning: **“No. Not yet. Production is still legacy and cannot send the new format until deployment is completed.”** I instead continued expanding tests and release preparation. That created false confidence. I own that failure.

### Why the tests did not prevent the incident

The 41 tests were useful but scoped to the local candidate code. They covered exact HTML reproduction, numbering, Friday/Saturday routing, recipient holds, provider failure, partial delivery, memory, rights checks and email-safe markup. They did **not** and could not prove that Render had checked out that code or was invoking its Enhanced flags.

| Test class | What it proved | What it could not prove |
|---|---|---|
| Rendering tests | Enhanced v4 generated the approved HTML | That Render was using Enhanced v4 |
| Checksum lock | Local Edition 0042 matched the proof | That the checksum-locked files were deployed |
| Friday simulation | The proposed Friday command was safe | That Render's live command had changed |
| Saturday simulation | Proposed routing and structural gates worked | That Saturday production contained those changes |
| Failure-path tests | Candidate code held or returned non-zero correctly | That production was running candidate code |
| Inbox proof | The proof rendered acceptably for Fordy | That the subscriber job would send that artefact |

The missing test was not another unit test. It was a **live deployment identity check**.

## Receipt control failure

The Edition 0042 receipt accurately reported pipeline throughput, source coverage and 32/32 delivery. It did not report a Git commit, renderer ID, launch flags, template checksum or expected-versus-actual release identity. It therefore labelled the run `DELIVERED SUCCESSFULLY` and said `Tomorrow's edition is safe` while being unable to verify the format Fordy had approved.[1]

The receipt conflated **email delivery success** with **product release success**. Future receipts must separate those states.

## Impact

Thirty-two subscribers received one operationally healthy Edition 0042 in the old format. They did not receive the expected product change. No duplicate or corrective Edition 0042 has been sent. The immediate impact is a missed launch moment and reduced confidence in the release process, rather than a delivery outage.

Saturday's Weekly Wrap is also **not protected by the local fixes until they are deployed**. The current live Saturday job remains its legacy format. It should not be represented as Enhanced v4 without a separate design proof and live activation.

## Corrective controls

| Control | Required behaviour |
|---|---|
| Release manifest | Bind edition, date, renderer, HTML checksum and expected commit |
| Protected production branch | No scheduled release from uncommitted or feature-only work |
| Build gate | Run the complete suite during deploy and fail the build on any test failure |
| Exact start command | Store the production command in source control and compare it with the live service |
| Live identity preflight | Before schedule, confirm deployed commit, branch, command and artefact checksum |
| Canary proof | Generate from the deployed service, not the local workspace |
| Release receipt | Show commit, renderer, checksum, command profile and expected/actual match |
| Two-part status | Report `Delivery status` separately from `Release identity status` |
| Hard hold | Any missing identity field prevents a `SAFE` status and blocks subscriber delivery |
| Rollback | Preserve the last known-good production commit and explicit rollback command |
| Observation window | Require three consecutive scheduled runs without intervention; any failure restarts the window |

## Recovery choices

| Choice | Subscriber impact | Risk | Recommendation |
|---|---|---|---|
| Resend Edition 0042 in Enhanced v4 today | Subscribers receive a second Edition 0042 | Duplicate fatigue and edition ambiguity | **Do not recommend** |
| Activate Enhanced v4 for the next daily edition | One clean product transition; no duplicate | Requires a new edition manifest and deployed canary | **Recommended** |
| Send Saturday Weekly Wrap unchanged | Keeps cadence | Continues the old visual system and undeployed defects | Not recommended without a fresh live safety check |
| Hold Saturday, activate after deployed proof | Protects trust and creates a clean restart | Misses one Wrap | Recommended if live activation cannot be fully proven in time |

## Recommendation

Do **not** send a second Edition 0042. Treat the delivered message as the only Edition 0042. Complete the production release through an observable commit-and-deploy process, generate a proof from the deployed service, and introduce Enhanced v4 on the next authorised daily edition. Hold Saturday's Weekly Wrap unless its current production path is separately verified or the Enhanced adaptation is deliberately designed and approved.

## Minimum gate before the next activation

The next production send must remain held until every line below has objective evidence rather than an assumption.

| Gate | Evidence required |
|---|---|
| Source freeze | Clean working tree and one named release commit containing the exact format |
| Production merge | `master` points to the approved release commit or an auditable merge commit |
| Remote confirmation | GitHub returns the same production commit SHA |
| Build verification | All release tests pass inside the deployment build, not only locally |
| Live configuration | Render reports the expected branch, commit, build command, start command and schedule |
| Deployed canary | A proof generated by the deployed service arrives only in Fordy's test inbox |
| Artefact identity | Deployed proof reports the expected renderer and approved HTML checksum |
| Inbox rendering | Gmail mobile, Gmail desktop and Apple Mail explicitly pass |
| Audience preflight | Fresh live API count is reported, exclusions are listed and no fallback audience exists |
| Final authority | Fordy gives an explicit production go after reviewing the deployed canary |
| Production receipt | Receipt separates release-identity status from subscriber-delivery status and includes commit, renderer and checksum |

If any field is missing or mismatched, the status is **HELD**, never `SAFE`.

No recovery broadcast or production change should occur solely from this report. Fordy's explicit choice is required.

## References

[1]: Gmail message ID `1a044d9a53bb9656`, “DTL Signal Run Receipt — Edition 0042,” 28 August 2026.
[2]: Gmail message ID `1a0426bd24fb8756`, “[PROOF] DTL Signal | Edition 0042 | Final Format,” 27 August 2026.
[3]: https://github.com/Fordy888/Signal-v3/commit/7ae66b2b9a5864bdb9e2ca5cfc57cd9c175644c7 "Production master before Edition 0042"
[4]: https://github.com/Fordy888/Signal-v3/commit/89a02100ace73082cdb379f5028351c5b5c5a327 "Enhanced feature branch remote head before Edition 0042"
[5]: edition0042-release-readiness.md "Edition 0042 production-readiness audit"
