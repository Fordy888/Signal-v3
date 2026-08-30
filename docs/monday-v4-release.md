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

The Python 3.11 correction was committed and pushed to production master as `f47caf17f246714b8452445ab25c0e13c3dae683`; GitHub reports the identical remote SHA. Render's build history did not create a build for this push despite Auto-Deploy remaining `On Commit`, reconfirming the stale webhook condition. A manual build of the latest master commit is therefore required and remains protected by the persisted 47-test build gate.

Manual build `bld-daa14h67bikc73f4stvg` is now in progress. Render confirms it checked out the exact corrected master commit `f47caf17f246714b8452445ab25c0e13c3dae683`. No runtime command change or subscriber send has occurred while the guarded build runs.

Build `bld-daa14h67bikc73f4stvg` completed successfully on exact commit `f47caf17f246714b8452445ab25c0e13c3dae683`. Render reports all 47 tests passed and the build artefact uploaded successfully. The live settings page confirms the new test-gated build command is persisted, but the scheduled runtime command is still legacy `python -m src.main --send`. Activating the approved v4.0 runtime command is now the remaining configuration step before environment verification and canary.

The approved runtime command `python -m src.main --send --enhanced --alive-moment` has been entered in the live Render editor. It is recorded as **not yet persisted** until the settings page exits edit mode and shows the command read-only.

The first pointer save and keyboard focus attempt did not leave edit mode; the page still shows Cancel and Save Changes. The v4.0 text remains in the field but is **not yet counted as active**. Monday remains HELD until a read-only settings refresh confirms the command.

The read-only settings refresh now confirms the active scheduled command is `python -m src.main --send --enhanced --alive-moment`. The live schedule remains `0 20 * * *` UTC and the test-gated build command remains persisted. Runtime environment identity and the deployed canary are the remaining gates before Monday GO.

The authenticated environment page was inspected without revealing any secret values. It contains the existing production API, sender, timezone and website variables but none of the six non-secret v4.0 release-identity keys. These must be added before canary execution; otherwise Monday's new hard identity gate will hold the send as designed.

Environment edit mode is open and one blank variable row has been added. No existing key or secret value has been viewed, edited or deleted. The change remains unsaved until all six approved non-secret rows are populated and the read-only page confirms them by name.

Six blank rows are now present for the six approved v4.0 values. Existing production keys and masked values remain untouched. No environment change has yet been saved or applied.

Render represents the six new key fields as empty values rather than the visual `NAME_OF_VARIABLE` placeholder. DOM inspection confirms exactly 18 key rows: 12 existing named variables followed by six empty rows. No secret textarea values were inspected. The six rows can now be populated by their verified positions without touching the existing 12.

All six new rows are now populated with the approved non-secret values: release profile `v4.0`, launch date `2026-08-31`, renderer `enhanced-v4`, branch `master`, service ID `crn-d8ouk0bsq97s73fgc36g`, and the Edition 0043 governed image fixture path. Existing variables remain unchanged. The environment edit is still unsaved pending the explicit Render apply action.

The first environment submit click did not exit edit mode; the six values remain visible alongside the Save control. They are therefore still treated as **not active**. Render's split-button apply option must be selected and then verified from a read-only reload before Monday can move to GO.

Subsequent DOM inspection found no active Save, Choose or Cancel control even though the extracted page view still showed the earlier editor labels. This indicates an asynchronous state transition or stale rendered snapshot. No second submission was attempted; the page will be reloaded cleanly and the environment will be accepted only if all six key names appear in read-only mode.

A clean read-only reload confirms all six v4.0 keys are persisted by name and the environment editor is closed. Existing secret values remain masked. The active command remains `python -m src.main --send --enhanced --alive-moment`. Render is now rebuilding the exact `f47caf1` commit to apply the environment change; the canary remains the next gate.

Render's build history confirms `f47caf17f246714b8452445ab25c0e13c3dae683` is the latest successful build. The environment update did not create a second visible build record, which is acceptable because the six values are runtime configuration; they are verified in read-only mode and apply to the next run. The release is now at the deployed-canary gate.

The cron service's One-Off Jobs page confirms no existing one-off jobs and exposes no create/run control. The global Trigger Run control would execute the active subscriber command and is therefore not being used for canary testing. Render's service shell is being evaluated as the safer route; if unavailable, a temporary proof-only command with verified restoration will be required.

The authenticated Render Web Shell is available against the service's latest build image and exposes a dedicated terminal input. This allows the approved proof-only Edition 0043 canary command to run without altering the scheduled subscriber command and without using Trigger Run.

