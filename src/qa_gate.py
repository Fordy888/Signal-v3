"""Pre-send QA gate and structured run receipt for Signal pipeline.

This module provides:
1. Pre-send validation (metadata integrity, content checks)
2. Structured run receipts (logged + emailed to Paul)
3. Source health tracking (consecutive failure counting)
4. Plain-English alerts that answer: what failed, was it held or sent,
   what's the impact, what action is required, is tomorrow safe.

All checks are non-destructive: they return pass/fail with reasons.
The caller (main.py) decides whether to hold or proceed.
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
    sources_on_probation: int = 0
    items_fetched: int = 0
    items_scored: int = 0

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

    def plain_english_summary(self) -> str:
        """Plain-English summary for Paul. One glance tells you if everything is OK."""
        edition = f"Edition {self.edition_number:04d}"

        if self.pipeline_result == "success":
            summary = (
                f"{edition}: QA passed. "
                f"Delivered to {self.recipients_delivered}/{self.recipients_attempted} active subscribers. "
                f"Sources fetched: {self.sources_active}. "
                f"Failed sources: {self.sources_failed}. "
                f"Disabled sources skipped: {self.sources_disabled}. "
                f"Delivery failures: {self.recipients_failed}. "
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
                f"Sources fetched: {self.sources_active}. "
                f"Failed sources: {self.sources_failed}. "
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
                f"3+ days in a row ({', '.join(self.degraded_sources)}) — consider disabling or replacing."
            )

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
            for src in self.degraded_sources:
                degraded_html += f"<li>{src}</li>"
            degraded_html += "</ul><p style='margin:8px 0 0;font-size:13px;color:#666;'>These should be reviewed — they may need to be disabled or replaced.</p></div>"

        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:600px;margin:0 auto;padding:24px;color:#1f2937;">
    <div style="border-bottom:2px solid {status_color};padding-bottom:12px;margin-bottom:20px;">
        <h2 style="margin:0;font-size:18px;">Signal Run Receipt — Edition {self.edition_number:04d}</h2>
        <p style="margin:4px 0 0;font-size:13px;color:#666;">{now_str}</p>
    </div>

    <div style="padding:16px;background:{status_color}12;border-left:4px solid {status_color};border-radius:4px;margin-bottom:20px;">
        <strong style="color:{status_color};font-size:16px;">{status_label}</strong>
    </div>

    <table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:16px;">
        <tr><td style="padding:6px 0;color:#666;width:180px;">Subscribers</td><td style="padding:6px 0;">{self.recipients_delivered}/{self.recipients_attempted} delivered</td></tr>
        <tr><td style="padding:6px 0;color:#666;">Sources active</td><td style="padding:6px 0;">{self.sources_active}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">Sources failed</td><td style="padding:6px 0;">{self.sources_failed}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">Sources disabled (skipped)</td><td style="padding:6px 0;">{self.sources_disabled}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">Items scored</td><td style="padding:6px 0;">{self.items_scored}</td></tr>
        <tr><td style="padding:6px 0;color:#666;">Duration</td><td style="padding:6px 0;">{self.duration_seconds:.0f} seconds</td></tr>
    </table>

    {issues_html}
    {failed_html}
    {degraded_html}

    <div style="margin-top:20px;padding-top:16px;border-top:1px solid #e5e7eb;">
        <p style="margin:0 0 8px;"><strong>Action required:</strong> {action_text}</p>
        <p style="margin:0;"><strong>Tomorrow's edition:</strong> {tomorrow_text}</p>
    </div>

    <p style="margin-top:24px;font-size:12px;color:#9ca3af;">
        This is an automated operational receipt from the Signal pipeline.
    </p>
</body></html>"""

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
                return "The edition failed to generate properly. Check ANTHROPIC_API_KEY and synthesis logs on Render."
            if "source" in issue.lower():
                return "Too many sources failed. This may be a network issue on Render's side, or multiple feeds have gone offline."

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
            if "source" in issue.lower() and "50%" in issue.lower():
                return "If this is a network issue, it may resolve on its own. If sources are permanently broken, they need replacing."

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
            severity="warning",
            message=f"Running before 03:00 AEST ({now.strftime('%H:%M')}). Date may roll over during execution."
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
            severity="warning",
            message="; ".join(issues)
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


