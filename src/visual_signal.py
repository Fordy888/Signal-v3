"""Deterministic rendering for optional visual intelligence objects."""
from __future__ import annotations

from html import escape
from typing import Any


STATUS_COLOURS = {
    "STRENGTHENS": "#17A398",
    "CONFIRMS": "#4ECDC4",
    "WEAKENS": "#E6A817",
    "CHALLENGES": "#E8533A",
    "EXPOSED": "#E8533A",
    "CONSTRAINED": "#E6A817",
    "SUPPORTED": "#17A398",
}


def _status_colour(status: str) -> str:
    if status in STATUS_COLOURS:
        return STATUS_COLOURS[status]
    if any(term in status for term in ("EXPOSED", "ENFORCEMENT", "RISK")):
        return "#E8533A"
    if any(term in status for term in ("CONSTRAIN", "BINDING", "HEADWIND", "RISING")):
        return "#E6A817"
    if any(term in status for term in ("SUPPORTED", "STRENGTHEN", "CONFIRM", "COMMODIT")):
        return "#17A398"
    return "#888888"


def render_visual_signal(spec: dict[str, Any], *, dynamic_headlines: bool = False) -> str:
    if not spec.get("eligible") or spec.get("type") == "NONE":
        return ""
    rows = spec.get("rows") or []
    if not 2 <= len(rows) <= 5:
        return ""

    rendered_rows = []
    for row in rows:
        status = str(row.get("status", "")).upper()
        colour = _status_colour(status)
        rendered_rows.append(
            '<tr>'
            f'<td style="padding:9px 10px;border-top:1px solid #e8e8e8;font-size:13px;font-weight:700;color:#1a1a1a;">{escape(str(row.get("label", "")))}</td>'
            f'<td style="padding:9px 10px;border-top:1px solid #e8e8e8;font-size:10px;font-family:monospace;font-weight:800;color:{colour};letter-spacing:.8px;">{escape(status)}</td>'
            f'<td style="padding:9px 10px;border-top:1px solid #e8e8e8;font-size:13px;color:#555;">{escape(str(row.get("detail", "")))}</td>'
            '</tr>'
        )

    utility_label = "THE SHIFT" if dynamic_headlines else "VISUAL SIGNAL"
    return (
        '<tr><td style="padding:24px 40px 8px 40px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #dfe9e7;border-radius:4px;background:#fbfefd;">'
        '<tr><td colspan="3" style="padding:18px 18px 6px 18px;">'
        f'<p style="margin:0 0 4px 0;font-size:11px;font-family:monospace;color:#17A398;letter-spacing:1.5px;font-weight:800;text-transform:uppercase;">{utility_label}</p>'
        f'<p style="margin:0;font-size:17px;font-weight:750;color:#1a1a1a;">{escape(str(spec.get("title", "")))}</p>'
        f'<p style="margin:5px 0 8px 0;font-size:13px;color:#666;">{escape(str(spec.get("subtitle", "")))}</p>'
        '</td></tr>'
        + "".join(rendered_rows)
        + '</table></td></tr>'
    )
