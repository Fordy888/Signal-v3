# DTL Signal Weekly Wrap Readiness — 5 September 2026

**Target:** verify the deployed Saturday Weekly Wrap path without sending any email before Edition 0047 is released to subscribers.

## Deployed validation command

| Field | Evidence |
|---|---|
| Render service | `crn-d8ouk0bsq97s73fgc36g` |
| Deployed commit | `4a3794bf651367bba53b24bac09938353d096aaf` |
| Simulated Brisbane time | `2026-09-05T06:00:00+10:00` |
| Mode | `--dry-run` |
| Enhanced flag | Present; Saturday route must bypass the daily enhanced renderer |
| Subscriber delivery flag | Absent; command contains no `--send` and no `--proof` |
| Saved HTML | `/tmp/weekly-wrap-2026-09-05.html` |
| Schedule displayed | `0 20 * * *` UTC / 06:00 AEST |

A fresh read-only Render settings view confirmed the command above before Trigger Run was selected. The run identifier and terminal result remain outstanding; no readiness claim is made from the trigger alone.

Render registered the manual dry-run at `2026-09-04T07:17:55Z`. At the first runs-list check it had been active for 22 seconds. No email mode is present in the saved command. Source collection, Weekly Wrap synthesis, deterministic structure checks, saved HTML and terminal status remain outstanding.

## First deployed dry-run — held safely

The run ended failed after 12 minutes 59 seconds. It fetched and scored 440 items, retained 206 above threshold, generated a 19,625-character Weekly Wrap, injected the Founder’s Note and share block, and passed the Saturday date check, content minimum, source readiness, recipient count and reply-to checks. The Weekly Wrap structure gate did not report missing labels, story-count errors, source-link errors or rating-gauge leakage.

The pre-send QA gate held on one critical error: the generated body metadata said `Friday 04 September 2026` and its footer did not contain `Edition 0047 • 05.09.2026`, while the simulated Brisbane runtime was correctly `Saturday 05 September 2026`. The synthesis post-processor used the real process clock instead of the explicit governed runtime. Render logged `Edition HELD. Not sending`, wrote a held receipt, sent only that operational receipt to Paul, and exited with status 1. No Weekly Wrap or subscriber email was delivered.

## Governed-runtime repair

The synthesis entry point now accepts the pipeline’s timezone-aware governed runtime. `main.py` passes the same Brisbane clock used for edition type, subject and QA; the prompt metadata, deterministic header replacement and footer stamp derive from that single value. A regression reproduces a Friday model body under a Saturday governed runtime and proves it is rewritten to `Saturday 05 September 2026 | 06:00 AEST` and `PF::SIGNAL-0047 // 05.09.2026 // 06:00 AEST`.

All nine test modules passed independently in the integration checkout and a fresh detached worktree: **123/123 tests** in each environment. Deployment and a second no-send Render dry-run remain required; local results alone do not establish Weekly Wrap readiness.