def check_source_health(sources_failed: int, sources_active: int) -> QAResult:
    """Check if too many sources failed this run."""
    if sources_active == 0:
        return QAResult(
            check_name="Source Health",
            passed=False,
            severity="critical",
            message="Zero active sources. The pipeline has nothing to work with."
        )

    failure_rate = sources_failed / sources_active if sources_active > 0 else 1.0

    if failure_rate > 0.5:
        return QAResult(
            check_name="Source Health",
            passed=False,
            severity="critical",
            message=f"{sources_failed} out of {sources_active} sources failed ({failure_rate:.0%}). This suggests a network issue or multiple broken feeds."
        )

    if failure_rate > 0.25:
        return QAResult(
            check_name="Source Health",
            passed=True,
            severity="warning",
            message=f"{sources_failed} out of {sources_active} sources failed ({failure_rate:.0%}). Above normal but edition is still viable."
        )

    return QAResult(
        check_name="Source Health",
        passed=True,
        severity="info",
        message=f"{sources_failed}/{sources_active} sources failed ({failure_rate:.0%}). Within normal range."
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
            passed=True,
            severity="warning",
            message=f"Only {count} recipients. Unusually low — the subscriber API may be returning incomplete data."
        )

    return QAResult(
        check_name="Recipient Count",
        passed=True,
        severity="info",
        message=f"{count} recipients confirmed."
    )


def run_pre_send_qa(
    edition_number: int,
    html: str,
    scored_count: int,
    recipient_count: int,
    sources_failed: int,
    sources_active: int,
    mode: str,
    root: Path,
) -> tuple[bool, list[QAResult]]:
    """Run all pre-send QA checks.

    Returns:
        (should_send, results) — should_send is False if any critical check failed.
        If should_send is False, the edition MUST be held. No exceptions.
    """
    results = [
        check_edition_number(edition_number, root),
        check_date_integrity(edition_number),
        check_subject_body_alignment(html, edition_number),
        check_content_minimum(html, scored_count),
        check_source_health(sources_failed, sources_active),
        check_recipient_count(recipient_count, mode),
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
        sources_on_probation=sources_on_probation,
        items_fetched=items_fetched,
        items_scored=items_scored,
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
    """Email the run receipt to Paul. Always sends — success or failure.

    Uses Resend API. Non-fatal if email fails (receipt is still saved locally).
    """
    try:
        import resend

        api_key = os.environ.get("RESEND_API_KEY")
        from_email = os.environ.get("RESEND_FROM_EMAIL", "signal@signal.dtlc.ai")

        if not api_key:
            log.warning("Cannot send receipt email — RESEND_API_KEY not set")
            return

        resend.api_key = api_key

        # Subject line reflects status clearly
        if receipt.pipeline_result == "success":
            subject = f"✓ Signal {receipt.edition_number:04d} — Delivered ({receipt.recipients_delivered}/{receipt.recipients_attempted})"
        elif receipt.pipeline_result == "held":
            subject = f"⚠️ Signal {receipt.edition_number:04d} — HELD (QA failed)"
        elif receipt.pipeline_result == "partial_failure":
            subject = f"⚠️ Signal {receipt.edition_number:04d} — Sent with {receipt.recipients_failed} failure(s)"
        elif receipt.pipeline_result == "aborted":
            subject = f"🚨 Signal {receipt.edition_number:04d} — ABORTED"
        else:
            subject = f"Signal {receipt.edition_number:04d} — Run Receipt"

        resend.Emails.send({
            "from": f"Signal Ops <{from_email}>",
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
    """Track consecutive failures per source. Returns sources that have failed 3+ times.

    This enables early warning: if a source fails 3 runs in a row, it should be
    flagged for investigation (and potentially moved to probation/disabled).
    """
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
