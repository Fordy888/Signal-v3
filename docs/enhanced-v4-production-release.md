# DTL Signal Enhanced v4 — Production Release Record

## Approved direction

Proof v4 is the locked product direction. Production must retain the previous email's CEO View wording verbatim, the Think → Decide → Look Up → WE ARE ALIVE → Smile sequence, the restrained 75% WE ARE ALIVE image, quiet licence-compliant attribution and the minimal post-joke footer.

## Live Render state observed 24 August 2026

The current production cron is `dtl-signal` (`crn-d8ouk0bsq97s73fgc36g`), branch `master`, schedule `0 20 * * *` (06:00 AEST), auto-deploy enabled. Its start command remains `python -m src.main --send`.

The live build command still applies four hidden build-time shims: a calendar-derived edition counter, first-item-only gauge label, share block and share-block wiring. These behaviours must be moved into source control before the build command is simplified; otherwise a repository-only deployment would regress edition numbering, gauge labels and referral/share links.

## Durable Signal Memory path

Render cron filesystems are not a safe durable store between builds. Signal already has a full-access Resend API key. Resend's official API now supports:

- `GET https://api.resend.com/emails` to list up to 100 recently sent team emails;
- `GET https://api.resend.com/emails/{id}` to retrieve full HTML and tags for a delivered email.

The production-safe memory strategy is therefore to tag Enhanced deliveries and reconstruct the most recent prior Signal position from the latest successfully delivered Enhanced email. This keeps the memory boundary portable and avoids adding a new database during this release. Local JSON remains a test/offline fallback only.

## Red-Pen proof state — 24 August 2026

The locked Edition 0038 Enhanced proof was regenerated from the existing validated judgement plan. No editorial wording was changed. The masthead tagline and Edition number now use solid `#17A398`; the footer is an underlined solid-teal `→ dtlc.ai` link; the blank row below the masthead rule has been replaced by padding on the rule container; and the WE ARE ALIVE credit is a single licence-compliant line without the ghosted `source · licence` placeholders.

The ambiguous label is now `Financial Times (via Simon Willison)`. Verification confirmed that Simon Willison's page is a link post to the original Financial Times article with Willison's commentary, so this provenance is accurate.

Automated verification reports one CEO View, zero `opacity:` declarations, zero ambiguous source labels, one disambiguated source label, zero legacy `source`/`licence` credit words and one `→ dtlc.ai` footer CTA. The exact proof SHA-256 is `b03c084674677c547214185575a9f989ce4b289b5feee28b654143b19cf6f300`. All 21 Signal unit tests pass.

An internal browser sanity check found no obvious masthead, top-rule, image-credit or footer layout artefacts. This is not a release approval: Gmail mobile, Gmail desktop and Apple Mail remain the governing proof gate.

The live signup page at `https://dtlc.ai/signal` was checked directly. It loaded over HTTPS with the real signup fields and `Send Me the Next DTL Signal` CTA present. The same page also loaded with the approved `ref`, `utm_source`, `utm_medium`, `utm_campaign` and `utm_content` query pattern intact. No test subscriber was submitted.

## Exact proof delivery

The Red-Pen proof was sent only to `paul.ford@gmail.com` from the verified DTL Signal sender with subject `[PROOF] DTL Signal | Edition 0038 | Enhanced v4 Red-Pen`. Resend email ID: `91dbf513-af27-4f7b-86c1-cc131503666a`. Provider status reached `opened` immediately after delivery. This confirms receipt, not rendering quality or which client opened it.

Production and the subscriber audience were not touched. Fordy's visual confirmation is still required separately for Gmail mobile, Gmail desktop and Apple Mail.

### Edition 0042 final-format proof — 27 August 2026

The checksum-locked Edition 0042 proof was sent only to `paul.ford@gmail.com` from `DTL Signal <signal@signal.dtlc.ai>` with subject `[PROOF] DTL Signal | Edition 0042 | Final Format`. The frozen HTML SHA-256 is `e043f2c88984ca9250bbde7b34a3e71ae7eab93fd0591b2a59cf7e2290472255`; its content-bound idempotency key was `dtl-signal-proof-0042-e043f2c88984ca92`.

