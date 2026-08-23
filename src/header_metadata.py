"""Deterministic DTL Signal header metadata enforcement."""

from __future__ import annotations

import re


def ensure_header_metadata(
    html: str,
    day_name: str,
    date_formatted: str,
    time_str: str,
) -> tuple[str, str]:
    """Guarantee that pipeline-computed Brisbane metadata appears in the header.

    Returns ``(html, action)`` where action is ``unchanged``, ``replaced`` or
    ``injected``.
    """
    correct_line = f"{day_name} {date_formatted} | {time_str} AEST"
    header_limit = min(len(html), 6000)
    header = html[:header_limit]

    if correct_line in header:
        return html, "unchanged"

    weekdays = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
    date_line_pattern = re.compile(
        rf"(?:{weekdays})\s+\d{{1,2}}\s+[A-Za-z]+\s+\d{{4}}\s*\|\s*\d{{1,2}}:\d{{2}}\s*AEST",
        re.IGNORECASE,
    )
    match = date_line_pattern.search(header)
    if match:
        html = html[:match.start()] + correct_line + html[match.end():]
        return html, "replaced"

    subtitle_pos = header.find("Executive Business Intelligence")
    if subtitle_pos >= 0:
        row_end = html.find("</tr>", subtitle_pos)
        if row_end >= 0:
            row_end += len("</tr>")
            date_row = (
                '<tr><td style="padding: 4px 40px 24px 40px;">'
                '<p style="margin: 0; font-size: 11px; font-family: '
                "'SF Mono', 'Fira Code', 'Courier New', monospace; "
                'color: #bbb;">'
                f"{correct_line}</p></td></tr>"
            )
            html = html[:row_end] + date_row + html[row_end:]
            return html, "injected"

    date_row = (
        '<tr><td style="padding: 4px 40px 24px 40px;">'
        f'<p style="margin: 0; font-size: 11px; color: #bbb;">{correct_line}</p>'
        '</td></tr>'
    )
    first_row_end = html.find("</tr>")
    insert_at = first_row_end + len("</tr>") if first_row_end >= 0 else 0
    html = html[:insert_at] + date_row + html[insert_at:]
    return html, "injected"
