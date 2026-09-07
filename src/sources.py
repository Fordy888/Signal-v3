"""Fetch raw items from RSS feeds, HackerNews, and Reddit JSON endpoints.

v4.1 — Enhanced with:
- Proper browser-like User-Agent rotation
- Per-source retry with exponential backoff
- Detailed error classification (timeout, DNS, SSL, 403, 429, parse, etc.)
- Structured failure reporting for QA gate and diagnostics
"""
from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import feedparser
import requests
import yaml

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# USER-AGENT ROTATION
# ═══════════════════════════════════════════════════════════════════════════════

# Many RSS feeds block non-browser User-Agents. We use a realistic browser UA
# as the primary, with the Signal identifier as a secondary fallback.
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

# Fallback UA that identifies the bot (used on retry if browser UA is blocked)
SIGNAL_UA = "DTL-Signal/4.1 (+https://dtlc.ai/signal; daily intelligence brief)"


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SourceFetchResult:
    """Detailed result of fetching a single source."""
    name: str
    url: str
    category: str
    success: bool
    items_count: int = 0
    error_type: str = ""  # timeout, dns, ssl, http_403, http_429, http_4xx, http_5xx, parse_error, connection, empty_feed, unknown
    error_detail: str = ""
    response_code: int = 0
    duration_ms: int = 0
    retries_used: int = 0

    @property
    def domain(self) -> str:
        try:
            return urlparse(self.url).netloc
        except Exception:
            return "unknown"


@dataclass
class RawItem:
    """A single raw item before scoring."""
    item_id: str
    title: str
    summary: str
    url: str
    source: str
    category: str
    published_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_scoring_payload(self) -> dict[str, Any]:
        """The compact view sent to the scoring layer."""
        return {
            "item_id": self.item_id,
            "title": self.title,
            "summary": self.summary[:600],  # truncate for cost
            "source": self.source,
            "category": self.category,
            "url": self.url,
        }


def _load_sources_config(path: str) -> dict[str, Any]:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_source_counts(sources_config_path: str) -> dict[str, Any]:
    """Return source status counts for the run receipt.

    Returns dict with keys: active, disabled, probation, active_names
    """
    config = _load_sources_config(sources_config_path)
    feeds = config.get("rss_feeds", [])

    active = 0
    disabled = 0
    probation = 0
    active_names: list[str] = []

    for feed in feeds:
        status = feed.get("status", "active")
        if status == "disabled":
            disabled += 1
        elif status == "probation":
            probation += 1
            active += 1  # probation feeds are still fetched
            active_names.append(feed["name"])
        else:
            active += 1
            active_names.append(feed["name"])

    # Count HackerNews and Reddit as sources if enabled
    hn = config.get("hackernews", {})
    if hn.get("enabled"):
        active += 1
        active_names.append("HackerNews")

    reddit_cfg = config.get("reddit", {})
    if reddit_cfg.get("enabled"):
        for sub in reddit_cfg.get("subreddits", []):
            active += 1
            active_names.append(f"Reddit/{sub['name']}")

    return {
        "active": active,
        "disabled": disabled,
        "probation": probation,
        "active_names": active_names,
    }


def _classify_error(e: Exception) -> tuple[str, str]:
    """Classify an exception into a structured error type and detail string."""
    error_str = str(e).lower()

    if isinstance(e, requests.exceptions.Timeout):
        return "timeout", f"Request timed out: {e}"
    elif isinstance(e, requests.exceptions.SSLError):
        return "ssl", f"SSL/TLS error: {e}"
    elif isinstance(e, requests.exceptions.ConnectionError):
        # Dig deeper into connection errors
        if "name or service not known" in error_str or "nodename nor servname" in error_str:
            return "dns", f"DNS resolution failed: {e}"
        elif "connection refused" in error_str:
            return "connection_refused", f"Connection refused: {e}"
        elif "reset by peer" in error_str:
            return "connection_reset", f"Connection reset by peer: {e}"
        else:
            return "connection", f"Connection error: {e}"
    elif isinstance(e, requests.exceptions.HTTPError):
        resp = e.response
        if resp is not None:
            code = resp.status_code
            if code == 403:
                return "http_403", f"Forbidden (403): likely blocked or requires auth"
            elif code == 429:
                return "http_429", f"Rate limited (429): too many requests"
            elif code == 404:
                return "http_404", f"Not found (404): feed URL may have changed"
            elif code == 410:
                return "http_410", f"Gone (410): feed permanently removed"
            elif code == 451:
                return "http_451", f"Unavailable for legal reasons (451): geo-blocked"
            elif 400 <= code < 500:
                return f"http_{code}", f"Client error ({code}): {resp.reason}"
            elif 500 <= code < 600:
                return f"http_{code}", f"Server error ({code}): {resp.reason}"
        return "http_error", f"HTTP error: {e}"
    elif isinstance(e, socket.timeout):
        return "timeout", f"Socket timeout: {e}"
    else:
        return "unknown", f"Unexpected error: {type(e).__name__}: {e}"


