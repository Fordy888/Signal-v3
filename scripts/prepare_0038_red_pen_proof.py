"""Prepare the exact Edition 0038 Red-Pen proof for one-recipient delivery.

This utility never sends email. It reads the locked HTML artefact and writes the
single-recipient Resend connector payload used by the proof gate.
"""
from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "data" / "edition0038-enhanced-refined.html"
PAYLOAD_PATH = ROOT / "data" / "edition0038-red-pen-proof-send.json"


def main() -> int:
    html = HTML_PATH.read_text()
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    payload = {
        "from": "DTL Signal <signal@signal.dtlc.ai>",
        "to": ["paul.ford@gmail.com"],
        "replyTo": ["paul.ford@gmail.com"],
        "subject": "[PROOF] DTL Signal | Edition 0038 | Final Locked Format",
        "html": html,
        "text": text,
        "tags": [
            {"name": "message_type", "value": "proof"},
            {"name": "edition", "value": "0038"},
            {"name": "format", "value": "enhanced-v4"},
            {"name": "gate", "value": "red-pen"},
        ],
        "idempotencyKey": "dtl-signal-proof-0038-final-62b1732f",
    }
    PAYLOAD_PATH.write_text(json.dumps(payload, ensure_ascii=False))
    print(PAYLOAD_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
