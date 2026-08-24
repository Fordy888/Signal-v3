"""Governed Human Signal selection and rendering.

Jokes are selected from an approved library. The agent never generates a joke.
"""
from __future__ import annotations

import hashlib
import json
from html import escape
from pathlib import Path
from typing import Any


def load_jokes(path: Path) -> list[dict[str, str]]:
    jokes = json.loads(path.read_text())
    if len(jokes) < 100:
        raise ValueError("Governed joke library must contain at least 100 approved jokes")
    required = {"id", "setup", "punchline"}
    for joke in jokes:
        if not required.issubset(joke) or not all(str(joke[key]).strip() for key in required):
            raise ValueError("Every approved joke requires id, setup and punchline")
    return jokes


def load_joke_history(path: Path) -> list[str]:
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [str(item) for item in data.get("recent_joke_ids", [])]


def select_joke(jokes: list[dict[str, str]], edition_number: int, recent_ids: list[str], protect: int = 30) -> dict[str, str]:
    blocked = set(recent_ids[-protect:])
    eligible = [joke for joke in jokes if joke["id"] not in blocked]
    if not eligible:
        eligible = jokes
    digest = hashlib.sha256(f"dtl-signal-{edition_number}".encode()).hexdigest()
    return eligible[int(digest[:12], 16) % len(eligible)]


def record_joke(path: Path, joke_id: str, protect: int = 30) -> None:
    history = load_joke_history(path)
    history.append(joke_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"recent_joke_ids": history[-protect:]}, indent=2) + "\n")


def render_human_signal(joke: dict[str, str]) -> str:
    return (
        '<tr><td style="padding:26px 40px 8px 40px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" style="background:#fafafa;border-left:3px solid #E6A817;">'
        '<tr><td style="padding:16px 18px;">'
        '<p style="margin:0 0 8px 0;font-size:10px;font-family:monospace;font-weight:800;letter-spacing:1.5px;color:#888;text-transform:uppercase;">DAD JOKE OF THE DAY</p>'
        f'<p style="margin:0;font-size:14px;line-height:1.65;color:#333;">{escape(joke["setup"])}<br>{escape(joke["punchline"])}</p>'
        '</td></tr></table></td></tr>'
    )

