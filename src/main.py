"""DTL Signal v3 main orchestrator.

Usage:
  python -m src.main --proof     # Proof edition → sends to PROOF_RECIPIENT_EMAIL only
  python -m src.main --send      # Broadcast edition → sends to ALL active subscribers from website API
  python -m src.main --dry-run   # Pipeline runs but no email sent (prints to stdout + recipient list)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

from .sources import fetch_all, get_source_counts
from .scoring import score_items
from .delivery import send_brief
from .attribution import report_send_results, resolve_subscriber_ids
from .signal_gauge import is_gauge_enabled, inject_gauge_into_html, personalise_gauge_for_subscriber

# ─── 0048 editorial layer ───────────────────────────────────────────────────
# CREATE goes through enhanced_renderer, not the flat synthesis renderer. The
# Founder's Note is part of the judgement plan and is drawn by the renderer, so
# there is no separate note-injection stage any more.
from .judgement_plan import generate_judgement_plan, scored_items_to_evidence, drain_shortfalls
from .signal_memory import load_signal_memory, memory_context
from .enhanced_renderer import render_enhanced_email
from .human_signal import load_joke_history, load_jokes, record_joke, select_joke
from .alive_moment import (
    load_alive_history,
    load_alive_moment,
    resolve_alive_moment_path,
    validate_alive_moment,
)
from .share_block import inject_share_block, personalise_share_for_subscriber
from .section_policy import EditionHalt, apply_section_policy, format_omissions
from . import freeze as freeze_store
from .history import load_history, record_edition
from .edition_counter import get_next_edition, increment_edition
from .subscribers import fetch_subscribers
from .qa_gate import (
    run_pre_send_qa,
    create_receipt,
    save_receipt,
    send_receipt_email,
    record_source_failures,
    classify_subscribers,
    build_category_coverage,
    build_failed_source_summary,
)

BRISBANE = ZoneInfo("Australia/Brisbane")


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"signal_{datetime.now(BRISBANE).strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )


def ping_heartbeat() -> None:
    """Ping BetterStack heartbeat on successful completion."""
    url = os.environ.get("BETTERSTACK_HEARTBEAT_URL")
    if not url or len(url) < 10 or not url.startswith("http"):
        log.warning("BETTERSTACK_HEARTBEAT_URL not set or invalid — skipping heartbeat")
        return
    try:
        import requests
        requests.get(url, timeout=10)
        log.info("Heartbeat pinged successfully")
    except Exception as e:
        log.warning("Heartbeat ping failed (non-fatal): %s", e)


def send_alert(subject: str, body: str) -> None:
    """Send an alert email to the proof recipient (Paul) via Resend."""
    try:
        import resend
        api_key = os.environ.get("RESEND_API_KEY")
        alert_to = os.environ.get("PROOF_RECIPIENT_EMAIL", os.environ.get("RECIPIENT_EMAIL"))
        from_email = os.environ.get("RESEND_FROM_EMAIL", "signal@signal.dtlc.ai")

        if not api_key or not alert_to:
            log.warning("Cannot send alert — RESEND_API_KEY or PROOF_RECIPIENT_EMAIL not set")
            return

        resend.api_key = api_key
        resend.Emails.send({
            "from": f"DTL Signal Ops <{from_email}>",
            "to": [alert_to],
            "reply_to": alert_to,
            "subject": f"⚠️ SIGNAL ALERT: {subject}",
            "html": f"""<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px;">
                <h2 style="color:#dc2626;">⚠️ Signal Pipeline Alert</h2>
                <p style="font-size:16px;color:#333;line-height:1.6;">{body}</p>
                <p style="font-size:14px;color:#666;margin-top:24px;">
                    This is an automated alert from the DTL Signal pipeline.<br>
                    Time: {datetime.now(BRISBANE).strftime('%Y-%m-%d %H:%M AEST')}
                </p>
            </div>""",
        })
        log.info("Alert email sent: %s", subject)
    except Exception as e:
        log.warning("Alert email failed (non-fatal): %s", e)


def load_proof_recipient() -> str | None:
    """Get the proof recipient email (Paul's email for review)."""
    return os.environ.get("PROOF_RECIPIENT_EMAIL", os.environ.get("RECIPIENT_EMAIL"))


def load_subscribers_from_yaml(root: Path) -> list[dict]:
    """Load subscriber registry from config/subscribers.yaml (fallback only)."""
    subs_path = root / "config" / "subscribers.yaml"
    if not subs_path.exists():
        log.warning("No subscribers.yaml found")
        return []
    with open(subs_path, "r") as f:
        data = yaml.safe_load(f)
    subscribers = data.get("subscribers", [])
    active = [s for s in subscribers if s.get("active", True)]
    log.info("Loaded %d active subscriber(s) from subscribers.yaml (fallback)", len(active))
    return active


def verify_recipient_integrity(recipients: list[dict]) -> bool:
    """Fail-safe: verify recipient list integrity before sending."""
    if not recipients:
        log.error("FAIL-SAFE: Recipient list is empty")
        return False

    emails = []
    for r in recipients:
        email = r.get("email", "").strip()
        if not email or "@" not in email:
            log.error("FAIL-SAFE: Invalid email found in recipient list: %s", r)
            return False
        emails.append(email.lower())

    unique_emails = set(emails)
    if len(unique_emails) != len(emails):
        dupes = [e for e in emails if emails.count(e) > 1]
        log.error("FAIL-SAFE: Duplicate emails detected: %s", set(dupes))
        return False

    if len(recipients) > 500:
        log.error("FAIL-SAFE: Recipient count (%d) exceeds safety maximum (500). Aborting.", len(recipients))
        return False

    log.info("FAIL-SAFE: Recipient integrity verified — %d unique valid emails", len(recipients))
    return True


def annotate_receipt(receipt, omissions: list, frozen_sha: str = "") -> None:
    """Record graceful omissions and the frozen payload hash on the receipt.

    Omissions use an [OMITTED] prefix so they appear in the receipt detail
    without being read as warnings or critical failures — an omitted optional
    section is a normal outcome, not a fault.
    """
    for omission in omissions:
        receipt.qa_issues.append(f"[OMITTED] {omission}")
    if frozen_sha:
        receipt.qa_issues.append(f"[FROZEN] Payload SHA-256 {frozen_sha}")


def main() -> int:
    parser = argparse.ArgumentParser(description="DTL Signal v3 — daily intelligence brief")
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--proof", action="store_true",
                            help="Proof mode: send to Paul only for review")
    mode_group.add_argument("--send", action="store_true",
                            help="Send mode: broadcast to all active subscribers from website API")
    mode_group.add_argument("--dry-run", action="store_true",
                            help="Dry run: pipeline runs but no email sent")
    parser.add_argument("--save-html", type=str, default=None,
                        help="Also save the brief to this file path")
    parser.add_argument("--force-type", type=str, choices=["daily", "weekly_wrap"],
                        default=None,
                        help="Override day-of-week detection (for testing)")
    args = parser.parse_args()

    # Locate project root (parent of src/)
    root = Path(__file__).resolve().parent.parent

    # Load .env (for local development; on Render, env vars are injected directly)
    env_path = root / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    setup_logging(root / "logs")
    global log
    log = logging.getLogger("dtl_signal")

    start_time = time.time()
    mode = "proof" if args.proof else "send" if args.send else "dry-run"
    log.info("DTL Signal v3 starting (mode=%s) at %s",
             mode, datetime.now(BRISBANE).strftime("%Y-%m-%d %H:%M AEST"))

    # Get code version for traceability in run receipts
    try:
        import subprocess
        code_version = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(root), stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        code_version = "unknown"
    log.info("Code version: %s", code_version)

    # ─── DAY-OF-WEEK ROUTING ──────────────────────────────────────────
    now_brisbane = datetime.now(BRISBANE)
    day_of_week = now_brisbane.weekday()  # 0=Mon, 5=Sat, 6=Sun

    if args.force_type:
        edition_type = args.force_type
        log.info("Edition type forced via --force-type: %s", edition_type)
    elif day_of_week == 6:  # Sunday
        log.info("Sunday — no edition scheduled. Exiting cleanly.")
        return 0
    elif day_of_week == 5:  # Saturday
        edition_type = "weekly_wrap"
        log.info("Saturday detected — running Signal Weekly Wrap")
    else:
        edition_type = "daily"
        log.info("Weekday detected — running Daily Signal")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set. Configure .env or environment.")
        return 1

    # ─── Get source counts for receipt ─────────────────────────────────
    sources_config_path = str(root / "config" / "sources.yaml")
    source_counts = get_source_counts(sources_config_path)
    log.info("Source inventory: %d active, %d disabled, %d on probation",
             source_counts["active"], source_counts["disabled"], source_counts["probation"])

    # ─── Resolve recipient list based on mode ───────────────────────────
    if args.proof:
        # Proof mode: send to Paul only
        proof_email = load_proof_recipient()
        if not proof_email:
            log.error("PROOF_RECIPIENT_EMAIL not set — cannot send proof")
            return 1
        recipients = [{"email": proof_email, "firstName": "Paul"}]
        log.info("PROOF MODE: sending to %s only", proof_email)

    elif args.send:
        # Send mode: fetch all active subscribers from website API
        log.info("SEND MODE: fetching subscribers from website API...")
        api_subscribers = fetch_subscribers()

        if not api_subscribers:
            log.warning("Website API returned no subscribers — trying YAML fallback")
            yaml_subs = load_subscribers_from_yaml(root)
            if yaml_subs:
                recipients = [{"email": s["email"], "firstName": s.get("name", "").split()[0]} for s in yaml_subs]
                log.warning("Using %d subscriber(s) from YAML fallback", len(recipients))
            else:
                log.error("ABORT: No subscribers from API or YAML. Cannot send to 0 people.")
                send_alert(
                    "Subscriber fetch failed — edition NOT sent",
                    "The website API returned no subscribers and the YAML fallback is also empty. "
                    "Today's edition was NOT sent. Please check WEBSITE_BASE_URL and SIGNAL_PIPELINE_API_KEY on Render."
                )
                return 1
        else:
            recipients = api_subscribers
            log.info("Fetched %d active subscriber(s) from website API", len(recipients))

    else:
        # Dry-run mode: fetch from API to show real recipient list
        log.info("DRY-RUN MODE: fetching subscribers from website API for display...")
        api_subscribers = fetch_subscribers()
        if api_subscribers:
            recipients = api_subscribers
        else:
            recipients = [{"email": "dry-run-fallback@example.com", "firstName": "DryRun"}]

    # ─── FAIL-SAFE: Verify recipient list before proceeding ─────────────
    if not verify_recipient_integrity(recipients):
        alert_msg = (
            f"Recipient integrity check failed in {mode} mode. "
            f"Recipient count at time of check: {len(recipients)}. "
            f"Edition was NOT sent. Check pipeline logs on Render for details."
        )
        send_alert("Recipient integrity check FAILED — edition NOT sent", alert_msg)
        return 1

    # ─── FAIL-SAFE: Verify against live subscriber source of truth ──────
    if args.send:
        log.info("FAIL-SAFE: Verifying recipients against live subscriber source of truth...")
        verify_subscribers = fetch_subscribers()
        if verify_subscribers:
            api_count = len(recipients)
            verify_count = len(verify_subscribers)

            if api_count != verify_count:
                log.error(
                    "FAIL-SAFE ABORT: Subscriber count mismatch! "
                    "First fetch: %d, Verification fetch: %d.",
                    api_count, verify_count
                )
                send_alert(
                    f"Count mismatch ({api_count} vs {verify_count}) — edition NOT sent",
                    f"The subscriber API returned {api_count} subscribers on first call but "
                    f"{verify_count} on verification call. Today's edition was NOT sent."
                )
                return 1

            first_emails = set(r["email"].lower().strip() for r in recipients)
            verify_emails = set(r["email"].lower().strip() for r in verify_subscribers)
            if first_emails != verify_emails:
                added = verify_emails - first_emails
                removed = first_emails - verify_emails
                log.error(
                    "FAIL-SAFE ABORT: Subscriber email set mismatch! "
                    "Added: %s, Removed: %s. Edition NOT sent.",
                    added or "none", removed or "none"
                )
                send_alert(
                    "Subscriber list changed between fetches — edition NOT sent",
                    f"Added: {added or 'none'}. Removed: {removed or 'none'}. Edition NOT sent."
                )
                return 1

            log.info("FAIL-SAFE: Source of truth verified — %d subscribers confirmed", api_count)
        else:
            log.warning("FAIL-SAFE: Verification fetch returned empty — proceeding with original list")

    # ─── Pipeline stages ────────────────────────────────────────────────

    # 0. Load edition history and get next edition number
    history_urls = load_history(root)
    log.info("Loaded %d URLs from recent editions for cross-day dedup", len(history_urls))
    edition_number = get_next_edition(root)
    log.info("Next edition number: %04d", edition_number)

    # 1. Fetch raw items (returns tuple with failed sources AND detailed fetch results)
    log.info("Stage 1: Fetching sources...")
    raw_items, failed_sources, fetch_results = fetch_all(sources_config_path, history_urls=history_urls)
    if not raw_items:
        log.warning("No items fetched. Proceeding to graceful quiet-day briefs.")
    else:
        log.info("Stage 1 complete: %d raw items fetched", len(raw_items))

    # Log fetch diagnostics
    sources_succeeded = sum(1 for r in fetch_results if r.success)
    log.info("Source fetch summary: %d succeeded, %d failed out of %d attempted",
             sources_succeeded, len(failed_sources), len(fetch_results))

    # Track source health (consecutive failures)
    degraded_sources = record_source_failures(
        root,
        failed_sources=failed_sources,
        active_sources=source_counts["active_names"],
    )

    # 2. Score items
    log.info("Stage 2: Scoring items...")
    scored = score_items(
        items=raw_items,
        scoring_prompt_path=str(root / "prompts" / "scoring_prompt.md"),
    )
    log.info("Stage 2 complete: %d items survived scoring", len(scored))

    # Build category coverage for QA gate
    category_coverage = build_category_coverage(scored)
    log.info("Category coverage: %s", {k: v for k, v in category_coverage.items() if v > 0})

    # 3. CREATE — structured judgement plan, then the 0048 enhanced render.
    log.info("Stage 3: Building structured judgement plan...")
    memory_path = root / os.environ.get("SIGNAL_MEMORY_PATH", "data/signal_memory.json")
    joke_history_path = root / os.environ.get("SIGNAL_JOKE_HISTORY_PATH", "data/joke_history.json")
    alive_history_path = root / os.environ.get("SIGNAL_ALIVE_HISTORY_PATH", "data/alive_moment_history.json")

    omissions: list = []
    selected_joke = None
    alive_moment = None

    try:
        planner_evidence = scored_items_to_evidence(scored)
        enhanced_plan = generate_judgement_plan(
            evidence_items=planner_evidence,
            prior_memory=memory_context(load_signal_memory(memory_path)),
            prompt_path=root / "prompts" / "judgement_planner_prompt.md",
        )
        for shortfall in drain_shortfalls():
            log.info("Planner content-mix shortfall: %s", shortfall)

        # Dad Joke — optional. A library problem must not cost us the edition.
        try:
            selected_joke = select_joke(
                load_jokes(root / "data" / "dad_jokes.json"),
                edition_number=edition_number,
                recent_ids=load_joke_history(joke_history_path),
            )
        except Exception as exc:
            log.warning("Human Signal unavailable (non-fatal) — %s", exc)

        # Remember the World — optional. Previously this raised AliveMomentError
        # and failed the whole edition when no record existed for the day.
        try:
            alive_path = resolve_alive_moment_path(
                root,
                os.environ.get("SIGNAL_ALIVE_MOMENT_PATH", "data/alive_moments/{date}.json"),
                edition_id=f"{edition_number:04d}",
                edition_date=now_brisbane.strftime("%Y-%m-%d"),
            )
            if alive_path.exists():
                alive_moment = validate_alive_moment(
                    load_alive_moment(alive_path),
                    load_alive_history(alive_history_path),
                    expected_edition_id=f"{edition_number:04d}",
                    expected_date=now_brisbane.strftime("%Y-%m-%d"),
                )
                log.info("REMEMBER THE WORLD validated: %s", alive_moment["id"])
            else:
                log.info("No REMEMBER THE WORLD record at %s", alive_path)
        except Exception as exc:
            alive_moment = None
            log.warning("REMEMBER THE WORLD unavailable (non-fatal) — %s", exc)

        # Graceful omission: mandatory sections halt, optional ones drop out.
        enhanced_plan, alive_moment, selected_joke, omissions = apply_section_policy(
            enhanced_plan, alive_moment=alive_moment, joke=selected_joke
        )
        log.info(format_omissions(omissions))

        html = render_enhanced_email(
            plan=enhanced_plan,
            sources=planner_evidence,
            joke=selected_joke,
            edition_number=edition_number,
            generated_at=now_brisbane,
            alive_moment=alive_moment,
        )
        log.info("Stage 3 complete: %d chars of HTML produced", len(html))
    except EditionHalt as e:
        log.error("Edition halted — %s", e)
        receipt = create_receipt(
            edition_number=edition_number,
            mode=mode,
            sources_active=source_counts["active"],
            sources_disabled=source_counts["disabled"],
            sources_failed=len(failed_sources),
            items_fetched=len(raw_items),
            items_scored=len(scored),
            pipeline_result="held",
            duration_seconds=time.time() - start_time,
            code_version=code_version,
            category_coverage=category_coverage,
            fetch_results=fetch_results,
            edition_type=edition_type,
        )
        receipt.qa_issues = [f"[CRITICAL] Mandatory section: {e}"]
        save_receipt(root, receipt)
        send_receipt_email(receipt)
        return 1
    except Exception as e:
        log.error("Edition creation failed: %s", e)
        receipt = create_receipt(
            edition_number=edition_number,
            mode=mode,
            sources_active=source_counts["active"],
            sources_disabled=source_counts["disabled"],
            sources_failed=len(failed_sources),
            items_fetched=len(raw_items),
            items_scored=len(scored),
            pipeline_result="aborted",
            duration_seconds=time.time() - start_time,
            code_version=code_version,
            category_coverage=category_coverage,
            fetch_results=fetch_results,
            edition_type=edition_type,
        )
        receipt.qa_issues = [f"[CRITICAL] Create: Generation failed with error: {e}"]
        save_receipt(root, receipt)
        send_receipt_email(receipt)
        return 1

    # ─── Stage 3c: Signal Strength Gauge ───────────────────────────────
    if is_gauge_enabled(mode, edition_number):
        log.info("Stage 3c: Injecting Signal Strength Gauge...")
        try:
            html = inject_gauge_into_html(html, scored, edition_number)
            log.info("Stage 3c complete: Gauge injected for edition %04d", edition_number)
        except Exception as e:
            log.warning("Stage 3c: Gauge injection failed (non-fatal) — %s", e)

    # ─── Stage 3d: Share & subscribe block ─────────────────────────────
    # Previously injected by a base64 payload in the Render build command.
    try:
        html = inject_share_block(html, edition_number)
        log.info("Stage 3d complete: Share block injected for edition %04d", edition_number)
    except Exception as e:
        log.warning("Stage 3d: Share block injection failed (non-fatal) — %s", e)

    # Quality gate: block delivery if key synthesis section is missing
    if edition_type == "weekly_wrap":
        has_key_section = ("THE PATTERN" in html and "EXECUTIVE TAKEAWAY" in html)
        gate_label = "Weekly Wrap key sections (Traffic Light + EXECUTIVE TAKEAWAY)"
    else:
        has_key_section = (
            "WHY IT MATTERS" in html          # ai-adoption / focus layouts
            or "EXECUTIVE READ" in html       # legacy flat layout
        )
        gate_label = "Executive Read section (WHY IT MATTERS / EXECUTIVE READ)"

    if not has_key_section:
        log.error("BLOCKED: %s is missing or incomplete.", gate_label)
        send_alert(
            f"Quality gate failed — {gate_label} missing",
            f"The synthesised edition is missing {gate_label}. Edition NOT sent."
        )
        receipt = create_receipt(
            edition_number=edition_number,
            mode=mode,
            sources_active=source_counts["active"],
            sources_disabled=source_counts["disabled"],
            sources_failed=len(failed_sources),
            items_fetched=len(raw_items),
            items_scored=len(scored),
            pipeline_result="held",
            duration_seconds=time.time() - start_time,
            code_version=code_version,
            category_coverage=category_coverage,
            fetch_results=fetch_results,
            edition_type=edition_type,
        )
        receipt.qa_issues = [f"[CRITICAL] Content Quality: {gate_label} is missing or incomplete"]
        save_receipt(root, receipt)
        send_receipt_email(receipt)
        return 1

    # ─── PRE-SEND QA GATE ──────────────────────────────────────────────
    log.info("Running pre-send QA gate...")
    should_send, qa_results = run_pre_send_qa(
        edition_number=edition_number,
        html=html,
        scored_count=len(scored),
        recipient_count=len(recipients),
        sources_failed=len(failed_sources),
        sources_active=source_counts["active"],
        mode=mode,
        root=root,
        scored_items=scored,
        fetch_results=fetch_results,
    )

    if not should_send:
        log.error("PRE-SEND QA GATE FAILED — Edition HELD. Not sending.")
        receipt = create_receipt(
            edition_number=edition_number,
            mode=mode,
            sources_active=source_counts["active"],
            sources_disabled=source_counts["disabled"],
            sources_failed=len(failed_sources),
            sources_on_probation=source_counts["probation"],
            items_fetched=len(raw_items),
            items_scored=len(scored),
            qa_results=qa_results,
            degraded_sources=degraded_sources,
            pipeline_result="held",
            duration_seconds=time.time() - start_time,
            code_version=code_version,
            category_coverage=category_coverage,
            fetch_results=fetch_results,
            edition_type=edition_type,
        )
        save_receipt(root, receipt)
        send_receipt_email(receipt)
        return 1

    # ─── FREEZE ────────────────────────────────────────────────────────
    # The edition has been rendered exactly once and has passed QA. Freeze the
    # exact payload bytes now, before any delivery path can touch them. Proof
    # quotes this hash; approval binds to it; SEND replays these same bytes.
    # Nothing between here and delivery re-renders or mutates the edition.
    subject_line = f"DTL Signal — Edition {edition_number:04d}"
    try:
        freeze_conn = freeze_store.connect(root)
        frozen = freeze_store.freeze_edition(
            freeze_conn, edition_number, subject_line, html
        )
        log.info(
            "Edition %04d frozen: sha256=%s", edition_number, frozen.sha256
        )
        print(f"\nFROZEN PAYLOAD SHA-256: {frozen.sha256}")
    except freeze_store.FreezeError as e:
        log.error("Freeze failed — %s", e)
        send_alert("Freeze failed", str(e))
        return 1

    # Every delivery path from here reads the frozen bytes, never `html`.
    html = frozen.html

    # Save HTML if requested
    if args.save_html:
        save_path = Path(args.save_html)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w") as f:
            # Personalise gauge with proof subscriber hash for saved HTML
            proof_html = personalise_gauge_for_subscriber(html, "proof@dtlc.ai")
            f.write(proof_html)
        log.info("Brief saved to %s", save_path)

    # ─── Dry-run: print recipient list and exit ─────────────────────────
    if args.dry_run:
        print(f"\n{'=' * 60}")
        print(f"DRY RUN — Edition {edition_number:04d}")
        print(f"{'=' * 60}")
        print(f"\nRecipient count: {len(recipients)}")
        print(f"\nRecipient list:")
        for i, r in enumerate(recipients, 1):
            first_name = r.get("firstName") or "?"
            print(f"  {i:2d}. {first_name:15s} — {r['email']}")
        print(f"\n{'=' * 60}")
        print(f"Brief preview ({len(html)} chars total):")
        print("=" * 60 + "\n")
        print(html[:500] + "..." if len(html) > 500 else html)
        print(f"\n{'=' * 60}")
        log.info("Pipeline complete (dry run) in %.1f seconds", time.time() - start_time)

        receipt = create_receipt(
            edition_number=edition_number,
            mode=mode,
            sources_active=source_counts["active"],
            sources_disabled=source_counts["disabled"],
            sources_failed=len(failed_sources),
            sources_on_probation=source_counts["probation"],
            items_fetched=len(raw_items),
            items_scored=len(scored),
            qa_results=qa_results,
            degraded_sources=degraded_sources,
            pipeline_result="success",
            duration_seconds=time.time() - start_time,
            code_version=code_version,
            category_coverage=category_coverage,
            fetch_results=fetch_results,
            edition_type=edition_type,
        )
        annotate_receipt(receipt, omissions, frozen.sha256)
        save_receipt(root, receipt)
        return 0

    # ─── Deliver to all recipients ──────────────────────────────────────
    from .delivery import INTER_SEND_DELAY_S
    log.info("Stage 4: Delivering to %d recipient(s)...", len(recipients))

    success_count = 0
    fail_count = 0
    failed_recipient_emails: list[str] = []
    delivery_map: list[tuple[str, str]] = []  # (email, resend_message_id)

    for i, recipient in enumerate(recipients):
        email = recipient["email"]
        first_name = recipient.get("firstName", "")

        if i > 0:
            time.sleep(INTER_SEND_DELAY_S)

        log.info("  Sending to: %s (%s)", email, first_name or "no name")

        subject_override = None
        if edition_type == "weekly_wrap":
            week_ending = datetime.now(BRISBANE).strftime('%d %B %Y')
            if args.proof:
                subject_override = f"[PROOF] DTL Signal Weekly Wrap | Week Ending {week_ending}"
            else:
                subject_override = f"DTL Signal Weekly Wrap | Week Ending {week_ending}"
        elif args.proof:
            subject_override = f"[PROOF] DTL Signal | Edition {edition_number:04d} | {datetime.now(BRISBANE).strftime('%A %d %B %Y')}"

        # Exactly-once: claim the send-ledger row BEFORE sending, so a crash
        # mid-send can never become a resend. The claim is unique per
        # (edition, recipient).
        try:
            freeze_store.claim_send(freeze_conn, edition_number, email, frozen.sha256)
        except freeze_store.AlreadySent:
            log.warning("  ↷ SKIPPED %s — edition %04d already sent to them",
                        email, edition_number)
            continue

        # Personalise the frozen bytes for this subscriber. This substitutes a
        # placeholder for the subscriber's opaque hash — it is not a re-render,
        # and the frozen payload itself is never modified.
        personalised_html = personalise_gauge_for_subscriber(html, email)
        personalised_html = personalise_share_for_subscriber(
            personalised_html,
            sha256(email.strip().lower().encode()).hexdigest()[:12],
        )
        result = send_brief(
            html_body=personalised_html,
            recipient_email=email,
            subject_override=subject_override,
            edition_number=edition_number,
        )

        if result:
            success_count += 1
            if isinstance(result, str):
                delivery_map.append((email, result))
            log.info("  ✓ Delivered to %s", email)
        else:
            fail_count += 1
            failed_recipient_emails.append(email)
            # Delivery failed, so release the claim and allow a retry.
            freeze_store.release_send(freeze_conn, edition_number, email)
            log.error("  ✗ FAILED to deliver to %s", email)

    # ─── Post-delivery bookkeeping (crash-safe) ─────────────────────────
    duration = time.time() - start_time
    bookkeeping_error = None

    try:
        if args.send and success_count > 0:
            delivered_urls = []
            for item in scored:
                try:
                    url = item.raw.url if hasattr(item, 'raw') else item.get('url', '') if isinstance(item, dict) else ''
                    if url:
                        delivered_urls.append(url)
                except (AttributeError, TypeError):
                    continue
            edition_id = f"edition_{datetime.now(BRISBANE).strftime('%Y%m%d')}"
            record_edition(root, delivered_urls, edition_id=edition_id)
            increment_edition(root)
            log.info("Edition counter incremented. Next edition will be %04d", edition_number + 1)

            # Record the joke so rotation does not repeat it. Only after a real
            # delivery — a proof or dry run must not consume a joke.
            if selected_joke:
                record_joke(joke_history_path, selected_joke["id"])
                log.info("Human Signal %s recorded in rotation history", selected_joke["id"])
    except Exception as e:
        bookkeeping_error = str(e)
        log.error("Post-delivery bookkeeping failed (non-fatal): %s", e)

    # ─── Stage 5: DTL PL Attribution ───────────────────────────────────
    if delivery_map and success_count > 0:
        log.info("Stage 5: Reporting %d delivery(s) to DTL PL...", len(delivery_map))
        try:
            email_to_id = resolve_subscriber_ids(recipients)
            attribution_results = []
            for email_addr, msg_id in delivery_map:
                sub_id = email_to_id.get(email_addr.lower().strip())
                if sub_id:
                    attribution_results.append({
                        "subscriberId": sub_id,
                        "resendMessageId": msg_id,
                    })
                else:
                    log.warning("  No subscriber ID found for %s — skipping attribution", email_addr)
            if attribution_results:
                # Pure Logic API requires signalId as a NUMBER (the edition number).
                # Previously sent "edition_YYYYMMDD" string -> HTTP 400 "signalId (number) is required".
                report_ok = report_send_results(int(edition_number), attribution_results)
                if report_ok:
                    log.info("  ✓ DTL PL attribution complete: %d mappings reported", len(attribution_results))
                else:
                    log.warning("  ✗ DTL PL attribution failed (non-fatal)")
            else:
                log.warning("  No subscriber IDs resolved — attribution skipped")
        except Exception as e:
            log.error("Stage 5 (DTL PL attribution) failed (non-fatal): %s", e)
    elif success_count > 0:
        log.info("Stage 5: No message IDs captured — attribution skipped (Resend may not have returned IDs)")

    # ─── Build and send run receipt (ALWAYS runs) ───────────────────────
    try:
        if fail_count > 0:
            pipeline_result = "partial_failure"
        elif bookkeeping_error:
            pipeline_result = "delivered_bookkeeping_error"
        else:
            pipeline_result = "success"

        # Classify subscribers for insights in the receipt
        sub_insights = classify_subscribers(recipients)
        log.info("Subscriber insights: %d total (%d business / %d personal), %d new today",
                 sub_insights["total"], sub_insights["business"],
                 sub_insights["personal"], sub_insights["new_today"])

        receipt = create_receipt(
            edition_number=edition_number,
            mode=mode,
            sources_active=source_counts["active"],
            sources_disabled=source_counts["disabled"],
            sources_failed=len(failed_sources),
            sources_on_probation=source_counts["probation"],
            items_fetched=len(raw_items),
            items_scored=len(scored),
            recipients_attempted=len(recipients),
            recipients_delivered=success_count,
            recipients_failed=fail_count,
            failed_recipients=failed_recipient_emails,
            qa_results=qa_results,
            degraded_sources=degraded_sources,
            pipeline_result=pipeline_result,
            duration_seconds=duration,
            code_version=code_version,
            subscriber_insights=sub_insights,
            category_coverage=category_coverage,
            fetch_results=fetch_results,
            edition_type=edition_type,
        )

        annotate_receipt(receipt, omissions, frozen.sha256)

        if bookkeeping_error:
            receipt.qa_issues.append(f"[WARNING] Post-delivery bookkeeping error: {bookkeeping_error}")

        save_receipt(root, receipt)
        send_receipt_email(receipt)
    except Exception as e:
        log.error("CRITICAL: Receipt generation failed: %s", e)
        log.error("DELIVERY SUMMARY: %d/%d sent, %d failed. Failed: %s",
                  success_count, len(recipients), fail_count, failed_recipient_emails)

    log.info("Pipeline complete in %.1f seconds. Sent: %d/%d, Failed: %d",
             duration, success_count, len(recipients), fail_count)

    if fail_count > 0:
        ping_heartbeat()
        return 2

    ping_heartbeat()
    return 0


if __name__ == "__main__":
    sys.exit(main())
