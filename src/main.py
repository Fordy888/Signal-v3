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
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

from .sources import fetch_all, get_source_counts
from .scoring import score_items
from .synthesis import synthesise
from .delivery import send_brief
from .history import load_history, record_edition
from .edition_counter import get_next_edition, increment_edition
from .subscribers import fetch_subscribers
from .qa_gate import (
    run_pre_send_qa,
    create_receipt,
    save_receipt,
    send_receipt_email,
    record_source_failures,
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
    if not url:
        log.warning("BETTERSTACK_HEARTBEAT_URL not set — skipping heartbeat")
        return
    try:
        import requests
        requests.get(url, timeout=10)
        log.info("Heartbeat pinged successfully")
    except Exception as e:
        log.warning("Heartbeat ping failed (non-fatal): %s", e)


def send_alert(subject: str, body: str) -> None:
    """Send an alert email to the proof recipient (Paul) via Resend.
    
    Used for fail-safe notifications when something goes wrong before send.
    Non-fatal: if alert fails, the pipeline still aborts safely.
    """
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
            "from": f"Signal Ops <{from_email}>",
            "to": [alert_to],
            "reply_to": alert_to,
            "subject": f"⚠️ SIGNAL ALERT: {subject}",
            "html": f"""<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px;">
                <h2 style="color:#dc2626;">⚠️ Signal Pipeline Alert</h2>
                <p style="font-size:16px;color:#333;line-height:1.6;">{body}</p>
                <p style="font-size:14px;color:#666;margin-top:24px;">
                    This is an automated alert from the Signal pipeline.<br>
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
    """Fail-safe: verify recipient list integrity before sending.
    
    Checks:
    1. All recipients have valid email addresses
    2. No duplicates in the list
    3. Count is within expected bounds (at least 1, sanity max 500)
    
    Returns True if safe to proceed, False if send should abort.
    """
    if not recipients:
        log.error("FAIL-SAFE: Recipient list is empty")
        return False

    # Check all have email
    emails = []
    for r in recipients:
        email = r.get("email", "").strip()
        if not email or "@" not in email:
            log.error("FAIL-SAFE: Invalid email found in recipient list: %s", r)
            return False
        emails.append(email.lower())

    # Check for duplicates
    unique_emails = set(emails)
    if len(unique_emails) != len(emails):
        dupes = [e for e in emails if emails.count(e) > 1]
        log.error("FAIL-SAFE: Duplicate emails detected: %s", set(dupes))
        return False

    # Sanity bound — if list is suspiciously large, abort
    if len(recipients) > 500:
        log.error("FAIL-SAFE: Recipient count (%d) exceeds safety maximum (500). Aborting.", len(recipients))
        return False

    log.info("FAIL-SAFE: Recipient integrity verified — %d unique valid emails", len(recipients))
    return True


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
            # Safety: if API returns empty, fall back to YAML as last resort
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
        # Double-fetch: verify count AND email set match between two consecutive API calls
        log.info("FAIL-SAFE: Verifying recipients against live subscriber source of truth...")
        verify_subscribers = fetch_subscribers()
        if verify_subscribers:
            api_count = len(recipients)
            verify_count = len(verify_subscribers)

            # Count check
            if api_count != verify_count:
                log.error(
                    "FAIL-SAFE ABORT: Subscriber count mismatch! "
                    "First fetch: %d, Verification fetch: %d. "
                    "Possible race condition or API instability. Edition NOT sent.",
                    api_count, verify_count
                )
                send_alert(
                    f"Count mismatch ({api_count} vs {verify_count}) — edition NOT sent",
                    f"The subscriber API returned {api_count} subscribers on first call but "
                    f"{verify_count} on verification call. This could indicate a race condition, "
                    f"API instability, or data corruption. Today's edition was NOT sent as a safety measure. "
                    f"Please investigate and manually trigger a re-run if appropriate."
                )
                return 1

            # Email-level match: ensure the same set of emails in both fetches
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
                    f"The subscriber API returned different email sets between two consecutive calls. "
                    f"Added: {added or 'none'}. Removed: {removed or 'none'}. "
                    f"This suggests the subscriber list is being modified during the send window. "
                    f"Today's edition was NOT sent. Please investigate."
                )
                return 1

            log.info("FAIL-SAFE: Source of truth verified — %d subscribers confirmed (count + email match)", api_count)
        else:
            log.warning("FAIL-SAFE: Verification fetch returned empty — proceeding with original list (already validated)")

    # ─── Pipeline stages ────────────────────────────────────────────────

    # 0. Load edition history and get next edition number
    history_urls = load_history(root)
    log.info("Loaded %d URLs from recent editions for cross-day dedup", len(history_urls))
    edition_number = get_next_edition(root)
    log.info("Next edition number: %04d", edition_number)

    # 1. Fetch raw items (now returns tuple with failed sources)
    log.info("Stage 1: Fetching sources...")
    raw_items, failed_sources = fetch_all(sources_config_path, history_urls=history_urls)
    if not raw_items:
        log.warning("No items fetched. Proceeding to graceful quiet-day briefs.")
    else:
        log.info("Stage 1 complete: %d raw items fetched", len(raw_items))

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

    # 3. Synthesise brief (one edition for all subscribers — same content)
    log.info("Stage 3: Synthesising brief...")
    context_path = str(root / "config" / "context.yaml")
    if not Path(context_path).exists():
        log.error("Context file not found: %s", context_path)
        return 1

    try:
        html = synthesise(
            scored_items=scored,
            context_path=context_path,
            synthesis_prompt_path=str(root / "prompts" / "synthesis_prompt.md"),
            edition_number=edition_number,
        )
        log.info("Stage 3 complete: %d chars of HTML produced", len(html))
    except Exception as e:
        log.error("Synthesis failed: %s", e)
        # Send receipt for aborted run
        receipt = create_receipt(
            edition_number=edition_number,
            mode=mode,
            sources_active=source_counts["active"],
            sources_disabled=source_counts["disabled"],
            sources_failed=len(failed_sources),
            items_fetched=len(raw_items),
            items_scored=0,
            pipeline_result="aborted",
            duration_seconds=time.time() - start_time,
            code_version=code_version,
        )
        receipt.qa_issues = [f"[CRITICAL] Synthesis: Generation failed with error: {e}"]
        save_receipt(root, receipt)
        send_receipt_email(receipt)
        return 1

    # Quality gate: block delivery if Section 9 (DTLc.ai's Take) is missing
    has_section_9 = ("KEY INSIGHT" in html and "STRATEGIC IMPLICATION" in html and "WATCH FOR" in html)
    if not has_section_9:
        log.error("BLOCKED: Section 9 (DTLc.ai's Take) is missing or incomplete. Email will NOT be sent.")
        send_alert(
            "Quality gate failed — Section 9 missing",
            "The synthesised edition is missing Section 9 (DTLc.ai's Take). "
            "This is a required section. Edition was NOT sent."
        )
        # Send receipt for held run
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
        )
        receipt.qa_issues = ["[CRITICAL] Content Quality: Section 9 (DTLC.ai's Take) is missing or incomplete"]
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
    )

    if not should_send:
        log.error("PRE-SEND QA GATE FAILED — Edition HELD. Not sending.")
        # Build and send receipt for held edition
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
        )
        save_receipt(root, receipt)
        send_receipt_email(receipt)
        return 1

    # Save HTML if requested
    if args.save_html:
        save_path = Path(args.save_html)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w") as f:
            f.write(html)
        log.info("Brief saved to %s", save_path)

    # ─── Dry-run: print recipient list and exit ─────────────────────────
    if args.dry_run:
        print(f"\n{'=' * 60}")
        print(f"DRY RUN — Edition {edition_number:04d}")
        print(f"{'=' * 60}")
        print(f"\nRecipient count: {len(recipients)}")
        print(f"\nRecipient list:")
        for i, r in enumerate(recipients, 1):
            print(f"  {i:2d}. {r.get('firstName', '?'):15s} — {r['email']}")
        print(f"\n{'=' * 60}")
        print(f"Brief preview ({len(html)} chars total):")
        print("=" * 60 + "\n")
        print(html[:500] + "..." if len(html) > 500 else html)
        print(f"\n{'=' * 60}")
        log.info("Pipeline complete (dry run) in %.1f seconds", time.time() - start_time)

        # Still send receipt for dry runs (useful for testing)
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
        )
        save_receipt(root, receipt)
        return 0

    # ─── Deliver to all recipients ──────────────────────────────────────
    log.info("Stage 4: Delivering to %d recipient(s)...", len(recipients))

    success_count = 0
    fail_count = 0
    failed_recipient_emails: list[str] = []

    for i, recipient in enumerate(recipients):
        email = recipient["email"]
        first_name = recipient.get("firstName", "")

        # Rate limit: Resend free tier allows max 2 requests/second.
        # Wait 700ms between sends to stay safely under the limit.
        if i > 0:
            time.sleep(0.7)

        log.info("  Sending to: %s (%s)", email, first_name or "no name")

        subject_override = None
        if args.proof:
            subject_override = f"[PROOF] Signal | Edition {edition_number:04d} | {datetime.now(BRISBANE).strftime('%A %d %B %Y')}"

        ok = send_brief(
            html_body=html,
            recipient_email=email,
            subject_override=subject_override,
            edition_number=edition_number,
        )

        if ok:
            success_count += 1
            log.info("  ✓ Delivered to %s", email)
        else:
            fail_count += 1
            failed_recipient_emails.append(email)
            log.error("  ✗ FAILED to deliver to %s", email)

    # ─── Post-delivery bookkeeping ──────────────────────────────────────
    duration = time.time() - start_time

    if args.send and success_count > 0:
        # Record delivered URLs for cross-day dedup
        delivered_urls = [item.raw.url for item in scored if hasattr(item, 'raw') and item.raw.url]
        edition_id = f"edition_{datetime.now(BRISBANE).strftime('%Y%m%d')}"
        record_edition(root, delivered_urls, edition_id=edition_id)
        # Increment edition counter only on successful broadcast (not proof)
        increment_edition(root)
        log.info("Edition counter incremented. Next edition will be %04d", edition_number + 1)

    # ─── Build and send run receipt ─────────────────────────────────────
    if fail_count > 0:
        pipeline_result = "partial_failure"
    else:
        pipeline_result = "success"

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
    )
    save_receipt(root, receipt)
    send_receipt_email(receipt)

    log.info("Pipeline complete in %.1f seconds. Sent: %d/%d, Failed: %d",
             duration, success_count, len(recipients), fail_count)

    if fail_count > 0:
        ping_heartbeat()
        return 2

    ping_heartbeat()
    return 0


if __name__ == "__main__":
    sys.exit(main())
