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

DEFAULT_TIMEOUT = 30  # seconds (increased for cold-start wake-up)
RETRY_DELAY = 10  # seconds
WARM_UP_ATTEMPTS = 4  # total attempts to reach the website (handles autoscale cold starts)
WARM_UP_DELAY = 15  # seconds between warm-up retries


def _warm_up_website(base_url: str) -> bool:
    """Ping the website to wake it up from autoscale hibernation.
    
    Manus autoscale hosting spins instances down to 0 when inactive.
    The first request after hibernation can take 10-30 seconds to respond.
    This function sends a lightweight ping and waits for the site to be ready.
    
    Returns True if site is reachable, False if all attempts exhausted.
    """
    ping_url = f"{base_url.rstrip('/')}/"
    
    for attempt in range(1, WARM_UP_ATTEMPTS + 1):
        try:
            log.info("Wake-up ping attempt %d/%d → %s", attempt, WARM_UP_ATTEMPTS, ping_url)
            resp = requests.get(ping_url, timeout=DEFAULT_TIMEOUT, allow_redirects=True)
            if resp.status_code < 500:
                log.info("Website is awake (status %d) — ready to fetch subscribers", resp.status_code)
                return True
            else:
                log.warning("Website returned %d on wake-up ping — retrying in %ds...",
                            resp.status_code, WARM_UP_DELAY)
        except requests.exceptions.Timeout:
            log.warning("Wake-up ping timed out (attempt %d/%d) — site may be cold-starting. Waiting %ds...",
                        attempt, WARM_UP_ATTEMPTS, WARM_UP_DELAY)
        except requests.exceptions.ConnectionError as e:
            log.warning("Wake-up ping connection error (attempt %d/%d): %s — waiting %ds...",
                        attempt, WARM_UP_ATTEMPTS, e, WARM_UP_DELAY)
        except Exception as e:
            log.warning("Wake-up ping unexpected error (attempt %d/%d): %s — waiting %ds...",
                        attempt, WARM_UP_ATTEMPTS, e, WARM_UP_DELAY)
        
        if attempt < WARM_UP_ATTEMPTS:
            time.sleep(WARM_UP_DELAY)
    
    log.error("Website failed to wake up after %d attempts (%d seconds total)",
              WARM_UP_ATTEMPTS, WARM_UP_ATTEMPTS * WARM_UP_DELAY)
    return False


def fetch_subscribers() -> list[dict]:
    """Fetch active subscribers from the website API.

    Includes a warm-up step to handle autoscale cold starts.
    Returns list of dicts with keys: email, firstName, subscribedAt.
    Returns empty list on failure (caller should abort send).
    """
    base_url = os.environ.get("WEBSITE_BASE_URL")
    api_key = os.environ.get("SIGNAL_PIPELINE_API_KEY")

    if not base_url or not api_key:
        log.error("WEBSITE_BASE_URL or SIGNAL_PIPELINE_API_KEY not set")
        return []

    # Step 1: Wake up the website (handles autoscale cold starts)
    if not _warm_up_website(base_url):
        log.error("Cannot reach website after warm-up attempts — aborting subscriber fetch")
        return []

    # Step 2: Fetch subscribers from the API
    url = f"{base_url.rstrip('/')}/api/pipeline/subscribers"
    headers = {"Authorization": f"Bearer {api_key}"}

    for attempt in range(3):  # 3 attempts for the actual subscriber fetch
        try:
            resp = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)

            if resp.status_code == 401:
                log.error("Subscriber API returned 401 - API key mismatch. Aborting.")
                return []

            if resp.status_code >= 500:
                if attempt < 2:
                    log.warning("Subscriber API returned %d - retrying in %ds... (attempt %d/3)",
                                resp.status_code, RETRY_DELAY, attempt + 1)
                    time.sleep(RETRY_DELAY)
                    continue
                else:
                    log.error("Subscriber API returned %d on final retry - aborting.",
                              resp.status_code)
                    return []

            resp.raise_for_status()
            data = resp.json()
            subscribers = data.get("subscribers", [])

            if not subscribers:
                log.warning("Subscriber API returned empty list - safety abort")
                return []

            log.info("Fetched %d active subscriber(s) from website API",
                     len(subscribers))
            return subscribers

        except requests.exceptions.Timeout:
            if attempt < 2:
                log.warning("Subscriber API timed out (attempt %d/3) - retrying in %ds...",
                            attempt + 1, RETRY_DELAY)
                time.sleep(RETRY_DELAY)
                continue
            log.error("Subscriber API timed out after all retries")
            return []
        except requests.exceptions.ConnectionError as e:
            if attempt < 2:
                log.warning("Subscriber API connection failed (attempt %d/3): %s - retrying in %ds...",
                            attempt + 1, e, RETRY_DELAY)
                time.sleep(RETRY_DELAY)
                continue
            log.error("Subscriber API connection failed after all retries: %s", e)
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
        resp = requests.get(url, headers=headers, params=params,
                            timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        token = data.get("token")
        if token:
            log.debug("Got unsubscribe token for %s", email)
        return token
    except Exception as e:
        log.warning("Failed to fetch unsubscribe token for %s: %s (non-fatal)",
                    email, e)
        return None
