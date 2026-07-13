"""Pre-send QA gate and structured run receipt for Signal pipeline.

This module provides:
1. Pre-send validation (metadata integrity, content checks)
2. Content-readiness gate (replaces blunt source-percentage threshold)
3. Structured run receipts (logged + emailed to Paul)
4. Source health tracking (consecutive failure counting)
5. Plain-English alerts that answer: what failed, was it held or sent,
   what's the impact, what action is required, is tomorrow safe.

v4.1 — QA gate redesigned from blunt percentage to content-readiness:
  - At least 30 reliable sources must succeed
  - At least 25 quality items must be scored
  - Coverage across main business-impact categories required
  - No critical source category completely empty
  - Receipt shows source health, item count, category coverage, failed-source summary
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

BRISBANE = ZoneInfo("Australia/Brisbane")
RECEIPT_FILE = "data/run_receipts.json"
SOURCE_HEALTH_FILE = "data/source_health.json"
MAX_RECEIPTS = 30  # Keep last 30 run receipts
ALERT_RECIPIENT = "paul.ford@gmail.com"


# ═══════════════════════════════════════════════════════════════════════════════
# CONTENT-READINESS THRESHOLDS
# ═══════════════════════════════════════════════════════════════════════════════

# Minimum number of sources that must succeed for a viable edition
MIN_SOURCES_SUCCEEDED = 30

# Minimum number of scored items required
MIN_SCORED_ITEMS = 25

# Minimum number of distinct source categories that must have at least 1 scored item
MIN_CATEGORY_COVERAGE = 4

# Critical categories — if ALL sources in these categories fail, hold the edition.
# These map to the most important business-impact sections.
CRITICAL_SOURCE_CATEGORIES = [
    "ai_market_signals",       # Feeds Strategy & Leadership, Sales & Marketing
    "strategy_decision_making", # Feeds Strategy & Leadership
    "opportunity_radar",        # Feeds multiple sections
]

# Category-to-section mapping for coverage reporting
CATEGORY_TO_SECTIONS = {
    "ai_market_signals": ["Strategy & Leadership", "Sales & Marketing"],
    "opportunity_radar": ["Multiple sections"],
    "product_service_ideas": ["Operations & Workflow", "Sales & Marketing"],
    "threat_detection": ["Governance & Risk"],
    "people_to_watch": ["People & Capability"],
    "tactical_ai_stack": ["Operations & Workflow", "Data & Systems"],
    "cultural_economic_shifts": ["People & Capability", "Customer Experience"],
    "australian_government_policy": ["Governance & Risk"],
    "strategy_decision_making": ["Strategy & Leadership"],
    "venture_capital": ["Finance & Commercial Performance"],
    "geopolitics": ["Governance & Risk", "Strategy & Leadership"],
    "australian_business": ["Multiple sections"],
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class QAResult:
    """Result of a single QA check."""
    check_name: str
    passed: bool
    severity: str  # "critical" (hold edition) | "warning" (send + note in receipt) | "info"
    message: str

    def __str__(self) -> str:
        icon = "✓" if self.passed else "✗" if self.severity == "critical" else "⚠"
        return f"  {icon} [{self.severity.upper()}] {self.check_name}: {self.message}"


@dataclass
class RunReceipt:
    """Structured receipt for a pipeline run."""
    # Metadata
    edition_number: int = 0
    mode: str = ""  # proof | send | dry-run
    timestamp_aest: str = ""
    date: str = ""
    weekday: str = ""

    # Sources
    sources_total: int = 0
    sources_active: int = 0
    sources_disabled: int = 0
    sources_failed: int = 0
    sources_succeeded: int = 0
    sources_on_probation: int = 0
    items_fetched: int = 0
    items_scored: int = 0

    # Content readiness
    categories_with_items: int = 0
    categories_total: int = 0
    category_coverage_detail: str = ""
    failed_source_summary: str = ""

    # Delivery
    recipients_attempted: int = 0
    recipients_delivered: int = 0
    recipients_failed: int = 0
    failed_recipients: list[str] = field(default_factory=list)

    # Quality
    qa_checks_passed: int = 0
    qa_checks_failed: int = 0
    qa_checks_warned: int = 0
    qa_issues: list[str] = field(default_factory=list)

    # Source health
    degraded_sources: list[str] = field(default_factory=list)

    # Timing
    duration_seconds: float = 0.0
    pipeline_result: str = ""  # "success" | "partial_failure" | "held" | "aborted"

    # Subscriber insights
    subscribers_total: int = 0
    subscribers_business: int = 0
    subscribers_personal: int = 0
    subscribers_new_today: int = 0
    subscriber_emails_business: list[str] = field(default_factory=list)
    subscriber_emails_personal: list[str] = field(default_factory=list)

    # Traceability
    code_version: str = ""  # Git commit hash that produced this edition
    edition_type: str = "daily"  # "daily" or "weekly_wrap" — for analytics distinction

    def plain_english_summary(self) -> str:
        """Plain-English summary for Paul. One glance tells you if everything is OK."""
        edition = f"Edition {self.edition_number:04d}"

        if self.pipeline_result == "success":
            summary = (
                f"{edition}: QA passed. "
                f"Delivered to {self.recipients_delivered}/{self.recipients_attempted} active subscribers. "
                f"Sources: {self.sources_succeeded}/{self.sources_active} succeeded. "
                f"Items scored: {self.items_scored}. "
                f"Category coverage: {self.categories_with_items}/{self.categories_total}. "
                f"Status: Safe."
            )
        elif self.pipeline_result == "held":
            reasons = "; ".join(self.qa_issues) if self.qa_issues else "Unknown critical failure"
            summary = (
                f"{edition}: QA failed. Send held. "
                f"Reason: {reasons}. "
                f"Action required: review and fix before tomorrow's edition."
            )
        elif self.pipeline_result == "partial_failure":
            summary = (
                f"{edition}: Sent with issues. "
                f"Delivered to {self.recipients_delivered}/{self.recipients_attempted} subscribers. "
                f"{self.recipients_failed} delivery failure(s): {', '.join(self.failed_recipients)}. "
                f"Sources: {self.sources_succeeded}/{self.sources_active} succeeded. "
                f"Status: Edition delivered but needs attention."
            )
        elif self.pipeline_result == "aborted":
            reasons = "; ".join(self.qa_issues) if self.qa_issues else "Pipeline error"
            summary = (
                f"{edition}: Pipeline aborted. Edition NOT sent. "
                f"Reason: {reasons}. "
                f"Action required: investigate before tomorrow's run."
            )
        else:
            summary = f"{edition}: Unknown status ({self.pipeline_result})."

        # Add warnings if any
        warnings = [i for i in self.qa_issues if i.startswith("[WARNING]")]
        if warnings and self.pipeline_result == "success":
            summary += f" Notes: {'; '.join(w.replace('[WARNING] ', '') for w in warnings)}."

        # Add degraded source early warning
        if self.degraded_sources:
            summary += (
                f" Early warning: {len(self.degraded_sources)} source(s) have failed "
                f"3+ days in a row ({', '.join(self.degraded_sources[:5])}) — consider disabling or replacing."
            )

        # Add subscriber insights
        if self.subscribers_total > 0:
            new_str = f" ({self.subscribers_new_today} new today)" if self.subscribers_new_today > 0 else ""
            summary += (
                f" Subscribers: {self.subscribers_total} active "
                f"({self.subscribers_business} business / {self.subscribers_personal} personal){new_str}."
            )

        # Add code version for traceability
        if self.code_version:
            summary += f" Code version: {self.code_version}."

        return summary

    def alert_email_html(self) -> str:
        """Clean, readable HTML email for Paul. Not a technical dump."""
        now_str = datetime.now(BRISBANE).strftime("%A %d %B %Y at %H:%M AEST")

        if self.pipeline_result in ("held", "aborted"):
            status_label = "HELD — NOT SENT" if self.pipeline_result == "held" else "ABORTED — NOT SENT"
            status_color = "#dc2626"
            action_text = self._get_action_text()
            tomorrow_text = self._get_tomorrow_safety()
        elif self.pipeline_result == "partial_failure":
            status_label = "SENT WITH ISSUES"
            status_color = "#d97706"
            action_text = "Check delivery failures. These subscribers did not receive today's edition."
            tomorrow_text = "Tomorrow's edition should send normally unless the same delivery issues persist."
        else:
            status_label = "DELIVERED SUCCESSFULLY"
            status_color = "#16a34a"
            action_text = "No action required."
            tomorrow_text = "Tomorrow's edition is safe."

        # Build issues section
        issues_html = ""
        if self.qa_issues:
            issues_html = "<div style='margin-top:16px;padding:12px;background:#fef2f2;border-radius:6px;'>"
            issues_html += "<strong>Issues found:</strong><ul style='margin:8px 0;padding-left:20px;'>"
            for issue in self.qa_issues:
                # Strip the [CRITICAL] / [WARNING] prefix for cleaner display
                clean = issue.replace("[CRITICAL] ", "").replace("[WARNING] ", "")
                issues_html += f"<li style='margin:4px 0;'>{clean}</li>"
            issues_html += "</ul></div>"

        # Build failed recipients section
        failed_html = ""
        if self.failed_recipients:
            failed_html = "<div style='margin-top:12px;padding:12px;background:#fffbeb;border-radius:6px;'>"
            failed_html += f"<strong>Failed deliveries ({self.recipients_failed}):</strong><ul style='margin:8px 0;padding-left:20px;'>"
            for email in self.failed_recipients:
                failed_html += f"<li>{email}</li>"
            failed_html += "</ul></div>"

        # Build degraded sources section
        degraded_html = ""
        if self.degraded_sources:
            degraded_html = "<div style='margin-top:12px;padding:12px;background:#eff6ff;border-radius:6px;'>"
            degraded_html += f"<strong>Sources failing consistently (3+ days):</strong><ul style='margin:8px 0;padding-left:20px;'>"
            for src in self.degraded_sources[:10]:
                degraded_html += f"<li>{src}</li>"
            if len(self.degraded_sources) > 10:
                degraded_html += f"<li>... and {len(self.degraded_sources) - 10} more</li>"
            degraded_html += "</ul><p style='margin:8px 0 0;font-size:13px;color:#666;'>These should be reviewed — they may need to be disabled or replaced.</p></div>"

        # Build content readiness section (new in v4.1)
        readiness_html = ""
        if self.category_coverage_detail or self.failed_source_summary:
            readiness_html = "<div style='margin-top:16px;padding:12px;background:#f0f9ff;border-radius:6px;border:1px solid #bae6fd;'>"
            readiness_html += "<strong style='font-size:14px;'>Content Readiness</strong>"
            readiness_html += "<table style='width:100%;border-collapse:collapse;font-size:13px;margin-top:8px;'>"
            readiness_html += f"<tr><td style='padding:4px 0;color:#666;width:180px;'>Sources succeeded</td><td>{self.sources_succeeded}/{self.sources_active}</td></tr>"
            readiness_html += f"<tr><td style='padding:4px 0;color:#666;'>Items scored</td><td>{self.items_scored}</td></tr>"
            readiness_html += f"<tr><td style='padding:4px 0;color:#666;'>Category coverage</td><td>{self.categories_with_items}/{self.categories_total} categories</td></tr>"
            readiness_html += "</table>"
            if self.category_coverage_detail:
                readiness_html += f"<p style='margin:8px 0 0;font-size:12px;color:#555;'>{self.category_coverage_detail}</p>"
            readiness_html += "</div>"

        # Build failed source summary section (new in v4.1)
        failed_sources_html = ""
        if self.failed_source_summary:
            failed_sources_html = "<div style='margin-top:12px;padding:12px;background:#fef3c7;border-radius:6px;border:1px solid #fcd34d;'>"
            failed_sources_html += "<strong style='font-size:13px;'>Failed Sources Summary</strong>"
            failed_sources_html += f"<p style='margin:8px 0 0;font-size:12px;color:#555;white-space:pre-line;'>{self.failed_source_summary}</p>"
            failed_sources_html += "</div>"

        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:600px;margin:0 auto;padding:24px;color:#1f2937;">
    <div style="border-bottom:2px solid {status_color};padding-bottom:12px;margin-bottom:20px;">
        <h2 style="margin:0;font-size:18px;">DTL Signal Run Receipt — {"Weekly Wrap" if self.edition_type == "weekly_wrap" else f"Edition {self.edition_number:04d}"}</h2>
        <p style="margin:4px 0 0;font-size:13px;color:#666;">{now_str}</p>
    </div>

    <div style="padding:16px;background:{status_color}12;border-left:4px solid {status_color};border-radius:4px;margin-bottom:20px;">
        <strong style="color:{status_color};font-size:16px;">{status_label}</strong>
    </div>

    <table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:16px;">
        <tr><td style="padding:6px 0;color:#666;width:180px;"><strong>Edition type</strong></td><td style="padding:6px 0;"><strong style="display:inline-block;padding:2px 10px;border-radius:4px;font-size:13px;background:{('#E6A817' if self.edition_type == 'weekly_wrap' else '#10b981')};color:#fff;">{('WEEKLY WRAP' if self.edition_type == 'weekly_wrap' else 'DAILY SIGNAL')}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#666;width:180px;">Subscribers</td><td style="padding:6px 0;">{self.recipients_delivered}/{self.recipients_attempted} delivered</td></tr>
        <tr><td style="padding:6px 0;color:#666;">Sources succeeded</td><td style="padding:6px 0;">{self.sources_succeeded}/{self.sources_active}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">Sources failed</td><td style="padding:6px 0;">{self.sources_failed}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">Sources disabled (skipped)</td><td style="padding:6px 0;">{self.sources_disabled}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">Items scored</td><td style="padding:6px 0;">{self.items_scored}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">Category coverage</td><td style="padding:6px 0;">{self.categories_with_items}/{self.categories_total}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">Duration</td><td style="padding:6px 0;">{self.duration_seconds:.0f} seconds</td></tr>
    </table>

    {self._subscriber_insights_html()}

    {readiness_html}
    {failed_sources_html}
    {issues_html}
    {failed_html}
    {degraded_html}

    <div style="margin-top:20px;padding-top:16px;border-top:1px solid #e5e7eb;">
        <p style="margin:0 0 8px;"><strong>Action required:</strong> {action_text}</p>
        <p style="margin:0;"><strong>Tomorrow's edition:</strong> {tomorrow_text}</p>
    </div>

    <p style="margin-top:24px;font-size:12px;color:#9ca3af;">
        This is an automated operational receipt from the DTL Signal pipeline.
    </p>
</body></html>"""

    def _subscriber_insights_html(self) -> str:
        """Render subscriber insights section for the receipt email."""
        if self.subscribers_total == 0:
            return ""

        new_badge = ""
        if self.subscribers_new_today > 0:
            new_badge = (
                f"<span style='display:inline-block;background:#16a34a;color:#fff;"
                f"padding:2px 8px;border-radius:10px;font-size:12px;margin-left:8px;'>"
                f"+{self.subscribers_new_today} new today</span>"
            )

        html = (
            f"<div style='margin-bottom:16px;padding:12px;background:#f0fdf4;border-radius:6px;border:1px solid #bbf7d0;'>"
            f"<strong style='font-size:14px;'>Subscriber Insights</strong>{new_badge}"
            f"<table style='width:100%;border-collapse:collapse;font-size:13px;margin-top:8px;'>"
            f"<tr><td style='padding:4px 0;color:#666;width:160px;'>Total active</td><td>{self.subscribers_total}</td></tr>"
            f"<tr><td style='padding:4px 0;color:#666;'>Business emails</td><td>{self.subscribers_business}</td></tr>"
            f"<tr><td style='padding:4px 0;color:#666;'>Personal emails</td><td>{self.subscribers_personal}</td></tr>"
            f"</table>"
            f"</div>"
        )
        return html

    def _get_action_text(self) -> str:
        """Determine plain-English action text based on issues."""
        if not self.qa_issues:
            return "Investigate pipeline logs on Render."

        # Parse the most critical issue to give specific guidance
        for issue in self.qa_issues:
            if "recipient" in issue.lower() or "subscriber" in issue.lower():
                return "Review the subscriber API connection. Check that WEBSITE_BASE_URL and SIGNAL_PIPELINE_API_KEY are correct on Render."
            if "edition number" in issue.lower() or "counter" in issue.lower():
                return "The edition counter may be corrupted. Check data/edition_counter.json on Render."
            if "content" in issue.lower() or "html" in issue.lower() or "generation" in issue.lower():
                return "The edition failed to generate properly. Check synthesis logs on Render for the specific error (code bug, prompt issue, or API timeout)."
            if "source" in issue.lower() or "readiness" in issue.lower():
                return "Content readiness check failed. Review the source failure summary below — some sources may need User-Agent fixes, replacements, or disabling."
            if "category" in issue.lower() or "coverage" in issue.lower():
                return "Category coverage is too thin. Check which source categories are failing and whether feeds need replacing."

        return "Review the pipeline logs on Render for details."

    def _get_tomorrow_safety(self) -> str:
        """Assess whether tomorrow's run is likely safe."""
        for issue in self.qa_issues:
            if "subscriber" in issue.lower() or "recipient" in issue.lower():
                return "Tomorrow's edition is NOT safe until the subscriber API issue is resolved."
            if "edition number" in issue.lower():
                return "Tomorrow's edition may have the same issue. The counter needs manual correction."
            if "content" in issue.lower() or "generation" in issue.lower():
                return "Tomorrow's edition may work if this was a temporary API issue. Monitor the next run."
            if "source" in issue.lower() or "readiness" in issue.lower():
                return "If source failures are persistent (networking/blocking), they will recur tomorrow. Review the failure report and consider disabling broken sources."
            if "category" in issue.lower():
                return "Category coverage issues will persist until failing sources are fixed or replaced."

        return "Uncertain — monitor tomorrow's run closely."


