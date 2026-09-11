"""Deterministic email-client-safe checks for rendered Signal HTML."""
from __future__ import annotations

import re


FORBIDDEN_MARKUP = (
    "<script",
    "<form",
    "<iframe",
    "position:fixed",
    "position:sticky",
    "display:flex",
    "display:grid",
    "opacity:",
)
UNRESOLVED_TOKENS = ("{{", "}}", "SUBSCRIBER_HASH")


def validate_email_html(html: str) -> tuple[bool, list[str]]:
    issues: list[str] = []
    lowered = html.lower()
    for token in FORBIDDEN_MARKUP:
        if token in lowered:
            issues.append(f"Email-unsafe markup or style: {token}")
    for token in UNRESOLVED_TOKENS:
        if token in html:
            issues.append(f"Unresolved template token: {token}")

    if not re.search(r'<table[^>]+width=["\']100%["\']', html, re.IGNORECASE):
        issues.append("Missing full-width table-based email shell")

    for image in re.findall(r"<img\b[^>]*>", html, re.IGNORECASE):
        if not re.search(r'src=["\']https://', image, re.IGNORECASE):
            issues.append("Image source is not HTTPS")
        if not re.search(r'\balt=["\'][^"\']+["\']', image, re.IGNORECASE):
            issues.append("Image is missing meaningful alt text")
        if not re.search(r'\bwidth=["\']\d+["\']', image, re.IGNORECASE):
            issues.append("Image is missing an explicit email-client width")

    for attribute, url in re.findall(
        r'\b(href|src)=["\']([^"\']+)["\']', html, re.IGNORECASE
    ):
        if attribute.lower() == "href" and url.startswith("mailto:"):
            continue
        if not url.startswith("https://"):
            issues.append(f"Non-HTTPS {attribute.lower()} target: {url}")
    return not issues, issues
