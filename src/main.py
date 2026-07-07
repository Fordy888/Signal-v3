"""DTL Signal v1 main orchestrator. Run with: python -m src.main [--dry-run]"""
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


def load_subscribers(root: Path) -> list[dict]:
    """Load subscriber registry from config/subscribers.yaml."""
    subs_path = root / "config" / "subscribers.yaml"
    if not subs_path.exists():
        # Fallback to legacy single-subscriber mode
        log.info("No subscribers.yaml found — using legacy single-subscriber mode")
        return [{
            "id": "paul_ford",
            "name": "Paul Ford",
            "email_env": "RECIPIENT_EMAIL",
            "context_file": "config/context.yaml",
            "edition_prefix": "PF",
            "active": True,
        }]
    with open(subs_path, "r") as f:
        data = yaml.safe_load(f)
    subscribers = data.get("subscribers", [])
    # Filter to active only
    active = [s for s in subscribers if s.get("active", True)]
    log.info("Loaded %d active subscriber(s) from subscribers.yaml", len(active))
    return active


def get_subscriber_email(subscriber: dict) -> str | None:
    """Resolve email address for a subscriber."""
    # Direct email field takes priority
    if subscriber.get("email"):
        return subscriber["email"]
    # Otherwise look up from env var
    env_key = subscriber.get("email_env")
    if env_key:
        return os.environ.get(env_key)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="DTL Signal v1 — daily intelligence brief")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run the pipeline but print the brief to stdout instead of emailing")
    parser.add_argument("--save-html", type=str, default=None,
                        help="Also save the brief to this file path")
    parser.add_argument("--subscriber", type=str, default=None,
                        help="Run for a specific subscriber ID only (default: all active)")
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
    log.info("DTL Signal v1 starting (dry_run=%s) at %s",
             args.dry_run, datetime.now(BRISBANE).strftime("%Y-%m-%d %H:%M AEST"))

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set. Configure .env or environment.")
        return 1

    # Load subscribers
    subscribers = load_subscribers(root)
    if args.subscriber:
        subscribers = [s for s in subscribers if s["id"] == args.subscriber]
        if not subscribers:
            log.error("Subscriber '%s' not found or not active", args.subscriber)
            return 1

    # 0. Load edition history and get next edition number
    history_urls = load_history(root)
    log.info("Loaded %d URLs from recent editions for cross-day dedup", len(history_urls))
    edition_number = get_next_edition(root)
    log.info("Next edition number: %04d", edition_number)

    # 1. Fetch raw items (shared across all subscribers)
    log.info("Stage 1: Fetching sources...")
    raw_items = fetch_all(str(root / "config" / "sources.yaml"), history_urls=history_urls)
    if not raw_items:
        log.warning("No items fetched. Proceeding to graceful quiet-day briefs.")
    else:
        log.info("Stage 1 complete: %d raw items fetched", len(raw_items))

    # 2. Score items (shared across all subscribers)
    log.info("Stage 2: Scoring items...")
    scored = score_items(
        items=raw_items,
        scoring_prompt_path=str(root / "prompts" / "scoring_prompt.md"),
    )
    log.info("Stage 2 complete: %d items survived scoring", len(scored))

    # 3 & 4. Synthesise and deliver for each subscriber
    all_ok = True
    for subscriber in subscribers:
        sub_id = subscriber["id"]
        sub_name = subscriber["name"]
        context_file = subscriber.get("context_file", "config/context.yaml")
        context_path = str(root / context_file)

        log.info("--- Processing subscriber: %s (%s) ---", sub_name, sub_id)

        # Verify context file exists
        if not Path(context_path).exists():
            log.error("Context file not found for %s: %s", sub_id, context_path)
            all_ok = False
            continue

        # Synthesise brief for this subscriber
        log.info("Stage 3 [%s]: Synthesising brief...", sub_id)
        try:
            html = synthesise(
                scored_items=scored,
                context_path=context_path,
                synthesis_prompt_path=str(root / "prompts" / "synthesis_prompt.md"),
                edition_number=edition_number,
            )
            log.info("Stage 3 [%s]: %d chars of HTML produced", sub_id, len(html))
        except Exception as e:
            log.error("Synthesis failed for %s: %s", sub_id, e)
            all_ok = False
            continue

        # --- Quality gate: block delivery if Section 9 (DTLc.ai's Take) is missing ---
        has_section_9 = ("KEY INSIGHT" in html and "STRATEGIC IMPLICATION" in html and "WATCH FOR" in html)
        if not has_section_9:
            log.error("[%s] BLOCKED: Section 9 (DTLc.ai's Take) is missing or incomplete. Email will NOT be sent.", sub_id)
            all_ok = False
            continue

        # Save / deliver
        save_path: Path | None = None
        if args.save_html:
            save_path = Path(args.save_html).with_suffix(f".{sub_id}.html")
        elif args.dry_run:
            save_path = root / "logs" / f"brief_{sub_id}_{datetime.now(BRISBANE).strftime('%Y%m%d_%H%M')}.html"

        if save_path:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "w") as f:
                f.write(html)
            log.info("[%s] Brief saved to %s", sub_id, save_path)

        if args.dry_run:
            print(f"\n{'=' * 60}")
            print(f"DRY RUN — {sub_name} ({sub_id}) brief:")
            print("=" * 60 + "\n")
            print(html[:500] + "..." if len(html) > 500 else html)
            print(f"\n{'=' * 60}")
            if save_path:
                print(f"HTML saved to: {save_path}")
            print("=" * 60)
            continue

        # Real send
        log.info("Stage 4 [%s]: Delivering via Resend...", sub_id)
        recipient = get_subscriber_email(subscriber)
        if not recipient:
            log.error("No email resolved for subscriber %s", sub_id)
            all_ok = False
            continue

        ok = send_brief(html_body=html, recipient_email=recipient, edition_number=edition_number)
        if ok:
            log.info("[%s] Delivery successful to %s", sub_id, recipient)
            # Record delivered item URLs for cross-day dedup
            delivered_urls = [item["url"] for item in scored if "url" in item]
            edition_id = f"{sub_id}_{datetime.now(BRISBANE).strftime('%Y%m%d')}"
            record_edition(root, delivered_urls, edition_id=edition_id)
            # Increment edition counter only on successful send (not proof/dry-run)
            increment_edition(root)
            log.info("Edition counter incremented to %04d", edition_number)
        else:
            log.error("[%s] DELIVERY FAILED to %s", sub_id, recipient)
            all_ok = False

    duration = time.time() - start_time

    if args.dry_run:
        log.info("Pipeline complete (dry run) in %.1f seconds", duration)
        return 0

    if all_ok:
        log.info("Pipeline complete in %.1f seconds. All deliveries successful.", duration)
        ping_heartbeat()
        return 0
    else:
        log.error("Pipeline complete in %.1f seconds. ONE OR MORE DELIVERIES FAILED.", duration)
        # Still ping heartbeat — the pipeline ran, some may have succeeded
        ping_heartbeat()
        return 2


if __name__ == "__main__":
    sys.exit(main())
