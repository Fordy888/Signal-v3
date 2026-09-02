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
