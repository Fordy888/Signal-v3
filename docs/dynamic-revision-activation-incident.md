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
