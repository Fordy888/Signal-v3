"""DTL PL Attribution Bridge.

After each Signal edition send, report the delivery mapping
(signalId + subscriberId + resendMessageId) back to the website
so DTL PL can attribute email events to specific editions.
"""
from __future__ import annotations
import logging
import os
import requests

log = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 15


def report_send_results(
    signal_id: int,
    delivery_results: list[dict],
) -> bool:
    """POST delivery mapping to /api/pipeline/send-results.
    
    Args:
        signal_id: The numeric edition number (e.g., 14)
        delivery_results: List of dicts with keys:
            - subscriberId (int): database ID of the subscriber
            - resendMessageId (str): Resend message ID returned on send
    
    Returns:
        True if the report was accepted, False otherwise.
    """
    base_url = os.environ.get("WEBSITE_BASE_URL")
    api_key = os.environ.get("SIGNAL_PIPELINE_API_KEY")

    if not base_url or not api_key:
        log.warning("WEBSITE_BASE_URL or SIGNAL_PIPELINE_API_KEY not set — skipping attribution report")
        return False

    if not delivery_results:
        log.info("No delivery results to report — skipping attribution")
        return True

    url = f"{base_url.rstrip('/')}/api/pipeline/send-results"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "signalId": signal_id,
        "results": delivery_results,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            log.info(
                "DTL PL attribution reported: %d deliveries recorded for %s",
                data.get("recorded", len(delivery_results)),
                signal_id,
            )
            return True
        else:
            log.error(
                "DTL PL attribution failed (HTTP %d): %s",
                resp.status_code,
                resp.text[:200],
            )
            return False
    except requests.exceptions.Timeout:
        log.error("DTL PL attribution timed out after %ds", DEFAULT_TIMEOUT)
        return False
    except Exception as e:
        log.error("DTL PL attribution unexpected error: %s", e)
        return False


def resolve_subscriber_ids(
    recipients: list[dict],
) -> dict[str, int]:
    """Resolve subscriber database IDs by fetching from the API.
    
    Returns a dict mapping email (lowercase) -> subscriber database ID.
    """
    base_url = os.environ.get("WEBSITE_BASE_URL")
    api_key = os.environ.get("SIGNAL_PIPELINE_API_KEY")

    if not base_url or not api_key:
        log.warning("Cannot resolve subscriber IDs — env vars not set")
        return {}

    url = f"{base_url.rstrip('/')}/api/pipeline/subscribers"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        resp = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        subscribers = data.get("subscribers", [])
        return {
            sub["email"].lower().strip(): sub["id"]
            for sub in subscribers
            if "email" in sub and "id" in sub
        }
    except Exception as e:
        log.warning("Failed to resolve subscriber IDs: %s (non-fatal)", e)
        return {}