Resend email ID: `2fad61b5-a31a-409a-a7d6-764588afea0c`. The provider record confirms the intended sender, one recipient, the correct subject and status `opened`. This confirms receipt only; it does not self-certify Gmail mobile, Gmail desktop or Apple Mail rendering. Production and the subscriber audience remain untouched.

## Locked founder and human-close contracts — 27 August 2026

Fordy reconfirmed two reader-facing components after positive audience feedback. `CEO VIEW` is now labelled `FOUNDER'S NOTE`, while preserving the established structure rather than reducing it to a short annotation: one direct headline, substantive founder commentary and a single inline `— Paul` sign-off. The note remains immediately after THE ONE THING. Its editorial wording may change with each edition; its structure and founder voice are locked.

The Daily Dad Joke is mandatory in every edition. It remains governed by the approved 100-joke library and 30-edition recent-repeat protection, and it is the final content block immediately before the minimal footer.

The deterministic proof was rebuilt with these contracts. Automated verification reports one FOUNDER'S NOTE, zero legacy CEO VIEW labels, zero separate `Do something different today` lines, one inline `— Paul`, one Daily Dad Joke and zero opacity declarations. All 22 Signal tests pass. The rebuilt proof SHA-256 is `62b1732fe04bdf2f9d0502d5a25ea57c01b1f0a833634429efdec6528d64fb86`.

Internal browser inspection shows the locked heading-headline-commentary-signoff hierarchy and the joke immediately before the footer. This remains a design sanity check only; a new exact email proof and the three real-client confirmations are still required before production.

## Global photography reference — 27 August 2026

Fordy introduced the Sony World Photography Awards 2015 shortlist article on Bored Panda as the quality reference for a renamed `LET'S NOT FORGET WE ARE ALIVE` section. The reference points toward exceptional, emotionally immediate photography from many countries and categories rather than generic stock imagery.

The Bored Panda article identifies individual works and photographers and links to the World Photography Organisation, but it does not grant DTL Signal commercial reuse rights. It is therefore inspiration and discovery material only. Every selected Signal photograph must still be traced to the original photographer or rights holder and clear the existing real-image, commercial-rights, exact-place/subject, attribution and human-approval gates.

The current Moorea humpback-and-calf proof photograph already clears those gates and can remain the deterministic acceptance asset. The final ordering remains a product decision because both the photography section and Daily Dad Joke have been described as “at the end.” The recommended connected sequence remains photography → Daily Dad Joke → minimal footer, preserving Perspective → Peace → Smile.

## Next issue drafting lock — 27 August 2026

The next scheduled Brisbane issue is Friday 28 August 2026. Using the live calendar-derived production anchor of Edition 0017 on 24 July 2026 and weekday-only progression, the correct next number is Edition 0042. This draft calculation does not mutate production state.

The locked reader sequence for the draft is: THE ONE THING → FOUNDER'S NOTE → THE EVIDENCE → optional Visual Signal → INTERPRETATION / WHAT CHANGED / Executive Actions → COUNTER-SIGNAL / What to Watch → REMEMBER THE WORLD → Daily Dad Joke → minimal footer. REMEMBER THE WORLD is a grounding-through-art moment, not a new business-content stage.

## External references

1. Resend, “List Sent Emails”: https://resend.com/docs/api-reference/emails/list-emails
2. Resend, “Retrieve Sent Email”: https://resend.com/docs/api-reference/emails/retrieve-email
3. Simon Willison, “Anthropic’s best AI model struggles to attract users as cheaper tools thrive”: https://simonwillison.net/2026/Aug/23/anthropics-best-ai-model-struggles-to-attract-users-as-cheaper-t/
4. Bored Panda, “25 Of The Best Photos From The 2015 Sony World Photography Awards Shortlist”: https://www.boredpanda.com/sony-world-photography-awards-2015-shortlist/
