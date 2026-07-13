"""
DTL Signal — Beta Subscriber Update Email
"The good, the bad and the ugly — one week into DTL Signal"

Sends a one-off progress update to all active subscribers.
Designed to be triggered manually or via Render cron job at 3:00 PM AEST on 14 July 2026.

Usage:
    python send_subscriber_update.py --send     # Send to all active subscribers
    python send_subscriber_update.py --proof    # Send proof to Paul only
"""
from __future__ import annotations
import argparse
import logging
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import resend

from src.subscribers import fetch_subscribers
from src.delivery import INTER_SEND_DELAY_S, MAX_RETRIES, INITIAL_BACKOFF_S

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

BRISBANE = ZoneInfo("Australia/Brisbane")

SUBJECT = "The good, the bad and the ugly — one week into DTL Signal"

def build_html(first_name: str = "") -> str:
    """Build the subscriber update email HTML."""
    greeting = f"Hi {first_name}," if first_name else "Hi,"
    
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{SUBJECT}</title>
</head>
<body style="margin:0; padding:0; background-color:#ffffff; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; color:#1a1a1a; line-height:1.7;">
<div style="max-width:600px; margin:0 auto; padding:40px 24px;">

<p style="font-size:16px; margin-bottom:24px;">{greeting}</p>

<p style="font-size:16px; margin-bottom:24px;">We are now one week into the DTL Signal beta, and your feedback has already helped improve the product.</p>

<p style="font-size:16px; margin-bottom:8px;"><strong>The good:</strong> the core idea is working. DTL Signal is becoming a concise executive intelligence briefing that helps leaders understand what matters, why it matters and what to do next.</p>

<p style="font-size:16px; margin-bottom:8px;"><strong>The bad:</strong> the early editions contained too much information, some stories were not sufficiently differentiated, and the daily format could feel demanding.</p>

<p style="font-size:16px; margin-bottom:24px;"><strong>The ugly:</strong> we also uncovered a few delivery and operational issues behind the scenes. They have now been identified and fixed.</p>

<p style="font-size:16px; margin-bottom:12px;">Based on the feedback, we have made several important changes:</p>

<ul style="font-size:16px; margin-bottom:24px; padding-left:24px;">
<li style="margin-bottom:8px;">Fewer, stronger stories that can be read in under five minutes</li>
<li style="margin-bottom:8px;">Clear ACT, WATCH and NOTE classifications</li>
<li style="margin-bottom:8px;">Stories organised around business impact, not simply AI news</li>
<li style="margin-bottom:8px;">Three practical Executive Actions at the beginning of each edition</li>
<li style="margin-bottom:8px;">A stronger Executive Read that identifies the pattern behind the headlines</li>
<li style="margin-bottom:8px;">Delivery at approximately 6:30 AM AEST</li>
<li style="margin-bottom:8px;">A new DTL Signal Weekly Wrap every Saturday</li>
<li style="margin-bottom:8px;">No Sunday edition</li>
</ul>

<p style="font-size:16px; margin-bottom:24px;">A few people have also asked about the business model.</p>

<p style="font-size:16px; margin-bottom:24px;">DTL Signal will remain free throughout the beta. Over time, the model is likely to include premium intelligence products, team and enterprise editions, and connections to DTLC.ai training, implementation and strategic advisory services.</p>

<p style="font-size:16px; margin-bottom:24px;">The intention is not to build another advertising-heavy newsletter. The objective is to create a trusted executive intelligence product that delivers genuine value before asking for anything in return.</p>

<p style="font-size:16px; margin-bottom:24px;">Thank you again for being part of the first group. Every open, click, reply and piece of feedback is helping shape what DTL Signal becomes.</p>

<p style="font-size:16px; margin-bottom:4px;">Regards,</p>
<p style="font-size:16px; margin-bottom:4px;"><strong>Paul Ford</strong></p>
<p style="font-size:14px; color:#666; margin-bottom:2px;">Founder, DTL Signal</p>
<p style="font-size:14px; color:#666;">CEO, DTLC.ai</p>

</div>
</body>
</html>"""


def send_update_email(recipient_email: str, first_name: str = "") -> bool:
    """Send the update email to a single recipient."""
    api_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("RESEND_FROM_EMAIL", "signal@signal.dtlc.ai")
    
    if not api_key:
        log.error("RESEND_API_KEY not set")
        return False
    
    resend.api_key = api_key
    
    html = build_html(first_name)
    
    payload = {
        "from": f"Paul Ford <{from_email}>",
        "to": [recipient_email],
        "reply_to": "paul.ford@gmail.com",
        "subject": SUBJECT,
        "html": html,
    }
    
    backoff = INITIAL_BACKOFF_S
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            r = resend.Emails.send(payload)
            email_id = r.get("id") if isinstance(r, dict) else getattr(r, "id", None)
            log.info("Sent to %s (id=%s)", recipient_email, email_id)
            return True
        except Exception as e:
            error_msg = str(e).lower()
            is_rate_limit = "too many requests" in error_msg or "429" in error_msg or "rate" in error_msg
            if is_rate_limit and attempt <= MAX_RETRIES:
                log.warning("Rate limited (attempt %d/%d) — backing off %.1fs", attempt, MAX_RETRIES + 1, backoff)
                time.sleep(backoff)
                backoff *= 2
            else:
                log.error("Failed to send to %s: %s", recipient_email, e)
                return False
    return False


def main():
    parser = argparse.ArgumentParser(description="Send DTL Signal beta subscriber update")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--send", action="store_true", help="Send to all active subscribers")
    group.add_argument("--proof", action="store_true", help="Send proof to Paul only")
    args = parser.parse_args()
    
    start_time = time.time()
    
    if args.proof:
        proof_email = os.environ.get("PROOF_RECIPIENT_EMAIL", "paul.ford@gmail.com")
        log.info("PROOF MODE: Sending to %s only", proof_email)
        ok = send_update_email(proof_email, "Paul")
        if ok:
            log.info("✓ Proof sent successfully")
        else:
            log.error("✗ Proof send failed")
        return 0 if ok else 1
    
    # Send mode: fetch all active subscribers
    log.info("SEND MODE: Fetching active subscribers...")
    subscribers = fetch_subscribers()
    
    if not subscribers:
        log.error("ABORT: No subscribers returned from API. Cannot send to 0 people.")
        return 1
    
    log.info("Sending subscriber update to %d recipients...", len(subscribers))
    
    success_count = 0
    fail_count = 0
    
    for i, sub in enumerate(subscribers):
        email = sub["email"]
        first_name = sub.get("firstName", "")
        
        if i > 0:
            time.sleep(INTER_SEND_DELAY_S)
        
        ok = send_update_email(email, first_name)
        if ok:
            success_count += 1
        else:
            fail_count += 1
            log.error("  ✗ Failed: %s", email)
    
    duration = time.time() - start_time
    log.info("=" * 60)
    log.info("SUBSCRIBER UPDATE COMPLETE")
    log.info("  Sent: %d / %d", success_count, len(subscribers))
    log.info("  Failed: %d", fail_count)
    log.info("  Duration: %.1fs", duration)
    log.info("=" * 60)
    
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    exit(main())
