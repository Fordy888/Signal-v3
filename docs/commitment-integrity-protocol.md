# DTL Signal Commitment Integrity Protocol

**Effective:** 2 September 2026

> A commitment is complete only when the promised customer-visible outcome is proven.

Signal must never use one word—such as `confirmed`, `ready`, `GO` or `complete`—to describe several different states. Every release statement must name the exact state and its evidence.

## Mandatory status vocabulary

| Status | Meaning | Required evidence |
|---|---|---|
| **PROPOSED** | A change is being considered. | Written scope; no implementation claim. |
| **APPROVED** | Fordy has approved an exact proof or requirement. | Approval message plus proof subject and SHA-256. |
| **BUILT** | The approved change exists and passes its defined checks. | Test count, clean-tree result and reproduced proof checksum. |
| **COMMITTED** | The built change is on the intended GitHub branch. | Full commit SHA and matching remote branch SHA. |
| **DEPLOYED** | Render is running that exact commit. | Render build ID, successful build result and runtime commit. |
| **CANARY VERIFIED** | The deployed service produced the expected version for one recipient. | One-recipient receipt with commit, renderer, artefact identity and visible markers. |
| **LIVE** | The production schedule and command point to the canary-verified revision. | Read-only Render command, schedule and environment verification. |
| **SUBSCRIBER VERIFIED** | Subscribers actually received the promised release. | Live delivery receipt plus the subscriber email matching the expected release contract. |

`CONFIRMED` may be used only with one of these named states—for example, `APPROVED confirmed` or `DEPLOYED confirmed`. An unqualified `confirmed`, `ready`, `GO` or `complete` is prohibited.

## Release commitment record

Every subscriber-visible change must record the following before deployment:

| Field | Requirement |
|---|---|
| Target edition and scheduled time | Exact Brisbane date, edition number and `06:00 AEST` schedule |
| Approved proof | Subject, file and SHA-256 |
| Expected commit | Full Git SHA containing the approved change |
| Expected renderer | Named renderer contract, such as `enhanced-v4-dynamic` |
| Expected artefact | Proof or release-contract SHA-256 |
| Current status | One mandatory status from the table above |
| Remaining blocker | Explicit technical, access or approval dependency |
| Next verification deadline | Time by which the next status must be proven |
| Hold action | Exact mechanism that prevents the old or wrong version from sending |

## Timing and escalation

The default Signal schedule is 06:00 AEST. A release intended for the next edition must be **COMMITTED by 18:00 AEST**, **DEPLOYED by 22:00 AEST**, and **CANARY VERIFIED by 02:00 AEST**. If any deadline is missed, the release is reported as `HELD` and the scheduled job must be prevented from sending an unverified version.

An approval after the COMMITTED deadline targets the following available edition unless Fordy explicitly authorises an accelerated release. Approval never implies deployment.

## Stop rules

The system must hold rather than send when the expected commit, renderer or artefact identity is missing or mismatched; when the approved release is committed but Render is still running an earlier commit; when a canary has not passed; when recipient data is unavailable; or when the customer-visible email does not match the approved release contract.

A successful delivery count does not override a release mismatch. `33/33 delivered` can coexist with `RELEASE FAILED` when the wrong version was sent.

## Enforced registry release evidence

The durable registry path requires all of the following before production preflight may freeze an audience and before the morning worker may claim a release:

| Required evidence | Source of truth |
|---|---|
| Approved versioned editorial policy | `SIGNAL_APPROVED_EDITORIAL_REVISION` matching the generated plan, currently `ai-adoption-v1` |
| Approved reader experience | One-recipient proof-scope registry canary with matching registry, Resend and Gmail evidence |
| Target Git commit | `SIGNAL_EXPECTED_GIT_COMMIT` |
| Actual deployed Git commit | `RENDER_GIT_COMMIT` |
| Expected and actual renderer | `SIGNAL_EXPECTED_DAILY_RENDERER` plus runtime renderer ID |
| Expected branch and Render service | Source-controlled environment contract plus Render runtime evidence |
| Edition-specific content and image identity | Immutable registry HTML, source metadata, image ID/checksum and governed date record |
| Frozen audience identity | Immutable recipient rows, audience count and audience checksum |
| Delivery eligibility | Date-matched `SCHEDULED` state, exact frozen commit and open 06:00 AEST delivery window |

Historical fixed-edition manifests remain evidence for their specific releases but are not recurring production controls. The registry preflight gate holds when the versioned editorial policy, renderer, branch, service or commit differs. The delivery worker then re-verifies the immutable frozen release and refuses any content generation, source fetch, image substitution or audience refresh. Only the verified proof-scope canary may establish `CANARY VERIFIED`; `LIVE` and `SUBSCRIBER VERIFIED` still require an on-time future subscriber edition.

## Communication rule

Every status update must use this structure:

| Field | Example |
|---|---|
| **Target** | Edition 0046, Thursday 3 September, 06:00 AEST |
| **Current state** | COMMITTED |
| **Evidence** | GitHub master `345c20b` |
| **Not yet true** | Not deployed; not canary verified; not subscriber-visible |
| **Blocker** | Render authentication required |
| **Next deadline** | DEPLOYED by 22:00 AEST |

This structure is mandatory whenever Fordy asks whether a change is confirmed.

## Current incident application

The dynamic-headline and Quang Phu Cau revision was APPROVED, BUILT and COMMITTED, but not DEPLOYED. Edition 0045 was SUBSCRIBER VERIFIED as the previous v4 release on commit `6c39f00`, not the approved revision on GitHub master `345c20b`. The release must remain described as **COMMITTED / NOT DEPLOYED / NOT LIVE** until direct Render evidence advances it.
