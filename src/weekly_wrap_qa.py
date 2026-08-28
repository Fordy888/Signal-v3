"""Deterministic structural gate for the Saturday Weekly Wrap."""
from __future__ import annotations

import re


REQUIRED_LABELS = (
    "The Week in One Signal",
    "THE PATTERN",
    "OPPORTUNITY",
    "RISK",
    "What to Watch Next Week",
    "EXECUTIVE TAKEAWAY",
)
FORBIDDEN_PHRASES = ("your pipeline", "your buyer", "quiet today")


def validate_weekly_wrap_html(html: str) -> tuple[bool, list[str]]:
    issues: list[str] = []
    for label in REQUIRED_LABELS:
        if label.lower() not in html.lower():
            issues.append(f"Missing required Weekly Wrap label: {label}")

    story_count = len(re.findall(r"What happened\s*:", html, re.IGNORECASE))
    if story_count != 5:
        issues.append(f"Expected exactly 5 Weekly Wrap stories; found {story_count}")

    source_links = re.findall(r'<a\s+[^>]*href=["\']https://', html, re.IGNORECASE)
    if len(source_links) < 5:
        issues.append(f"Expected at least 5 HTTPS source links; found {len(source_links)}")

    lowered = html.lower()
    if "/api/gauge" in lowered or "rate this signal" in lowered:
        issues.append(
            "Weekly Wrap rating gauge is disabled until story-to-source mapping is deterministic"
        )
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lowered:
            issues.append(f"Forbidden Weekly Wrap phrase: {phrase}")
    return not issues, issues
