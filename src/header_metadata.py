"""Deterministic DTL Signal header metadata enforcement."""

from __future__ import annotations

import re


def ensure_header_metadata(
    html: str,
    day_name: str,
    date_formatted: str,
    time_str: str,
    edition_number: int | None = None,
    date_compact: str | None = None,
) -> tuple[str, str]:
    """Guarantee that pipeline-computed Brisbane metadata appears in the header.

    Returns ``(html, action)`` where action is ``unchanged``, ``replaced`` or
    ``injected``.
    """
    correct_line = f"{day_name} {date_formatted} | {time_str} AEST"
    header_limit = min(len(html), 6000)
    header = html[:header_limit]

    actions: list[str] = []

    if correct_line in header:
        actions.append("header_unchanged")
    else:
        weekdays = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
        date_line_pattern = re.compile(
            rf"(?:{weekdays})\s+\d{{1,2}}\s+[A-Za-z]+\s+\d{{4}}\s*\|\s*\d{{1,2}}:\d{{2}}\s*AEST",
            re.IGNORECASE,
        )
        match = date_line_pattern.search(header)
        if match:
            html = html[:match.start()] + correct_line + html[match.end():]
            actions.append("header_replaced")
        else:
            subtitle_pos = header.find("Executive Business Intelligence")
            if subtitle_pos >= 0:
                row_end = html.find("</tr>", subtitle_pos)
            else:
                row_end = -1

            date_row = (
                '<tr><td style="padding: 4px 40px 24px 40px;">'
                '<p style="margin: 0; font-size: 11px; font-family: '
                "'SF Mono', 'Fira Code', 'Courier New', monospace; "
                'color: #bbb;">'
                f"{correct_line}</p></td></tr>"
            )
            if row_end >= 0:
                row_end += len("</tr>")
                html = html[:row_end] + date_row + html[row_end:]
            else:
                first_row_end = html.find("</tr>")
                insert_at = first_row_end + len("</tr>") if first_row_end >= 0 else 0
                html = html[:insert_at] + date_row + html[insert_at:]
            actions.append("header_injected")

    if edition_number is not None and date_compact:
        correct_stamp = (
            f"PF::SIGNAL-{edition_number:04d} // {date_compact} // {time_str} AEST"
        )
        stamp_pattern = re.compile(
            r"PF::SIGNAL-\d{3,4}\s*//\s*\d{2}\.\d{2}\.\d{4}"
            r"\s*//\s*\d{1,2}:\d{2}\s*AEST",
            re.IGNORECASE,
        )
        stamp_match = stamp_pattern.search(html)
        if stamp_match:
            existing_stamp = stamp_match.group(0)
            if existing_stamp == correct_stamp:
                actions.append("footer_unchanged")
            else:
                html = html[:stamp_match.start()] + correct_stamp + html[stamp_match.end():]
                actions.append("footer_replaced")
        else:
            stamp_row = (
                '<tr><td style="padding: 0 40px 20px 40px;">'
                '<p style="margin: 0; font-size: 9px; color: #bbb;">'
                f"{correct_stamp}</p></td></tr>"
            )
            final_table_close = html.rfind("</table>")
            insert_at = final_table_close if final_table_close >= 0 else len(html)
            html = html[:insert_at] + stamp_row + html[insert_at:]
            actions.append("footer_injected")

    return html, ",".join(actions)