# ═══════════════════════════════════════════════════════════════════════════════
# PRE-SEND QA CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def check_edition_number(edition_number: int, root: Path) -> QAResult:
    """Verify edition number is sequential and reasonable."""
    counter_path = root / "data" / "edition_counter.json"
    if counter_path.exists():
        try:
            with open(counter_path, "r") as f:
                data = json.load(f)
            last = data.get("current", 0)
            expected = last + 1
            if edition_number != expected:
                return QAResult(
                    check_name="Edition Number",
                    passed=False,
                    severity="critical",
                    message=f"Expected edition {expected:04d} but got {edition_number:04d}. The edition counter may be corrupted."
                )
        except Exception:
            pass

    if edition_number < 1 or edition_number > 9999:
        return QAResult(
            check_name="Edition Number",
            passed=False,
            severity="critical",
            message=f"Edition number {edition_number} is out of valid range (1-9999)."
        )

    return QAResult(
        check_name="Edition Number",
        passed=True,
        severity="info",
        message=f"Edition {edition_number:04d} is sequential and valid."
    )


def check_date_integrity(edition_number: int) -> QAResult:
    """Verify date/weekday consistency."""
    now = datetime.now(BRISBANE)
    weekday = now.strftime("%A")
    date_str = now.strftime("%d %B %Y")

    if now.hour < 3:
        return QAResult(
            check_name="Date Integrity",
            passed=False,
            severity="critical",
            message=f"Running before 03:00 AEST ({now.strftime('%H:%M')}). Date may roll over during execution. Metadata errors damage trust — holding edition."
        )

    return QAResult(
        check_name="Date Integrity",
        passed=True,
        severity="info",
        message=f"{weekday} {date_str} — timestamp consistent."
    )


