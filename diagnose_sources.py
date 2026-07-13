"""Source Diagnostic Tool — tests all configured sources and classifies errors.

Run from project root:
  python diagnose_sources.py

Outputs:
  - Console summary
  - data/source_diagnostic_report.json (full structured data)
  - data/source_diagnostic_report.md (human-readable report)
"""
import json
import socket
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import requests
import yaml


# ═══════════════════════════════════════════════════════════════════════════════
# USER-AGENTS (same as production sources.py)
# ═══════════════════════════════════════════════════════════════════════════════

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

SIGNAL_UA = "DTL-Signal/4.1 (+https://dtlc.ai/signal; daily intelligence brief)"
OLD_UA = "DTL Signal/1.0 (Personal intelligence brief; +https://dtlc.ai)"


def classify_error(e: Exception) -> tuple[str, str]:
    """Classify an exception into error type and detail."""
    error_str = str(e).lower()

    if isinstance(e, requests.exceptions.Timeout):
        return "timeout", f"Request timed out: {e}"
    elif isinstance(e, requests.exceptions.SSLError):
        return "ssl", f"SSL/TLS error: {e}"
    elif isinstance(e, requests.exceptions.ConnectionError):
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
                return "http_403", f"Forbidden (403)"
            elif code == 429:
                return "http_429", f"Rate limited (429)"
            elif code == 404:
                return "http_404", f"Not found (404)"
            elif code == 410:
                return "http_410", f"Gone (410) — feed permanently removed"
            elif code == 451:
                return "http_451", f"Unavailable for legal reasons (451)"
            elif 400 <= code < 500:
                return f"http_{code}", f"Client error ({code}): {resp.reason}"
            elif 500 <= code < 600:
                return f"http_{code}", f"Server error ({code}): {resp.reason}"
        return "http_error", f"HTTP error: {e}"
    elif isinstance(e, socket.timeout):
        return "timeout", f"Socket timeout: {e}"
    else:
        return "unknown", f"{type(e).__name__}: {e}"


