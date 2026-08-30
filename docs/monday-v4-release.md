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

The complete 37-file release candidate was committed on `feature/development-thesis-v1` as `5f316db76bcbed19f9ab9a4b598f2d0ae4c60758`. GitHub reports the identical remote feature-branch SHA. Production `master`, the live Render service and subscribers remain unchanged.

Merge, live Render deploy and the deployed canary remain outstanding.

## Authenticated Render verification — 30 August 2026

Fordy authenticated the live Render dashboard and the production service was inspected read-only. The service is still deployed from `master` at legacy commit `7ae66b2`, still runs `python -m src.main --send`, and has no build after 24 August. Auto-Deploy displays `On Commit`, but the 30 August GitHub merge to `da2ef3e` did not trigger a build, confirming the webhook remains stale.

The live schedule remains `0 20 * * *` UTC, equivalent to 06:00 AEST. The hidden dashboard build command still contains the four Base64-decoded source mutation shims. Therefore Monday is **not yet GO**: the source-controlled release has reached GitHub, but not the live Render runtime.

The required correction is now exact rather than inferred: update the live build command to the source-controlled build/test command, update the live command to `python -m src.main --send --enhanced --alive-moment`, add the v4.0 release-identity environment values from `render.yaml`, then manually deploy `da2ef3e` and verify a deployed proof canary before Monday.

### Live change log

Fordy explicitly authorised the Render production correction on 30 August. The legacy hidden build mutation has been replaced in the editable field with `pip install -r requirements.txt && python -m unittest discover -s tests -v`; at this checkpoint the field is prepared but not yet submitted.

The first Save and Enter attempts did not exit Render's edit state; the field still displays the approved command alongside Cancel and Save Changes. This is recorded as **not yet saved** and will be verified from the read-only settings state before any later step is treated as complete.

The build command was subsequently accepted and automatically triggered build `bld-daa0u467bikc73f4cqa0` for master commit `da2ef3e`. Dependency installation succeeded, but the test gate failed during module loading for three release-test modules. Render correctly stopped the deploy, so production remains on legacy commit `7ae66b2` and no subscriber send occurred. The exact traceback is being isolated before any retry; Monday remains HELD until a clean live build succeeds.

The authenticated settings page now confirms the source-controlled build command is persisted. The scheduled runtime command intentionally remains `python -m src.main --send` until a corrected commit passes the live build gate; this prevents an unbuilt v4.0 runtime from being activated.

Render's log filter confirms three Python tracebacks at 11:08:15 UTC, corresponding to the three failed test-module imports. The filtered interface exposes only the traceback headers, so the saved page payload is being parsed next for the exception lines; no retry or command weakening has occurred.

A targeted search returned no `No module named` lines. The next diagnosis therefore focuses on incompatible package/API imports shared by the three affected test modules rather than absent Git files.

Searches for both `cannot import name` and unittest's `Error importing test module` heading returned no detailed exception lines in Render's filtered interface. The investigation is therefore moving to a local clean Python 3.11 environment using the exact freshly resolved dependency versions shown in the live build, rather than weakening the build gate or guessing from truncated logs.

The decisive Render filter is `enhanced_renderer`: all three collection failures terminate at `/opt/render/project/src/src/enhanced_renderer.py`, line 150. The exact Git commit passes renderer imports in a fresh local environment, so this is a live build-workspace source mutation or syntax issue at that line—not a third-party dependency or missing-module problem. The deployed source line is being compared with Git next.

The root cause was Python-version grammar, not a missing dependency: line 150 used a nested f-string with escaped quotes, accepted by the sandbox interpreter but rejected by Render's Python 3.11 parser. The action-row construction now uses a separate `action_html` variable and contains no nested escaped f-string. A second time-dependent test was also made deterministic after the fresh Sunday reproduction showed it could exit before reaching the intended empty-subscriber hold.

The corrected code passes all **47 tests** in the same fresh dependency environment that reproduced the failed build. The source-controlled test gate remains intact; no test was removed or weakened.

## References

[1]: https://render.com/docs/environment-variables "Render — Default Environment Variables"