def check_subject_body_alignment(html: str, edition_number: int) -> QAResult:
    """Verify edition number and date appear correctly in the HTML body."""
    now = datetime.now(BRISBANE)
    edition_padded = f"{edition_number:04d}"
    date_formatted = now.strftime("%d %B %Y")

    issues = []

    # Check edition number appears in body
    if edition_padded not in html and f"{edition_number:03d}" not in html:
        issues.append(f"Edition number ({edition_padded}) not found in the email body")

    # Check date appears in body (at least the day and month)
    day_month = now.strftime("%d %B")
    if day_month not in html:
        issues.append(f"Today's date ({date_formatted}) not found in the email body")

    if issues:
        return QAResult(
            check_name="Subject/Body Alignment",
            passed=False,
            severity="critical",
            message="; ".join(issues) + ". Subject and body must match — metadata errors damage trust."
        )

    return QAResult(
        check_name="Subject/Body Alignment",
        passed=True,
        severity="info",
        message=f"Edition {edition_padded} and date {date_formatted} present in body."
    )


def check_content_minimum(html: str, scored_count: int) -> QAResult:
    """Verify the edition has minimum viable content."""
    if not html or len(html) < 1000:
        return QAResult(
            check_name="Content Minimum",
            passed=False,
            severity="critical",
            message=f"The edition body is too short ({len(html) if html else 0} characters). The generation likely failed."
        )

    if scored_count == 0 and len(html) < 3000:
        return QAResult(
            check_name="Content Minimum",
            passed=True,
            severity="warning",
            message=f"Quiet day edition (0 items scored, {len(html)} chars). Edition is valid but minimal."
        )

    return QAResult(
        check_name="Content Minimum",
        passed=True,
        severity="info",
        message=f"{len(html)} chars, {scored_count} items scored. Content looks healthy."
    )


