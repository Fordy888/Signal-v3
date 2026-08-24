"""Deterministic HTML renderer for the Development Thesis V1 comparison."""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

from .human_signal import render_human_signal
from .alive_moment import render_alive_moment
from .visual_signal import render_visual_signal


ACTION_COLOURS = {"ACT": "#E8533A", "WATCH": "#E6A817", "NOTE": "#888888"}
MOVEMENT_COLOURS = {
    "STRENGTHENS": "#17A398",
    "CONFIRMS": "#4ECDC4",
    "WEAKENS": "#E6A817",
    "CHALLENGES": "#E8533A",
    "DOES_NOT_MATERIALLY_CHANGE": "#888888",
}


def _p(text: str, *, size: int = 15, colour: str = "#444", margin: str = "0") -> str:
    return f'<p style="margin:{margin};font-size:{size}px;line-height:1.65;color:{colour};">{text}</p>'


def _divider() -> str:
    return '<tr><td style="padding:0 40px;"><div style="border-top:1px solid #e8e8e8;"></div></td></tr>'


def render_enhanced_email(
    plan: dict[str, Any],
    sources: list[dict[str, Any]],
    joke: dict[str, str],
    edition_number: int,
    generated_at: datetime,
    alive_moment: dict[str, Any] | None = None,
) -> str:
    source_map = {str(item["source_id"]): item for item in sources}
    edition_padded = f"{edition_number:04d}"
    date_long = generated_at.strftime("%A %d %B %Y")
    date_compact = generated_at.strftime("%d.%m.%Y")
    time_text = generated_at.strftime("%H:%M")
    one = plan["one_thing"]

    html = [
        '<table width="100%" cellpadding="0" cellspacing="0" style="max-width:900px;margin:0 auto;background:#fff;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,Arial,sans-serif;">',
        '<tr><td style="height:4px;background:linear-gradient(90deg,#E8533A 0%,#E8533A 50%,#4ECDC4 50%,#4ECDC4 100%);"></td></tr>',
        '<tr><td style="padding:32px 40px 0 40px;"><table width="100%"><tr>',
        '<td><p style="margin:0;font:800 24px monospace;letter-spacing:3px;color:#1a1a1a;">DTL SIGNAL</p></td>',
        f'<td align="right"><p style="margin:0;font:11px monospace;color:#999;letter-spacing:1px;">Edition {edition_padded}</p></td>',
        '</tr></table></td></tr>',
        '<tr><td style="padding:4px 40px 0 40px;"><p style="margin:0;font-size:12px;color:#999;letter-spacing:1.5px;text-transform:uppercase;">Executive Business Intelligence</p></td></tr>',
        f'<tr><td style="padding:4px 40px 24px 40px;"><p style="margin:0;font:11px monospace;color:#bbb;">{escape(date_long)} | {time_text} AEST</p></td></tr>',
        '<tr><td style="padding:0 40px;"><div style="border-top:2px solid #4ECDC4;"></div></td></tr>',
        '<tr><td style="padding:18px 40px 0 40px;"><p style="margin:0;font:800 9px monospace;color:#aaa;letter-spacing:2px;text-transform:uppercase;">THINK</p></td></tr>',
        '<tr><td style="padding:22px 40px 8px 40px;"><p style="margin:0;font:800 11px monospace;color:#E8533A;letter-spacing:1.7px;">THE ONE THING</p></td></tr>',
        f'<tr><td style="padding:0 40px 8px 40px;"><p style="margin:0;font-size:24px;font-weight:800;line-height:1.35;color:#1a1a1a;">{escape(str(one["statement"]))}</p></td></tr>',
        f'<tr><td style="padding:4px 40px 22px 40px;">{_p(escape(str(one["business_implication"])), size=15, colour="#555")}</td></tr>',
        _divider(),
        '<tr><td style="padding:20px 40px 6px 40px;"><p style="margin:0;font:800 12px monospace;color:#17A398;letter-spacing:1.7px;">THE EVIDENCE</p></td></tr>',
    ]

    for item in plan["evidence_items"]:
        sources_for_item = [source_map[source_id] for source_id in item["source_ids"] if source_id in source_map]
        source_links = ", ".join(
            f'<a href="{escape(str(source["url"]), quote=True)}" style="color:#17A398;text-decoration:none;font-weight:650;">{escape(str(source["source"]))}</a>'
            for source in sources_for_item
        )
        colour = ACTION_COLOURS[item["action_tag"]]
        html.extend(
            [
                '<tr><td style="padding:16px 40px 10px 40px;">',
                f'<p style="margin:0 0 7px 0;"><span style="display:inline-block;background:{colour};color:#fff;font:800 9px monospace;letter-spacing:1.3px;padding:3px 8px;border-radius:2px;">{escape(item["action_tag"])}</span> <span style="font:800 10px monospace;color:#17A398;letter-spacing:1px;text-transform:uppercase;">{escape(item["category"])}</span></p>',
                f'<p style="margin:0 0 11px 0;font-size:18px;font-weight:800;line-height:1.35;color:#1a1a1a;">{escape(item["headline"])}</p>',
                _p(f'{escape(item["evidence"])} <span style="white-space:nowrap;">({source_links})</span>'),
                '</td></tr>',
                _divider(),
            ]
        )

    changed = plan["what_changed"]
    movement = changed["classification"]
    movement_colour = MOVEMENT_COLOURS[movement]
    html.extend(
        [
            render_visual_signal(plan["visual_signal"]),
            '<tr><td style="padding:24px 40px 0 40px;"><p style="margin:0;font:800 9px monospace;color:#aaa;letter-spacing:2px;text-transform:uppercase;">DECIDE</p></td></tr>',
            '<tr><td style="padding:18px 40px 6px 40px;"><p style="margin:0;font:800 11px monospace;color:#17A398;letter-spacing:1.5px;">EXECUTIVE READ</p></td></tr>',
            '<tr><td style="padding:0 40px 4px 40px;"><p style="margin:0 0 5px 0;font:800 10px monospace;color:#999;letter-spacing:1px;">INTERPRETATION</p></td></tr>',
            f'<tr><td style="padding:0 40px 14px 40px;">{_p(escape(plan["interpretation"]), colour="#444")}</td></tr>',
            '<tr><td style="padding:0 40px 4px 40px;"><p style="margin:0 0 5px 0;font:800 10px monospace;color:#E8533A;letter-spacing:1px;">CEO VIEW</p></td></tr>',
            f'<tr><td style="padding:0 40px 14px 40px;">{_p(escape(plan["dtl_view"]), colour="#1a1a1a")}</td></tr>',
            '<tr><td style="padding:18px 40px 8px 40px;">',
            '<table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fffe;border:2px solid #4ECDC4;border-radius:4px;">',
            '<tr><td style="padding:20px 22px;">',
            '<p style="margin:0 0 8px 0;font:800 11px monospace;color:#E8533A;letter-spacing:1.5px;">WHAT CHANGED?</p>',
            f'<p style="margin:0 0 10px 0;"><span style="display:inline-block;background:{movement_colour};color:#fff;font:800 10px monospace;letter-spacing:1px;padding:4px 9px;border-radius:2px;">{escape(movement.replace("_", " "))}</span></p>',
            _p(escape(changed["explanation"]), colour="#333"),
            '</td></tr></table></td></tr>',
            '<tr><td style="padding:22px 40px 8px 40px;"><p style="margin:0;font:800 11px monospace;color:#E8533A;letter-spacing:1.5px;">EXECUTIVE ACTION / WATCH</p></td></tr>',
            '<tr><td style="padding:0 40px 14px 40px;"><table width="100%">',
        ]
    )

    for index, action in enumerate(plan["executive_actions"], 1):
        html.append(f'<tr><td style="padding:6px 0;">{_p(f"<strong style=\"color:#E8533A;\">{index}.</strong> {escape(action)}", size=14, colour="#333")}</td></tr>')
    html.append('</table></td></tr>')

    counter = plan["counter_signal"]
    html.extend(
        [
            '<tr><td style="padding:24px 40px 0 40px;"><p style="margin:0;font:800 9px monospace;color:#aaa;letter-spacing:2px;text-transform:uppercase;">LOOK UP</p></td></tr>',
            '<tr><td style="padding:24px 40px 8px 40px;">',
            '<table width="100%" cellpadding="0" cellspacing="0" style="background:#fffaf1;border-left:4px solid #E6A817;">',
            '<tr><td style="padding:18px 20px;">',
            '<p style="margin:0 0 8px 0;font:800 11px monospace;color:#9b6c00;letter-spacing:1.5px;">COUNTER-SIGNAL</p>',
            _p(escape(counter["statement"]), colour="#333", margin="0 0 8px 0"),
            _p(f'<strong>What would change our view:</strong> {escape(counter["would_change_view_if"])}', size=13, colour="#666"),
            '</td></tr></table></td></tr>',
            '<tr><td style="padding:18px 40px 5px 40px;"><p style="margin:0;font:800 10px monospace;color:#E6A817;letter-spacing:1px;text-transform:uppercase;">What to Watch</p></td></tr>',
        ]
    )
    for watch in plan["executive_read"]["watch_items"]:
        html.append(f'<tr><td style="padding:3px 40px;">{_p("• " + escape(watch), size=13, colour="#555")}</td></tr>')
    if alive_moment:
        html.append(render_alive_moment(alive_moment))
    html.extend(
        [
            '<tr><td style="padding:24px 40px 0 40px;"><p style="margin:0;font:800 9px monospace;color:#aaa;letter-spacing:2px;text-transform:uppercase;">SMILE</p></td></tr>',
            render_human_signal(joke),
            '<tr><td style="padding:24px 40px 8px 40px;"><p style="margin:0;font:11px monospace;color:#999;">Signal learns. Every open, every click, every skip trains the next edition.</p></td></tr>',
            '<tr><td style="padding:0 40px 26px 40px;"><table width="100%"><tr>',
            f'<td><p style="margin:0;font:9px monospace;color:#bbb;letter-spacing:1px;">PF::SIGNAL-{edition_padded} // {date_compact} // {time_text} AEST</p></td>',
            '<td align="right"><p style="margin:0;font:9px monospace;color:#bbb;"><a href="https://dtlc.ai" style="color:#4ECDC4;text-decoration:none;">dtlc.ai</a></p></td>',
            '</tr></table></td></tr>',
            '<tr><td style="height:4px;background:linear-gradient(90deg,#4ECDC4 0%,#4ECDC4 50%,#E8533A 50%,#E8533A 100%);"></td></tr>',
            '</table>',
        ]
    )
    return "".join(html)
