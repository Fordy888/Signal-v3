"""Fetch raw items from RSS feeds, HackerNews, and Reddit JSON endpoints."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser
import requests
import yaml

log = logging.getLogger(__name__)


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


def _fetch_rss(name: str, url: str, category: str, ua: str, timeout: int, max_age_hours: int) -> list[RawItem]:
    """Fetch and parse a single RSS feed. Resilient to failure — logs and returns []."""
    try:
        headers = {"User-Agent": ua}
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception as e:
        log.warning("RSS fetch failed for %s (%s): %s", name, url, e)
        return []

    parsed = feedparser.parse(resp.content)
    if parsed.bozo and not parsed.entries:
        log.warning("RSS parse failed for %s: %s", name, parsed.bozo_exception)
        return []

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

    log.info("RSS %s: %d items", name, len(items))
    return items


def _fetch_hackernews(max_items: int, category: str, ua: str, timeout: int) -> list[RawItem]:
    """Fetch HackerNews front page via the official Firebase API."""
    try:
        top_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        resp = requests.get(top_url, headers={"User-Agent": ua}, timeout=timeout)
        resp.raise_for_status()
        top_ids = resp.json()[:max_items]
    except Exception as e:
        log.warning("HackerNews top fetch failed: %s", e)
        return []

    items: list[RawItem] = []
    for hn_id in top_ids:
        try:
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{hn_id}.json"
            r = requests.get(item_url, headers={"User-Agent": ua}, timeout=timeout)
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

    log.info("HackerNews: %d items", len(items))
    return items


def _fetch_reddit(subreddit: str, max_items: int, category: str, ua: str, timeout: int) -> list[RawItem]:
    """Fetch top posts from a subreddit via the public JSON endpoint."""
    try:
        url = f"https://www.reddit.com/r/{subreddit}/top.json?t=day&limit={max_items}"
        resp = requests.get(url, headers={"User-Agent": ua}, timeout=timeout)
        resp.raise_for_status()
        posts = resp.json().get("data", {}).get("children", [])
    except Exception as e:
        log.warning("Reddit fetch failed for r/%s: %s", subreddit, e)
        return []

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

    log.info("Reddit r/%s: %d items", subreddit, len(items))
    return items


def fetch_all(sources_config_path: str, history_urls: set[str] | None = None) -> tuple[list[RawItem], list[str]]:
    """Top-level: fetch from every configured source. Returns raw items, deduplicated by URL.

    Args:
        sources_config_path: Path to sources.yaml
        history_urls: Set of URLs from recent editions (72h) to exclude.

    Returns:
        Tuple of (items, failed_source_names) for receipt tracking.
    """
    config = _load_sources_config(sources_config_path)
    fetch_cfg = config.get("fetch", {})
    ua = fetch_cfg.get("user_agent", "DTL Signal/1.0")
    timeout = fetch_cfg.get("timeout_seconds", 15)
    max_age_hours = fetch_cfg.get("max_age_hours", 48)

    all_items: list[RawItem] = []
    failed_sources: list[str] = []

    # RSS feeds
    for feed in config.get("rss_feeds", []):
        # Skip disabled feeds entirely (saves time and avoids noise in logs)
        status = feed.get("status", "active")
        if status == "disabled":
            continue
        if status == "probation":
            log.info("RSS [PROBATION] %s — fetching but flagged for review", feed["name"])
        items = _fetch_rss(
            name=feed["name"],
            url=feed["url"],
            category=feed["category"],
            ua=ua,
            timeout=timeout,
            max_age_hours=max_age_hours,
        )
        if not items and status != "probation":
            # Only count as failed if it returned nothing (timeout, 4xx, 5xx, parse error)
            failed_sources.append(feed["name"])
        all_items.extend(items)

    # HackerNews
    hn = config.get("hackernews", {})
    if hn.get("enabled"):
        hn_items = _fetch_hackernews(
            max_items=hn.get("max_items", 10),
            category=hn.get("category", "ai_market_signals"),
            ua=ua,
            timeout=timeout,
        )
        if not hn_items:
            failed_sources.append("HackerNews")
        all_items.extend(hn_items)

    # Reddit
    reddit_cfg = config.get("reddit", {})
    if reddit_cfg.get("enabled"):
        for sub in reddit_cfg.get("subreddits", []):
            reddit_items = _fetch_reddit(
                subreddit=sub["name"],
                max_items=sub.get("max_items", 5),
                category=sub.get("category", "opportunity_radar"),
                ua=ua,
                timeout=timeout,
            )
            if not reddit_items:
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

    log.info("Fetched %d items total, %d after dedup, %d source(s) failed",
             len(all_items), len(deduped), len(failed_sources))
    if failed_sources:
        log.warning("Failed sources: %s", ", ".join(failed_sources))

    # Filter out URLs from recent editions (72-hour dedup)
    if history_urls:
        before_history = len(deduped)
        deduped = [item for item in deduped if item.url not in history_urls]
        log.info("History filter removed %d previously-delivered URLs", before_history - len(deduped))

    return deduped, failed_sources