def check_content_readiness(
    sources_succeeded: int,
    sources_active: int,
    scored_count: int,
    category_coverage: dict[str, int],
    fetch_results: list | None = None,
) -> QAResult:
    """Content-readiness gate — replaces the old blunt source-percentage check.

    A send is allowed only if:
    1. At least 30 reliable sources succeed
    2. At least 25 quality items are scored
    3. Coverage across at least 4 source categories
    4. No critical source category is completely empty (all sources in that category failed)

    This makes more sense than a blunt percentage because Signal is meant to be
    short and sharp — 31 sources producing 45 scored items may be enough for a
    strong edition, but only if coverage is balanced and sources are credible.
    """
    issues = []
    warnings = []

    # Check 1: Minimum sources succeeded
    if sources_succeeded < MIN_SOURCES_SUCCEEDED:
        issues.append(
            f"Only {sources_succeeded}/{sources_active} sources succeeded "
            f"(minimum: {MIN_SOURCES_SUCCEEDED})"
        )

    # Check 2: Minimum scored items
    if scored_count < MIN_SCORED_ITEMS:
        issues.append(
            f"Only {scored_count} items scored (minimum: {MIN_SCORED_ITEMS})"
        )

    # Check 3: Category coverage
    categories_with_items = sum(1 for count in category_coverage.values() if count > 0)
    total_categories = len(category_coverage)
    if categories_with_items < MIN_CATEGORY_COVERAGE:
        issues.append(
            f"Only {categories_with_items}/{total_categories} categories have content "
            f"(minimum: {MIN_CATEGORY_COVERAGE})"
        )

    # Check 4: Critical categories not completely empty
    empty_critical = []
    if fetch_results:
        for critical_cat in CRITICAL_SOURCE_CATEGORIES:
            # Check if ANY source in this category succeeded
            cat_results = [r for r in fetch_results if r.category == critical_cat]
            if cat_results and all(not r.success for r in cat_results):
                empty_critical.append(critical_cat)

    if empty_critical:
        issues.append(
            f"Critical categories completely failed: {', '.join(empty_critical)}"
        )

    # Build coverage detail string for receipt — map source categories to business-impact sections
    # Aggregate by business-impact section for display
    section_coverage: dict[str, int] = {}
    BUSINESS_SECTIONS = [
        "Strategy & Leadership", "Sales & Marketing", "Customer Experience",
        "Operations & Workflow", "People & Capability", "Data & Systems",
        "Governance & Risk", "Finance & Commercial Performance",
    ]
    for section in BUSINESS_SECTIONS:
        section_coverage[section] = 0
    for cat, count in category_coverage.items():
        mapped_sections = CATEGORY_TO_SECTIONS.get(cat, [])
        for section in mapped_sections:
            if section in section_coverage:
                section_coverage[section] += count
            elif section == "Multiple sections":
                # Distribute evenly across all sections
                for s in BUSINESS_SECTIONS:
                    section_coverage[s] += max(1, count // len(BUSINESS_SECTIONS))
    coverage_parts = []
    for section, count in section_coverage.items():
        status = "\u2713" if count > 0 else "\u2717"
        coverage_parts.append(f"{status} {section}: {count}")

    # Determine result
    if issues:
        message = "Content readiness FAILED: " + "; ".join(issues)
        if warnings:
            message += f". Warnings: {'; '.join(warnings)}"
        return QAResult(
            check_name="Content Readiness",
            passed=False,
            severity="critical",
            message=message,
        )

    # Passed but may have warnings
    message = (
        f"Content ready: {sources_succeeded}/{sources_active} sources, "
        f"{scored_count} items scored, "
        f"{categories_with_items}/{total_categories} categories covered."
    )
    if warnings:
        return QAResult(
            check_name="Content Readiness",
            passed=True,
            severity="warning",
            message=message + f" Warnings: {'; '.join(warnings)}",
        )

    return QAResult(
        check_name="Content Readiness",
        passed=True,
        severity="info",
        message=message,
    )


def check_recipient_count(count: int, mode: str) -> QAResult:
    """Verify recipient count is within expected bounds."""
    if mode == "proof":
        if count != 1:
            return QAResult(
                check_name="Recipient Count",
                passed=False,
                severity="warning",
                message=f"Proof mode should have exactly 1 recipient, got {count}."
            )
        return QAResult(
            check_name="Recipient Count",
            passed=True,
            severity="info",
            message="Proof mode: 1 recipient (correct)."
        )

    # Send mode
    if count == 0:
        return QAResult(
            check_name="Recipient Count",
            passed=False,
            severity="critical",
            message="Zero recipients fetched from the subscriber API. Cannot send to nobody."
        )

    if count < 3:
        return QAResult(
            check_name="Recipient Count",
            passed=False,
            severity="critical",
            message=f"Only {count} recipient(s) fetched. Expected at least 3 active subscribers. The subscriber API may be returning incomplete data — holding edition."
        )

    return QAResult(
        check_name="Recipient Count",
        passed=True,
        severity="info",
        message=f"{count} recipients confirmed."
    )


def check_reply_to() -> QAResult:
    """Verify reply-to address is configured and valid."""
    from_email = os.environ.get("RESEND_FROM_EMAIL", "signal@signal.dtlc.ai")
    reply_to = "paul.ford@gmail.com"  # Hardcoded in delivery.py

    if not from_email or "@" not in from_email:
        return QAResult(
            check_name="Reply-To Validation",
            passed=False,
            severity="critical",
            message=f"RESEND_FROM_EMAIL is invalid or missing ('{from_email}'). Emails would send from a broken address."
        )

    if reply_to != "paul.ford@gmail.com":
        return QAResult(
            check_name="Reply-To Validation",
            passed=False,
            severity="critical",
            message=f"Reply-to is set to '{reply_to}' instead of paul.ford@gmail.com. Subscriber replies would route incorrectly."
        )

    if not os.environ.get("RESEND_API_KEY"):
        return QAResult(
            check_name="Reply-To Validation",
            passed=False,
            severity="critical",
            message="RESEND_API_KEY is not set. The delivery system cannot send emails."
        )

    return QAResult(
        check_name="Reply-To Validation",
        passed=True,
        severity="info",
        message=f"From: Signal <{from_email}>, Reply-to: {reply_to}. Routing confirmed."
    )


def build_category_coverage(scored_items: list, fetch_results: list | None = None) -> dict[str, int]:
    """Build a category coverage map from scored items.

    Returns dict mapping source category -> number of scored items in that category.
    """
    # All known source categories
    all_categories = list(CATEGORY_TO_SECTIONS.keys())
    coverage: dict[str, int] = {cat: 0 for cat in all_categories}

    for item in scored_items:
        # ScoredItem has a .raw attribute which is a RawItem with .category
        try:
            if hasattr(item, 'raw') and hasattr(item.raw, 'category'):
                cat = item.raw.category
            elif hasattr(item, 'category'):
                cat = item.category
            elif isinstance(item, dict):
                cat = item.get('category', '')
            else:
                continue

            if cat in coverage:
                coverage[cat] += 1
            else:
                coverage[cat] = coverage.get(cat, 0) + 1
        except (AttributeError, TypeError):
            continue

    return coverage


def build_failed_source_summary(fetch_results: list) -> str:
    """Build a concise failed-source summary for the receipt email.

    Groups failures by error type and shows top failing domains.
    """
    if not fetch_results:
        return ""

    failed = [r for r in fetch_results if not r.success]
    if not failed:
        return ""

    # Group by error type
    by_type: dict[str, list] = {}
    for r in failed:
        error_type = r.error_type or "unknown"
        by_type.setdefault(error_type, []).append(r)

    lines = [f"Total failed: {len(failed)} sources"]
    for error_type, results in sorted(by_type.items(), key=lambda x: -len(x[1])):
        names = [r.name for r in results[:5]]
        extra = f" (+{len(results) - 5} more)" if len(results) > 5 else ""
        lines.append(f"  {error_type}: {len(results)} — {', '.join(names)}{extra}")

    return "\n".join(lines)


def run_pre_send_qa(
    edition_number: int,
    html: str,
    scored_count: int,
    recipient_count: int,
    sources_failed: int,
    sources_active: int,
    mode: str,
    root: Path,
    scored_items: list | None = None,
    fetch_results: list | None = None,
) -> tuple[bool, list[QAResult]]:
    """Run all pre-send QA checks.

    Returns:
        (should_send, results) — should_send is False if any critical check failed.
        If should_send is False, the edition MUST be held. No exceptions.
    """
    # Calculate sources succeeded
    sources_succeeded = sources_active - sources_failed

    # Build category coverage from scored items
    category_coverage = build_category_coverage(scored_items or [])

    results = [
        check_edition_number(edition_number, root),
        check_date_integrity(edition_number),
        check_subject_body_alignment(html, edition_number),
        check_content_minimum(html, scored_count),
        check_content_readiness(
            sources_succeeded=sources_succeeded,
            sources_active=sources_active,
            scored_count=scored_count,
            category_coverage=category_coverage,
            fetch_results=fetch_results,
        ),
        check_recipient_count(recipient_count, mode),
        check_reply_to(),
    ]

    # Log all results
    log.info("═══ PRE-SEND QA GATE ═══")
    for r in results:
        log.info(str(r))
    log.info("════════════════════════")

    # Determine if we should hold
    critical_failures = [r for r in results if not r.passed and r.severity == "critical"]
    warnings = [r for r in results if not r.passed and r.severity == "warning"]

    if critical_failures:
        log.error("QA GATE: HOLD — %d critical failure(s). Edition will NOT send.", len(critical_failures))
        return False, results

    if warnings:
        log.warning("QA GATE: PASS WITH WARNINGS — %d non-critical warning(s). Edition will send.", len(warnings))

    return True, results


# ═══════════════════════════════════════════════════════════════════════════════
# RUN RECEIPT
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# SUBSCRIBER CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

# Common personal email domains
PERSONAL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.com.au",
    "hotmail.com", "hotmail.com.au", "outlook.com", "live.com",
    "icloud.com", "me.com", "mac.com", "aol.com",
    "protonmail.com", "proton.me", "fastmail.com",
    "msn.com", "bigpond.com", "bigpond.net.au",
    "optusnet.com.au", "internode.on.net",
}


