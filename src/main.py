"""DTL Signal v3 main orchestrator.

Usage:
  python -m src.main --proof     # Proof edition → sends to PROOF_RECIPIENT_EMAIL only
  python -m src.main --send      # Broadcast edition → sends to ALL active subscribers from website API
  python -m src.main --dry-run   # Pipeline runs but no email sent (prints to stdout)
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

from .sources import fetch_all
from .scoring import score_items
from .synthesis import synthesise
from .delivery import send_brief
from .history import load_history, record_edition
from .edition_counter import get_next_edition, increment_edition
from .subscribers import fetch_subscribers

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
    log.info("DTL Signal v3 starting (mode=%s) at %s",
             "proof" if args.proof else "send" if args.send else "dry-run",
             datetime.now(BRISBANE).strftime("%Y-%m-%d %H:%M AEST"))

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set. Configure .env or environment.")
        return 1

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
                return 1
        else:
            recipients = api_subscribers
            log.info("Fetched %d active subscriber(s) from website API", len(recipients))

    else:
        # Dry-run mode: use YAML for display purposes
        recipients = [{"email": "dry-run@example.com", "firstName": "DryRun"}]

    # ─── Pipeline stages ────────────────────────────────────────────────

    # 0. Load edition history and get next edition number
    history_urls = load_history(root)
    log.info("Loaded %d URLs from recent editions for cross-day dedup", len(history_urls))
    edition_number = get_next_edition(root)
    log.info("Next edition number: %04d", edition_number)

    # 1. Fetch raw items
    log.info("Stage 1: Fetching sources...")
    raw_items = fetch_all(str(root / "config" / "sources.yaml"), history_urls=history_urls)
    if not raw_items:
        log.warning("No items fetched. Proceeding to graceful quiet-day briefs.")
    else:
        log.info("Stage 1 complete: %d raw items fetched", len(raw_items))

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
        return 1

    # Quality gate: block delivery if Section 9 (DTLc.ai's Take) is missing
    has_section_9 = ("KEY INSIGHT" in html and "STRATEGIC IMPLICATION" in html and "WATCH FOR" in html)
    if not has_section_9:
        log.error("BLOCKED: Section 9 (DTLc.ai's Take) is missing or incomplete. Email will NOT be sent.")
        return 1

    # Save HTML if requested
    if args.save_html:
        save_path = Path(args.save_html)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w") as f:
            f.write(html)
        log.info("Brief saved to %s", save_path)

    # ─── Dry-run: print and exit ────────────────────────────────────────
    if args.dry_run:
        print(f"\n{'=' * 60}")
        print(f"DRY RUN — Brief preview:")
        print("=" * 60 + "\n")
        print(html[:500] + "..." if len(html) > 500 else html)
        print(f"\n{'=' * 60}")
        log.info("Pipeline complete (dry run) in %.1f seconds", time.time() - start_time)
        return 0

    # ─── Deliver to all recipients ──────────────────────────────────────
    log.info("Stage 4: Delivering to %d recipient(s)...", len(recipients))

    # For proof mode, add [PROOF] prefix to subject
    subject_prefix = "[PROOF] " if args.proof else ""

    success_count = 0
    fail_count = 0

    for recipient in recipients:
        email = recipient["email"]
        first_name = recipient.get("firstName", "")

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
            log.error("  ✗ FAILED to deliver to %s", email)

    # ─── Post-delivery bookkeeping ──────────────────────────────────────
    duration = time.time() - start_time

    if args.send and success_count > 0:
        # Record delivered URLs for cross-day dedup
        delivered_urls = [item["url"] for item in scored if "url" in item]
        edition_id = f"edition_{datetime.now(BRISBANE).strftime('%Y%m%d')}"
        record_edition(root, delivered_urls, edition_id=edition_id)
        # Increment edition counter only on successful broadcast (not proof)
        increment_edition(root)
        log.info("Edition counter incremented. Next edition will be %04d", edition_number + 1)

    log.info("Pipeline complete in %.1f seconds. Sent: %d, Failed: %d",
             duration, success_count, fail_count)

    if fail_count > 0:
        log.error("ONE OR MORE DELIVERIES FAILED.")
        ping_heartbeat()
        return 2

    ping_heartbeat()
    return 0


if __name__ == "__main__":
    sys.exit(main())
