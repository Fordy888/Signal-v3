"""Fetch active subscribers from the DTLC.ai website API.

This module replaces static subscribers.yaml for production use (Phase 2).
Set WEBSITE_BASE_URL and SIGNAL_PIPELINE_API_KEY environment variables.
"""
from __future__ import annotations

import logging
import os
import time

import requests

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15  # seconds
RETRY_DELAY = 5  # seconds


def fetch_subscribers() -> list[dict]:
    """Fetch active subscribers from the website API.

    Returns list of dicts with keys: email, firstName, subscribedAt.
    Returns empty list on failure (caller should abort send).
    """
    base_url = os.environ.get("WEBSITE_BASE_URL")
    api_key = os.environ.get("SIGNAL_PIPELINE_API_KEY")

    if not base_url or not api_key:
        log.error("WEBSITE_BASE_URL or SIGNAL_PIPELINE_API_KEY not set — cannot fetch subscribers")
        return []

    url = f"{base_url.rstrip('/')}/api/pipeline/subscribers"
    headers = {"Authorization": f"Bearer {api_key}"}

    for attempt in range(2):  # 1 retry on 500
        try:
            resp = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)

            if resp.status_code == 401:
                log.error("Subscriber API returned 401 — API key mismatch. Aborting.")
                return []

            if resp.status_code >= 500:
                if attempt == 0:
                    log.warning("Subscriber API returned %d — retrying in %ds...",
                                resp.status_code, RETRY_DELAY)
                    time.sleep(RETRY_DELAY)
                    continue
                else:
                    log.error("Subscriber API returned %d on retry — aborting.", resp.status_code)
                    return []

            resp.raise_for_status()
            data = resp.json()
            subscribers = data.get("subscribers", [])

            if not subscribers:
                log.warning("Subscriber API returned empty list — safety abort (0 subscribers)")
                return []

            log.info("Fetched %d active subscriber(s) from website API", len(subscribers))
            return subscribers

        except requests.exceptions.Timeout:
            log.error("Subscriber API timed out after %ds", DEFAULT_TIMEOUT)
            return []
        except requests.exceptions.ConnectionError as e:
            log.error("Subscriber API connection failed: %s", e)
            return []
        except Exception as e:
            log.error("Subscriber API unexpected error: %s", e)
            return []

    return []


def fetch_unsubscribe_token(email: str) -> str | None:
    """Fetch the unsubscribe token for a specific subscriber.

    Returns the token string, or None on failure.
    """
    base_url = os.environ.get("WEBSITE_BASE_URL")
    api_key = os.environ.get("SIGNAL_PIPELINE_API_KEY")

    if not base_url or not api_key:
        log.error("WEBSITE_BASE_URL or SIGNAL_PIPELINE_API_KEY not set")
        return None

    url = f"{base_url.rstrip('/')}/api/pipeline/subscriber-token"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"email": email}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        token = data.get("token")
        if token:
            log.debug("Got unsubscribe token for %s", email)
        return token
    except Exception as e:
        log.warning("Failed to fetch unsubscribe token for %s: %s (non-fatal)", email, e)
        return None