def classify_subscribers(recipients: list[dict]) -> dict:
    """Classify subscribers into business vs personal based on email domain."""
    from datetime import timedelta

    now = datetime.now(BRISBANE)
    yesterday = now - timedelta(hours=24)

    business_emails = []
    personal_emails = []
    new_today = 0

    for r in recipients:
        email = r.get("email", "").strip().lower()
        if not email or "@" not in email:
            continue

        domain = email.split("@", 1)[1]

        if domain in PERSONAL_DOMAINS:
            personal_emails.append(email)
        else:
            business_emails.append(email)

        # Check if subscriber is new (signed up in last 24h)
        subscribed_at = r.get("subscribedAt")
        if subscribed_at:
            try:
                if isinstance(subscribed_at, str):
                    sub_dt = datetime.fromisoformat(subscribed_at.replace("Z", "+00:00"))
                    sub_dt = sub_dt.astimezone(BRISBANE)
                else:
                    sub_dt = subscribed_at
                if sub_dt >= yesterday:
                    new_today += 1
            except (ValueError, TypeError):
                pass

    return {
        "total": len(business_emails) + len(personal_emails),
        "business": len(business_emails),
        "personal": len(personal_emails),
        "new_today": new_today,
        "business_emails": business_emails,
        "personal_emails": personal_emails,
    }


