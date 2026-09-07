# DTL Signal Edition 0047 Subscriber Release — 4 September 2026

**Target:** deliver the exact approved all-AI, adoption-first Edition 0047 artefact to the full eligible subscriber base only after CANARY VERIFIED and Weekly Wrap readiness.

## Preconditions

| Gate | Evidence |
|---|---|
| Approved HTML checksum | `c43ec4b92fa8bc815ff09538b38e5ee5e32a3882586f90195d6166247c408a06` |
| CANARY VERIFIED | Deployed commit `4a3794b`; target/actual commit, proof checksum and Norderney image identity matched; actual Gmail body verified |
| Weekly Wrap readiness | Deployed commit `5fb530c`; successful no-send Saturday dry-run; exactly five stories; required labels and source links; no rating gauge; Saturday metadata aligned |
| Subscriber authorisation | Paul Ford explicitly approved the whole-base send after Weekly Wrap readiness |

## Subscriber run start

The Render command was independently re-read before triggering: deployed commit `5fb530c199ee460138d35a6c918d28eba5af5546`, approved release ID, approved checksum, versioned release manifest, date-resolved image record, `--send --enhanced --alive-moment --locked-edition 47`, and no `--as-of` or proof flag. The live subscriber source resolved to **33 eligible recipients**. Render started the run at `2026-09-04T08:35:39Z`; the process reported `mode=send`, Brisbane runtime `2026-09-04 18:35 AEST`, code version `5fb530c199ee460138d35a6c918d28eba5af5546`, and Daily Signal routing.

This entry records the authorised start only. It is not delivery evidence. LIVE and SUBSCRIBER VERIFIED remain false until the run, provider results, receipt and actual mailbox checks are complete.

## Render terminal result

The run rendered the checksum-locked Edition 0047 artefact and entered delivery only after the release gate logged target match for release `ai-adoption-v1-proof-0047`, renderer `enhanced-v4-focus-numbers`, deployed commit `5fb530c199ee460138d35a6c918d28eba5af5546`, approved proof checksum and approved image identity. Render then reported **33 sent, 0 failed** and finished the cron job successfully after 697.8 seconds.

Post-delivery instrumentation recorded 33 DTL PL delivery events, 33 mappings and 33 subscriber-insight records. One non-fatal bookkeeping warning, `'id'`, caused the saved run receipt to label the status `delivered_bookkeeping_error` rather than a clean success state. The warning occurred after all 33 provider send calls had succeeded. This establishes a completed broadcast at the application layer, but **SUBSCRIBER VERIFIED remains false** pending independent provider and Gmail evidence plus receipt inspection.

## Independent mailbox and receipt verification

Gmail independently contains the live subscriber message `1a06b99f3cc2d144` with subject `DTL Signal | Edition 0047 | Friday 04 September 2026` and the run receipt `1a06b99fbfca32cf`. The actual reader-visible message contains the approved Founder’s Note, five Newsroom stories, five Focus figures, interpretation/actions/counter/watch, the full Norderney REMEMBER THE WORLD section with attribution, and the Dad Joke after the image.

The receipt reports **33/33 delivered**, target release status `MATCH`, renderer `enhanced-v4-focus-numbers`, target commit = actual commit `5fb530c199ee460138d35a6c918d28eba5af5546`, approved proof = configured proof = actual HTML checksum `c43ec4b92fa8bc815ff09538b38e5ee5e32a3882586f90195d6166247c408a06`, and approved image = configured image `REMEMBER-0047-NORDERNEY-MARIENHOEHE`. Application logs contain a provider send ID and delivery result for every recipient, with 0 failures.

This establishes **SUBSCRIBER VERIFIED** for Edition 0047. The non-fatal bookkeeping warning remains a separate instrumentation defect and did not alter recipient count, content identity, release identity or delivery.
