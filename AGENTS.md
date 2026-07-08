# AGENTS.md — Signal Pipeline

**Before doing any work on Signal, read these documents in order:**

1. `SIGNAL_CONTEXT.md` — What Signal is, how it operates, operating principles, QA gate, current state.
2. `CONNECTOR_MANIFEST.md` — Connected services, permissions, source-of-truth definitions, change rules.
3. `EDITORIAL.md` — Editorial philosophy and quality principles.

---

## Hard Operating Rule

**Before any Signal work begins, the AI session must:**
1. Read `AGENTS.md` (this file)
2. Read `SIGNAL_CONTEXT.md`
3. Read `CONNECTOR_MANIFEST.md`
4. Read `EDITORIAL.md`

The session must be able to summarise the current Signal operating context before touching code. If it cannot, it has not loaded sufficient context to work safely.

---

## Quick Rules

- Signal is a **live product**, not a prototype.
- **GitHub** (`master`) is the code source of truth. Render auto-deploys from it.
- **Subscriber API** is the recipient source of truth. Never use static lists.
- **QA gate** must pass before any edition sends. Critical failures = hold.
- **Run receipt** must be sent after every run (success or failure).
- **Do not change** send time, from address, reply-to, models, or editorial structure without Paul's approval.
- **Source governance** uses the scoring framework. Respect status fields (active/probation/disabled).

---

## Key Contacts

- **Owner:** Paul Ford (paul.ford@gmail.com)
- **Alerts go to:** paul.ford@gmail.com
- **Receipts go to:** paul.ford@gmail.com

---

## Do Not

- Do not ask Paul to repeat information that is documented in `SIGNAL_CONTEXT.md` or `CONNECTOR_MANIFEST.md`.
- Do not assume connectors are unavailable — check the manifest.
- Do not make changes to production systems without confirming deployment.
- Do not skip the QA gate for any reason.
- Do not send editions with metadata mismatches (date, edition number, weekday).

---

## Context/Version Confirmation

When making changes to Signal, every commit message or report to Paul should confirm:
- Which context documents were read before starting.
- Which commit was the starting point (e.g., "Starting from `93fdc21`").
- The run receipt includes the code commit hash so every edition is traceable to a specific code version.

---

## If Something Breaks

1. Check `SIGNAL_CONTEXT.md` for the current architecture.
2. Check `CONNECTOR_MANIFEST.md` for service configuration.
3. Check Render logs for the specific error.
4. Fix, commit, push. Render auto-deploys.
5. Confirm the fix is live before reporting to Paul.
