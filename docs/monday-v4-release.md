# DTL Signal v4.0 — Monday Release Record

**Target:** Monday 31 August 2026, Edition 0043

**Saturday decision:** Weekly Wrap on 29 August remains unchanged
**Current status:** Source-controlled release controls complete; not yet committed, merged or deployed

## Locked release boundary

The Brisbane weekday counter resolves Saturday 29 August to Edition 0042 and Monday 31 August to Edition 0043. The production command now activates Enhanced v4 only for the daily route; Saturday continues through its current Weekly Wrap route.

## New hard production controls

| Control | Behaviour |
|---|---|
| Launch date | v4.0 identity enforcement activates on 31 August 2026 |
| Renderer | Monday daily production must report `enhanced-v4` |
| Branch | Render must report `master` |
| Service | Render must report service `crn-d8ouk0bsq97s73fgc36g` |
| Commit | `RENDER_GIT_COMMIT` must be present |
| Release profile | Must report `v4.0` |
| Failure state | Any missing or mismatched identity field holds the send |
| Build | The full unit suite runs during the Render build |
| Receipt | Separates delivery status from release-identity status and reports renderer, commit, branch, service and HTML SHA-256 |

Render documents `RENDER_GIT_BRANCH`, `RENDER_GIT_COMMIT`, `RENDER_SERVICE_ID` and related variables as default runtime environment values.[1]

## Production commands

| Service | Command |
|---|---|
| Scheduled Signal | `python -m src.main --send --enhanced --alive-moment` |
| Deployed proof canary | `python -m src.main --proof --enhanced --alive-moment --as-of 2026-08-31T06:00:00+10:00 --save-html data/deployed-canary-0043.html` |

The canary command is proof-only and resolves to Paul’s configured proof inbox. `--as-of` is rejected in subscriber-send mode, preventing simulated dates from being used for a broadcast.

## REMEMBER THE WORLD

Monday uses the separately dated and approved Edition 0043 Moorea candidate. Authenticity, rights, place/subject alignment, seasonal validity and non-repetition checks still execute. Future editions must provide their own approved candidate or omit the section rather than force an ungoverned image.

## Verification state

The suite now reports **47 passing tests**, including a full Monday Edition 0043 dynamic v4.0 no-send simulation with the four-colour signature, YOUR SIGNAL AT A GLANCE, FOUNDER'S NOTE, REMEMBER THE WORLD, Daily Dad Joke and exact Brisbane date/footer identity. The delivery function is never called.

The candidate was reconstructed in an isolated Git worktree from the staged release diff. The first clean-tree run exposed two newly created test modules that were present locally but excluded by an inherited `test_*.py` ignore rule. The ignore contract was corrected; the clean candidate now contains all four test modules changed or added by the release, and all 47 tests pass from Git-contained files only. This validates the same file boundary the Render build will receive.

Commit, merge, live Render deploy and the deployed canary remain outstanding.

## References

[1]: https://render.com/docs/environment-variables "Render — Default Environment Variables"