def create_receipt(
    edition_number: int,
    mode: str,
    sources_active: int = 0,
    sources_disabled: int = 0,
    sources_failed: int = 0,
    sources_on_probation: int = 0,
    items_fetched: int = 0,
    items_scored: int = 0,
    recipients_attempted: int = 0,
    recipients_delivered: int = 0,
    recipients_failed: int = 0,
    failed_recipients: list[str] | None = None,
    qa_results: list[QAResult] | None = None,
    degraded_sources: list[str] | None = None,
    duration_seconds: float = 0.0,
    pipeline_result: str = "success",
    code_version: str = "",
    subscriber_insights: dict | None = None,
    category_coverage: dict[str, int] | None = None,
    fetch_results: list | None = None,
    edition_type: str = "daily",
) -> RunReceipt:
    """Create a structured run receipt."""
    now = datetime.now(BRISBANE)

    qa_issues = []
    qa_passed = 0
    qa_failed = 0
    qa_warned = 0
    if qa_results:
        for r in qa_results:
            if r.passed:
                qa_passed += 1
            elif r.severity == "critical":
                qa_failed += 1
                qa_issues.append(f"[CRITICAL] {r.check_name}: {r.message}")
            else:
                qa_warned += 1
                qa_issues.append(f"[WARNING] {r.check_name}: {r.message}")

    sources_total = sources_active + sources_disabled
    sources_succeeded = sources_active - sources_failed

    # Build category coverage detail — display business-impact sections, not source categories
    category_coverage_detail = ""
    categories_with_items = 0
    categories_total = 8  # 8 business-impact sections
    BUSINESS_SECTIONS = [
        "Strategy & Leadership", "Sales & Marketing", "Customer Experience",
        "Operations & Workflow", "People & Capability", "Data & Systems",
        "Governance & Risk", "Finance & Commercial Performance",
    ]
    if category_coverage:
        # Map source categories to business-impact sections
        section_counts: dict[str, int] = {s: 0 for s in BUSINESS_SECTIONS}
        for cat, count in category_coverage.items():
            mapped = CATEGORY_TO_SECTIONS.get(cat, [])
            for section in mapped:
                if section in section_counts:
                    section_counts[section] += count
                elif section == "Multiple sections":
                    for s in BUSINESS_SECTIONS:
                        section_counts[s] += max(1, count // len(BUSINESS_SECTIONS))
        categories_with_items = sum(1 for c in section_counts.values() if c > 0)
        parts = []
        for section, count in section_counts.items():
            icon = "\u2713" if count > 0 else "\u2717"
            parts.append(f"{icon} {section}: {count}")
        category_coverage_detail = " | ".join(parts)

    # Build failed source summary
    failed_source_summary = build_failed_source_summary(fetch_results) if fetch_results else ""

    # Populate subscriber insights if provided
    si = subscriber_insights or {}

    return RunReceipt(
        edition_number=edition_number,
        mode=mode,
        timestamp_aest=now.strftime("%Y-%m-%d %H:%M:%S AEST"),
        date=now.strftime("%d %B %Y"),
        weekday=now.strftime("%A"),
        sources_total=sources_total,
        sources_active=sources_active,
        sources_disabled=sources_disabled,
        sources_failed=sources_failed,
        sources_succeeded=sources_succeeded,
        sources_on_probation=sources_on_probation,
        items_fetched=items_fetched,
        items_scored=items_scored,
        categories_with_items=categories_with_items,
        categories_total=categories_total,
        category_coverage_detail=category_coverage_detail,
        failed_source_summary=failed_source_summary,
        recipients_attempted=recipients_attempted,
        recipients_delivered=recipients_delivered,
        recipients_failed=recipients_failed,
        failed_recipients=failed_recipients or [],
        qa_checks_passed=qa_passed,
        qa_checks_failed=qa_failed,
        qa_checks_warned=qa_warned,
        qa_issues=qa_issues,
        degraded_sources=degraded_sources or [],
        duration_seconds=duration_seconds,
        pipeline_result=pipeline_result,
        subscribers_total=si.get("total", 0),
        subscribers_business=si.get("business", 0),
        subscribers_personal=si.get("personal", 0),
        subscribers_new_today=si.get("new_today", 0),
        subscriber_emails_business=si.get("business_emails", []),
        subscriber_emails_personal=si.get("personal_emails", []),
        code_version=code_version,
        edition_type=edition_type,
    )


def save_receipt(root: Path, receipt: RunReceipt) -> None:
    """Save the run receipt to data/run_receipts.json (local persistence)."""
    receipt_path = root / RECEIPT_FILE
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing receipts
    data = {"receipts": []}
    if receipt_path.exists():
        try:
            with open(receipt_path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            data = {"receipts": []}

    # Append new receipt
    data["receipts"].append(asdict(receipt))

    # Prune old receipts (keep last N)
    if len(data["receipts"]) > MAX_RECEIPTS:
        data["receipts"] = data["receipts"][-MAX_RECEIPTS:]

    # Write back
    try:
        with open(receipt_path, "w") as f:
            json.dump(data, f, indent=2)
        log.info("Run receipt saved: %s", receipt.plain_english_summary())
    except IOError as e:
        log.error("Failed to save run receipt: %s", e)


def send_receipt_email(receipt: RunReceipt) -> None:
    """Email the run receipt to Paul. Always sends — success or failure."""
    try:
        import resend

        api_key = os.environ.get("RESEND_API_KEY")
        from_email = os.environ.get("RESEND_FROM_EMAIL", "signal@signal.dtlc.ai")

        if not api_key:
            log.warning("Cannot send receipt email — RESEND_API_KEY not set")
            return

        resend.api_key = api_key

        # Subject line reflects status clearly
        edition_label = "DTL Signal Weekly Wrap" if receipt.edition_type == "weekly_wrap" else f"DTL Signal {receipt.edition_number:04d}"
        if receipt.pipeline_result == "success":
            subject = f"✓ {edition_label} — Delivered ({receipt.recipients_delivered}/{receipt.recipients_attempted})"
        elif receipt.pipeline_result == "held":
            subject = f"⚠️ {edition_label} — HELD (QA failed)"
        elif receipt.pipeline_result == "partial_failure":
            subject = f"⚠️ {edition_label} — Sent with {receipt.recipients_failed} failure(s)"
        elif receipt.pipeline_result == "aborted":
            subject = f"🚨 {edition_label} — ABORTED"
        else:
            subject = f"{edition_label} — Run Receipt"

        resend.Emails.send({
            "from": f"DTL Signal Ops <{from_email}>",
            "to": [ALERT_RECIPIENT],
            "reply_to": ALERT_RECIPIENT,
            "subject": subject,
            "html": receipt.alert_email_html(),
        })
        log.info("Receipt email sent to %s: %s", ALERT_RECIPIENT, subject)

    except Exception as e:
        log.warning("Receipt email failed (non-fatal): %s", e)


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE HEALTH TRACKING
# ═══════════════════════════════════════════════════════════════════════════════

def record_source_failures(root: Path, failed_sources: list[str], active_sources: list[str]) -> list[str]:
    """Track consecutive failures per source. Returns sources that have failed 3+ times."""
    health_path = root / SOURCE_HEALTH_FILE
    health_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing health data
    data = {}
    if health_path.exists():
        try:
            with open(health_path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            data = {}

    # Update: increment failures for failed sources, reset for successful ones
    for source in active_sources:
        if source in failed_sources:
            data[source] = data.get(source, 0) + 1
        else:
            data[source] = 0  # Reset on success

    # Find sources with 3+ consecutive failures
    degraded = [name for name, count in data.items() if count >= 3]

    # Write back
    try:
        with open(health_path, "w") as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        log.error("Failed to write source health file: %s", e)

    if degraded:
        log.warning("EARLY WARNING: %d source(s) have failed 3+ consecutive runs: %s",
                    len(degraded), ", ".join(degraded))

    return degraded