The first coordinate-based terminal input navigated away from the shell and did not execute the command. No canary, subscriber run or proof email was created. The shell has been reopened; the next attempt will target its dedicated `Terminal input` element directly.

The direct input-event attempt also did not transmit the command text to the terminal; it produced only blank prompts. Again, no canary, subscriber run or proof email was created. The next attempt will use the terminal's paste-event pathway and will be accepted only if the full proof command is visible in shell output.

The terminal paste pathway succeeded. The deployed service started the exact proof-only command for Monday 31 August 06:00 AEST, reported code version `f47caf17f246714b8452445ab25c0e13c3dae683`, selected the weekday Daily Signal route, resolved Edition 0043, and confirmed `PROOF MODE: sending to paul.ford@gmail.com only` with one valid recipient. Source fetching has started. No subscriber command was invoked; canary completion and receipt remain pending.

The canary continues normally through the live 111-source inventory. The expected blocked-source warning for The Information has appeared, but no fatal error or audience-boundary change is present. Synthesis, release identity, QA and one-recipient delivery remain pending.

Source collection has progressed through the technology, leadership, finance and Australian business feeds without a fatal error. The proof-only recipient boundary remains unchanged. The canary has not yet reached scoring or synthesis, so Monday is still awaiting the completed deployed proof.

The canary has now progressed through the governance, labour, sales, marketing and customer-source groups as well. Only expected source-level warnings are visible; no pipeline hold or recipient-boundary change has occurred. Completion, scoring and synthesis remain to be verified at the terminal tail.

The live source pass has reached the end of the configured inventory without a fatal pipeline error. The embedded terminal's extracted markdown truncates before the newest scoring/synthesis lines, so completion is not yet inferred from the screenshot alone. The proof-only recipient boundary remains intact while the tail and Gmail evidence are checked.

Keyword-level terminal inspection confirms Stage 1 completed with **173 raw items**, **102/111 sources succeeding** and nine failed sources classified as six HTTP 403 blocks plus three empty feeds. The canary entered Stage 2 scoring. Stage 3 synthesis is not yet present, so completion remains pending rather than assumed.

Two subsequent checks still show no Stage 3 marker. This is consistent with the live scorer processing 173 items, but it is not treated as success. Monday remains HELD until the deployed process either advances to synthesis or reports a scored-content hold.

Stage 2 completed successfully: all 173 fetched items were scored and 71 cleared the threshold. The canary entered Enhanced Stage 3. The first judgement-plan response was correctly rejected because one evidence headline exceeded the eight-word contract, and the built-in retry started. No unvalidated content was rendered or delivered; the final retry outcome remains pending.

The automatic retry succeeded. Stage 3 produced **22,796 characters** of Enhanced v4 HTML on live commit `f47caf17f246714b8452445ab25c0e13c3dae683`, with SHA-256 `4b3342a3699b872e2260e75c97d6ff571e8ebf4f7eb3cbb8b45b3cf574e74579`. The process then entered the pre-send QA gate. QA outcome, release-identity result and one-recipient delivery remain pending.

No explicit QA-pass or release-gate marker is yet present in the terminal search results. The canary is therefore still classified as incomplete; Monday GO is not inferred from successful rendering alone.

The terminal now confirms the proof-mode release identity observation passed, the live HTML was saved to `data/deployed-canary-0043.html`, and Stage 4 began with exactly one recipient. A final delivery-success marker is not yet visible, so the deployed canary is still pending rather than counted as complete.

Gmail confirms the deployed proof arrived from `DTL Signal <signal@signal.dtlc.ai>` to `paul.ford@gmail.com` at 11:41 UTC. Its body begins with the correct Edition 0043, Monday 31 August metadata and the v4.0 signature. The canary also exposed a clock-consistency defect: the subject says `Sunday 30 August 2026` because subject construction used the actual wall clock instead of the proof-only release clock. Monday's real scheduled run would naturally use Monday, but the canary must reproduce the production identity exactly before GO. This defect is being fixed and regression-protected; Monday remains HELD.

Subject construction now uses the same Brisbane `runtime_now` release clock as edition numbering, body metadata and QA for both daily proofs and Weekly Wrap proofs. A dedicated no-delivery test asserts the exact Monday Edition 0043 subject, and the complete suite now reports **48 passing tests**.

Render's embedded terminal does not expose a functional scroll container through browser automation, so the final lines cannot be treated as visible evidence yet. Canary completion will be cross-checked through the one-recipient proof email and operational receipt in Fordy's Gmail, then reconciled with Render logs if needed.

## References

[1]: https://render.com/docs/environment-variables "Render — Default Environment Variables"