def _fetch_with_retry(
    url: str,
    timeout: int,
    max_retries: int = 2,
    backoff_base: float = 2.0,
) -> tuple[requests.Response | None, str, str, int]:
    """Fetch a URL with retry logic and User-Agent rotation.

    Returns: (response_or_None, error_type, error_detail, retries_used)
    """
    last_error_type = ""
    last_error_detail = ""
    retries_used = 0

    for attempt in range(max_retries + 1):
        # Rotate UA: first attempt uses browser UA, retry uses different browser UA or Signal UA
        if attempt == 0:
            ua = USER_AGENTS[0]
        elif attempt == 1:
            ua = USER_AGENTS[1]
        else:
            ua = SIGNAL_UA

        headers = {
            "User-Agent": ua,
            "Accept": "application/rss+xml, application/xml, application/atom+xml, text/xml, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

        try:
            resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            resp.raise_for_status()
            return resp, "", "", retries_used
        except Exception as e:
            last_error_type, last_error_detail = _classify_error(e)
            retries_used = attempt

            # Don't retry on certain errors (permanent failures)
            if last_error_type in ("dns", "http_404", "http_410", "http_451"):
                break

            # Don't retry on 403 with different UA (already tried)
            if last_error_type == "http_403" and attempt >= 1:
                break

            # Backoff before retry
            if attempt < max_retries:
                wait = backoff_base ** attempt
                log.debug("Retry %d for %s after %.1fs (error: %s)", attempt + 1, url, wait, last_error_type)
                time.sleep(wait)

    return None, last_error_type, last_error_detail, retries_used


def _fetch_rss(name: str, url: str, category: str, timeout: int, max_age_hours: int) -> tuple[list[RawItem], SourceFetchResult]:
    """Fetch and parse a single RSS feed. Returns items and structured fetch result."""
    start = time.time()
    result = SourceFetchResult(name=name, url=url, category=category, success=False)

    # Fetch with retry
    resp, error_type, error_detail, retries = _fetch_with_retry(url, timeout)
    result.retries_used = retries
    result.duration_ms = int((time.time() - start) * 1000)

    if resp is None:
        result.error_type = error_type
        result.error_detail = error_detail
        log.warning("RSS fetch failed for %s (%s): [%s] %s (retries: %d)",
                    name, url, error_type, error_detail, retries)
        return [], result

    result.response_code = resp.status_code

    # Parse the feed
    try:
        parsed = feedparser.parse(resp.content)
    except Exception as e:
        result.error_type = "parse_error"
        result.error_detail = f"feedparser crashed: {e}"
        log.warning("RSS parse crashed for %s: %s", name, e)
        return [], result

    if parsed.bozo and not parsed.entries:
        result.error_type = "parse_error"
        result.error_detail = f"Feed malformed: {parsed.bozo_exception}"
        log.warning("RSS parse failed for %s: %s", name, parsed.bozo_exception)
        return [], result

    if not parsed.entries:
        result.error_type = "empty_feed"
        result.error_detail = "Feed returned 0 entries (valid XML but no content)"
        log.info("RSS %s: empty feed (0 entries)", name)
        return [], result

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    items: list[RawItem] = []
    for i, entry in enumerate(parsed.entries[:20]):  # cap items per feed
        # Determine published time
        published_at: datetime | None = None
        for time_field in ("published_parsed", "updated_parsed"):
            t = entry.get(time_field)
            if t:
                published_at = datetime(*t[:6], tzinfo=timezone.utc)
                break
        if published_at and published_at < cutoff:
            continue  # too old

        title = entry.get("title", "").strip()
        summary = entry.get("summary", "") or entry.get("description", "")
        # Strip basic HTML tags from summary for the scoring payload
        if "<" in summary:
            import re
            summary = re.sub(r"<[^>]+>", " ", summary)
            summary = re.sub(r"\s+", " ", summary).strip()

        url_link = entry.get("link", "")
        if not title or not url_link:
            continue

        items.append(RawItem(
            item_id=f"rss::{name}::{i}::{abs(hash(url_link)) % 10**8}",
            title=title,
            summary=summary[:1000],
            url=url_link,
            source=name,
            category=category,
            published_at=published_at,
        ))

    result.success = True
    result.items_count = len(items)
    log.info("RSS %s: %d items (%.0fms, %d retries)", name, len(items), result.duration_ms, retries)
    return items, result


def _fetch_hackernews(max_items: int, category: str, timeout: int) -> tuple[list[RawItem], SourceFetchResult]:
    """Fetch HackerNews front page via the official Firebase API."""
    start = time.time()
    result = SourceFetchResult(name="HackerNews", url="https://hacker-news.firebaseio.com/v0/topstories.json", category=category, success=False)

    try:
        top_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        headers = {"User-Agent": USER_AGENTS[0]}
        resp = requests.get(top_url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        top_ids = resp.json()[:max_items]
    except Exception as e:
        error_type, error_detail = _classify_error(e)
        result.error_type = error_type
        result.error_detail = error_detail
        result.duration_ms = int((time.time() - start) * 1000)
        log.warning("HackerNews top fetch failed: [%s] %s", error_type, error_detail)
        return [], result

    items: list[RawItem] = []
    for hn_id in top_ids:
        try:
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{hn_id}.json"
            r = requests.get(item_url, headers=headers, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            if not data or data.get("type") != "story":
                continue
            title = data.get("title", "").strip()
            url_link = data.get("url") or f"https://news.ycombinator.com/item?id={hn_id}"
            if not title:
                continue
            ts = data.get("time")
            published_at = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None

            items.append(RawItem(
                item_id=f"hn::{hn_id}",
                title=title,
                summary=f"HackerNews story, {data.get('score', 0)} points, {data.get('descendants', 0)} comments.",
                url=url_link,
                source="HackerNews",
                category=category,
                published_at=published_at,
            ))
        except Exception as e:
            log.debug("HN item %s failed: %s", hn_id, e)
            time.sleep(0.1)
            continue

    result.success = len(items) > 0
    result.items_count = len(items)
    result.duration_ms = int((time.time() - start) * 1000)
    log.info("HackerNews: %d items (%.0fms)", len(items), result.duration_ms)
    return items, result


def _fetch_reddit(subreddit: str, max_items: int, category: str, timeout: int) -> tuple[list[RawItem], SourceFetchResult]:
    """Fetch top posts from a subreddit via the public JSON endpoint."""
    url = f"https://www.reddit.com/r/{subreddit}/top.json?t=day&limit={max_items}"
    start = time.time()
    result = SourceFetchResult(name=f"Reddit/{subreddit}", url=url, category=category, success=False)

    try:
        headers = {"User-Agent": USER_AGENTS[0]}
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        posts = resp.json().get("data", {}).get("children", [])
    except Exception as e:
        error_type, error_detail = _classify_error(e)
        result.error_type = error_type
        result.error_detail = error_detail
        result.duration_ms = int((time.time() - start) * 1000)
        log.warning("Reddit fetch failed for r/%s: [%s] %s", subreddit, error_type, error_detail)
        return [], result

    items: list[RawItem] = []
    for post in posts:
        data = post.get("data", {})
        title = data.get("title", "").strip()
        if not title:
            continue
        permalink = f"https://reddit.com{data.get('permalink', '')}"
        external_url = data.get("url_overridden_by_dest") or permalink
        selftext = (data.get("selftext") or "")[:800]
        ts = data.get("created_utc")
        published_at = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None

        items.append(RawItem(
            item_id=f"reddit::{subreddit}::{data.get('id', '')}",
            title=title,
            summary=f"r/{subreddit} — score {data.get('score', 0)}, {data.get('num_comments', 0)} comments. {selftext}".strip(),
            url=external_url,
            source=f"Reddit r/{subreddit}",
            category=category,
            published_at=published_at,
        ))

    result.success = len(items) > 0
    result.items_count = len(items)
    result.duration_ms = int((time.time() - start) * 1000)
    log.info("Reddit r/%s: %d items (%.0fms)", subreddit, len(items), result.duration_ms)
    return items, result


def fetch_all(sources_config_path: str, history_urls: set[str] | None = None) -> tuple[list[RawItem], list[str], list[SourceFetchResult]]:
    """Top-level: fetch from every configured source. Returns raw items, deduplicated by URL.

    Args:
        sources_config_path: Path to sources.yaml
        history_urls: Set of URLs from recent editions (72h) to exclude.

    Returns:
        Tuple of (items, failed_source_names, all_fetch_results) for receipt tracking and diagnostics.
    """
    config = _load_sources_config(sources_config_path)
    fetch_cfg = config.get("fetch", {})
    timeout = fetch_cfg.get("timeout_seconds", 15)
    max_age_hours = fetch_cfg.get("max_age_hours", 48)

    all_items: list[RawItem] = []
    failed_sources: list[str] = []
    all_results: list[SourceFetchResult] = []

    # RSS feeds
    for feed in config.get("rss_feeds", []):
        # Skip disabled feeds entirely (saves time and avoids noise in logs)
        status = feed.get("status", "active")
        if status == "disabled":
            continue
        if status == "probation":
            log.info("RSS [PROBATION] %s — fetching but flagged for review", feed["name"])

        items, fetch_result = _fetch_rss(
            name=feed["name"],
            url=feed["url"],
            category=feed["category"],
            timeout=timeout,
            max_age_hours=max_age_hours,
        )
        all_results.append(fetch_result)

        if not fetch_result.success:
            failed_sources.append(feed["name"])
        all_items.extend(items)

    # HackerNews
    hn = config.get("hackernews", {})
    if hn.get("enabled"):
        hn_items, hn_result = _fetch_hackernews(
            max_items=hn.get("max_items", 10),
            category=hn.get("category", "ai_market_signals"),
            timeout=timeout,
        )
        all_results.append(hn_result)
        if not hn_result.success:
            failed_sources.append("HackerNews")
        all_items.extend(hn_items)

    # Reddit
    reddit_cfg = config.get("reddit", {})
    if reddit_cfg.get("enabled"):
        for sub in reddit_cfg.get("subreddits", []):
            reddit_items, reddit_result = _fetch_reddit(
                subreddit=sub["name"],
                max_items=sub.get("max_items", 5),
                category=sub.get("category", "opportunity_radar"),
                timeout=timeout,
            )
            all_results.append(reddit_result)
            if not reddit_result.success:
                failed_sources.append(f"Reddit/{sub['name']}")
            all_items.extend(reddit_items)

    # Deduplicate by URL
    seen: set[str] = set()
    deduped: list[RawItem] = []
    for item in all_items:
        if item.url in seen:
            continue
        seen.add(item.url)
        deduped.append(item)

    # Summary logging
    succeeded = sum(1 for r in all_results if r.success)
    log.info("Fetched %d items total, %d after dedup. Sources: %d/%d succeeded, %d failed",
             len(all_items), len(deduped), succeeded, len(all_results), len(failed_sources))

    if failed_sources:
        # Log error type breakdown
        error_breakdown: dict[str, int] = {}
        for r in all_results:
            if not r.success and r.error_type:
                error_breakdown[r.error_type] = error_breakdown.get(r.error_type, 0) + 1
        log.warning("Failed sources breakdown: %s", error_breakdown)
        log.warning("Failed source names: %s", ", ".join(failed_sources[:20]))

    # Filter out URLs from recent editions (72-hour dedup)
    if history_urls:
        before_history = len(deduped)
        deduped = [item for item in deduped if item.url not in history_urls]
        log.info("History filter removed %d previously-delivered URLs", before_history - len(deduped))

    return deduped, failed_sources, all_results