def test_source(name: str, url: str, category: str) -> dict:
    """Test a single source with multiple User-Agent strategies."""
    result = {
        "name": name,
        "url": url,
        "domain": urlparse(url).netloc,
        "category": category,
        "status": "unknown",
        "error_type": "",
        "error_detail": "",
        "response_code": 0,
        "items_found": 0,
        "duration_ms": 0,
        "ua_that_worked": "",
        "old_ua_works": False,
        "browser_ua_works": False,
        "recommendation": "",
    }

    # Strategy 1: Browser UA (Chrome)
    start = time.time()
    headers_browser = {
        "User-Agent": USER_AGENTS[0],
        "Accept": "application/rss+xml, application/xml, application/atom+xml, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    try:
        resp = requests.get(url, headers=headers_browser, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        result["browser_ua_works"] = True
        result["response_code"] = resp.status_code

        # Try parsing
        parsed = feedparser.parse(resp.content)
        if parsed.entries:
            result["status"] = "success"
            result["items_found"] = len(parsed.entries)
            result["ua_that_worked"] = "browser_chrome"
            result["duration_ms"] = int((time.time() - start) * 1000)
            result["recommendation"] = "keep"
            return result
        elif parsed.bozo:
            result["status"] = "parse_error"
            result["error_type"] = "parse_error"
            result["error_detail"] = f"Feed malformed: {parsed.bozo_exception}"
            result["duration_ms"] = int((time.time() - start) * 1000)
            result["recommendation"] = "investigate_feed_format"
            return result
        else:
            result["status"] = "empty_feed"
            result["error_type"] = "empty_feed"
            result["error_detail"] = "Feed returned 0 entries (valid XML but no content)"
            result["duration_ms"] = int((time.time() - start) * 1000)
            result["recommendation"] = "check_if_feed_moved"
            return result

    except Exception as e:
        error_type, error_detail = classify_error(e)
        result["duration_ms"] = int((time.time() - start) * 1000)

        # If it's a non-retryable error, don't bother with other UAs
        if error_type in ("dns", "http_404", "http_410"):
            result["status"] = "failed"
            result["error_type"] = error_type
            result["error_detail"] = error_detail
            if error_type == "dns":
                result["recommendation"] = "disable_dead_domain"
            elif error_type == "http_404":
                result["recommendation"] = "find_new_feed_url"
            elif error_type == "http_410":
                result["recommendation"] = "disable_permanently_gone"
            return result

        # Save the error but try with old UA
        browser_error_type = error_type
        browser_error_detail = error_detail
        if hasattr(e, 'response') and e.response is not None:
            result["response_code"] = e.response.status_code

    # Strategy 2: Old Signal UA (what we were using before)
    time.sleep(1)
    headers_old = {
        "User-Agent": OLD_UA,
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }

    try:
        resp = requests.get(url, headers=headers_old, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        result["old_ua_works"] = True

        parsed = feedparser.parse(resp.content)
        if parsed.entries:
            result["status"] = "success"
            result["items_found"] = len(parsed.entries)
            result["ua_that_worked"] = "old_signal_ua"
            result["recommendation"] = "keep"
            return result
    except Exception:
        pass

    # Strategy 3: Minimal UA (feedparser default)
    time.sleep(1)
    try:
        parsed = feedparser.parse(url)
        if parsed.entries:
            result["status"] = "success"
            result["items_found"] = len(parsed.entries)
            result["ua_that_worked"] = "feedparser_default"
            result["recommendation"] = "keep_use_feedparser_direct"
            return result
    except Exception:
        pass

    # All strategies failed
    result["status"] = "failed"
    result["error_type"] = browser_error_type
    result["error_detail"] = browser_error_detail

    # Determine recommendation
    if browser_error_type == "timeout":
        result["recommendation"] = "increase_timeout_or_disable"
    elif browser_error_type == "http_403":
        result["recommendation"] = "blocked_needs_different_approach_or_disable"
    elif browser_error_type == "http_429":
        result["recommendation"] = "rate_limited_reduce_frequency"
    elif browser_error_type == "ssl":
        result["recommendation"] = "ssl_issue_check_cert"
    elif browser_error_type in ("connection", "connection_refused", "connection_reset"):
        result["recommendation"] = "connection_issue_may_be_temporary"
    else:
        result["recommendation"] = "investigate_manually"

    return result


def main():
    root = Path(__file__).parent
    config_path = root / "config" / "sources.yaml"

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    feeds = config.get("rss_feeds", [])
    print(f"\n{'═' * 70}")
    print(f"  DTL SIGNAL — SOURCE DIAGNOSTIC")
    print(f"  Testing {len(feeds)} RSS feeds + HackerNews + Reddit")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'═' * 70}\n")

    results = []
    active_feeds = [f for f in feeds if f.get("status", "active") != "disabled"]
    disabled_feeds = [f for f in feeds if f.get("status", "active") == "disabled"]

    print(f"Active feeds to test: {len(active_feeds)}")
    print(f"Disabled feeds (skipped): {len(disabled_feeds)}")
    print()

    for i, feed in enumerate(active_feeds, 1):
        name = feed["name"]
        url = feed["url"]
        category = feed["category"]
        status_tag = " [PROBATION]" if feed.get("status") == "probation" else ""

        print(f"  [{i:2d}/{len(active_feeds)}] {name}{status_tag}...", end=" ", flush=True)
        result = test_source(name, url, category)
        results.append(result)

        if result["status"] == "success":
            print(f"✓ ({result['items_found']} items, {result['duration_ms']}ms, UA: {result['ua_that_worked']})")
        else:
            print(f"✗ [{result['error_type']}] {result['error_detail'][:60]}")

        # Small delay between tests to avoid being rate-limited ourselves
        time.sleep(0.5)

    # Test HackerNews
    print(f"\n  [HN] HackerNews...", end=" ", flush=True)
    try:
        resp = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json",
                           headers={"User-Agent": USER_AGENTS[0]}, timeout=15)
        resp.raise_for_status()
        top_ids = resp.json()[:5]
        hn_result = {
            "name": "HackerNews",
            "url": "https://hacker-news.firebaseio.com/v0/topstories.json",
            "domain": "hacker-news.firebaseio.com",
            "category": "ai_market_signals",
            "status": "success",
            "error_type": "",
            "error_detail": "",
            "items_found": len(top_ids),
            "recommendation": "keep",
        }
        print(f"✓ ({len(top_ids)} top stories accessible)")
    except Exception as e:
        error_type, error_detail = classify_error(e)
        hn_result = {
            "name": "HackerNews",
            "url": "https://hacker-news.firebaseio.com/v0/topstories.json",
            "domain": "hacker-news.firebaseio.com",
            "category": "ai_market_signals",
            "status": "failed",
            "error_type": error_type,
            "error_detail": error_detail,
            "items_found": 0,
            "recommendation": "investigate",
        }
        print(f"✗ [{error_type}] {error_detail[:60]}")
    results.append(hn_result)

    # Test Reddit
    reddit_cfg = config.get("reddit", {})
    if reddit_cfg.get("enabled"):
        for sub in reddit_cfg.get("subreddits", []):
            sub_name = sub["name"]
            url = f"https://www.reddit.com/r/{sub_name}/top.json?t=day&limit=5"
            print(f"  [Reddit] r/{sub_name}...", end=" ", flush=True)
            try:
                resp = requests.get(url, headers={"User-Agent": USER_AGENTS[0]}, timeout=15)
                resp.raise_for_status()
                posts = resp.json().get("data", {}).get("children", [])
                reddit_result = {
                    "name": f"Reddit/{sub_name}",
                    "url": url,
                    "domain": "www.reddit.com",
                    "category": sub.get("category", "opportunity_radar"),
                    "status": "success",
                    "error_type": "",
                    "error_detail": "",
                    "items_found": len(posts),
                    "recommendation": "keep",
                }
                print(f"✓ ({len(posts)} posts)")
            except Exception as e:
                error_type, error_detail = classify_error(e)
                reddit_result = {
                    "name": f"Reddit/{sub_name}",
                    "url": url,
                    "domain": "www.reddit.com",
                    "category": sub.get("category", "opportunity_radar"),
                    "status": "failed",
                    "error_type": error_type,
                    "error_detail": error_detail,
                    "items_found": 0,
                    "recommendation": "investigate",
                }
                print(f"✗ [{error_type}] {error_detail[:60]}")
            results.append(reddit_result)
            time.sleep(1)

    # ═══════════════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════════════
    print(f"\n{'═' * 70}")
    print(f"  DIAGNOSTIC SUMMARY")
    print(f"{'═' * 70}\n")

    succeeded = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "failed"]
    parse_errors = [r for r in results if r["status"] == "parse_error"]
    empty = [r for r in results if r["status"] == "empty_feed"]

    print(f"  Total tested:    {len(results)}")
    print(f"  ✓ Succeeded:     {len(succeeded)}")
    print(f"  ✗ Failed:        {len(failed)}")
    print(f"  ⚠ Parse errors:  {len(parse_errors)}")
    print(f"  ○ Empty feeds:   {len(empty)}")
    print()

    # Error type breakdown
    error_breakdown: dict[str, list] = {}
    for r in failed + parse_errors + empty:
        et = r.get("error_type", "unknown") or "unknown"
        error_breakdown.setdefault(et, []).append(r)

    print(f"  ERROR BREAKDOWN:")
    for et, items in sorted(error_breakdown.items(), key=lambda x: -len(x[1])):
        print(f"    {et:20s}: {len(items):3d} sources")
        for item in items[:3]:
            print(f"      → {item['name']} ({item['domain']})")
        if len(items) > 3:
            print(f"      → ... and {len(items) - 3} more")
    print()

    # Category coverage
    print(f"  CATEGORY COVERAGE (from successful sources):")
    cat_coverage: dict[str, int] = {}
    for r in succeeded:
        cat = r.get("category", "unknown")
        cat_coverage[cat] = cat_coverage.get(cat, 0) + r.get("items_found", 0)
    for cat, count in sorted(cat_coverage.items(), key=lambda x: -x[1]):
        print(f"    {cat:30s}: {count:3d} items")
    print()

    # Recommendations
    print(f"  RECOMMENDATIONS:")
    rec_groups: dict[str, list] = {}
    for r in failed + parse_errors + empty:
        rec = r.get("recommendation", "investigate")
        rec_groups.setdefault(rec, []).append(r["name"])
    for rec, names in sorted(rec_groups.items(), key=lambda x: -len(x[1])):
        print(f"    {rec}: {len(names)} sources")
        for n in names[:5]:
            print(f"      - {n}")
        if len(names) > 5:
            print(f"      - ... and {len(names) - 5} more")
    print()

    # ═══════════════════════════════════════════════════════════════════════
    # SAVE REPORTS
    # ═══════════════════════════════════════════════════════════════════════
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # JSON report
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tested": len(results),
            "succeeded": len(succeeded),
            "failed": len(failed),
            "parse_errors": len(parse_errors),
            "empty_feeds": len(empty),
            "disabled_skipped": len(disabled_feeds),
        },
        "error_breakdown": {et: len(items) for et, items in error_breakdown.items()},
        "category_coverage": cat_coverage,
        "results": results,
    }

    json_path = data_dir / "source_diagnostic_report.json"
    with open(json_path, "w") as f:
        json.dump(report_data, f, indent=2)
    print(f"  JSON report saved: {json_path}")

    # Markdown report
    md_lines = [
        f"# Signal Source Diagnostic Report",
        f"",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Environment:** Sandbox (not Render)",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total tested | {len(results)} |",
        f"| Succeeded | {len(succeeded)} |",
        f"| Failed | {len(failed)} |",
        f"| Parse errors | {len(parse_errors)} |",
        f"| Empty feeds | {len(empty)} |",
        f"| Disabled (skipped) | {len(disabled_feeds)} |",
        f"",
        f"## Error Breakdown",
        f"",
        f"| Error Type | Count | Example Sources |",
        f"|-----------|-------|-----------------|",
    ]
    for et, items in sorted(error_breakdown.items(), key=lambda x: -len(x[1])):
        examples = ", ".join(r["name"] for r in items[:3])
        md_lines.append(f"| {et} | {len(items)} | {examples} |")

    md_lines.extend([
        f"",
        f"## Failed Sources (Full List)",
        f"",
        f"| # | Name | Domain | Category | Error | Recommendation |",
        f"|---|------|--------|----------|-------|----------------|",
    ])
    for i, r in enumerate(sorted(failed + parse_errors + empty, key=lambda x: x["error_type"]), 1):
        md_lines.append(
            f"| {i} | {r['name']} | {r['domain']} | {r['category']} | "
            f"{r['error_type']} | {r['recommendation']} |"
        )

    md_lines.extend([
        f"",
        f"## Successful Sources",
        f"",
        f"| # | Name | Domain | Category | Items | UA Used |",
        f"|---|------|--------|----------|-------|---------|",
    ])
    for i, r in enumerate(succeeded, 1):
        md_lines.append(
            f"| {i} | {r['name']} | {r['domain']} | {r['category']} | "
            f"{r['items_found']} | {r.get('ua_that_worked', 'unknown')} |"
        )

    md_lines.extend([
        f"",
        f"## Category Coverage (Successful Sources Only)",
        f"",
        f"| Category | Items Available |",
        f"|----------|---------------|",
    ])
    for cat, count in sorted(cat_coverage.items(), key=lambda x: -x[1]):
        md_lines.append(f"| {cat} | {count} |")

    md_lines.extend([
        f"",
        f"## Recommendations",
        f"",
    ])
    for rec, names in sorted(rec_groups.items(), key=lambda x: -len(x[1])):
        md_lines.append(f"### {rec.replace('_', ' ').title()} ({len(names)} sources)")
        for n in names:
            md_lines.append(f"- {n}")
        md_lines.append("")

    md_path = data_dir / "source_diagnostic_report.md"
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines))
    print(f"  Markdown report saved: {md_path}")
    print(f"\n{'═' * 70}\n")


if __name__ == "__main__":
    main()
