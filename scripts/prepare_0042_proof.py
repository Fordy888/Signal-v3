"""Prepare—but never send—the exact Edition 0042 proof payload.

The generated JSON is restricted to Fordy's proof inbox and uses an
idempotency key derived from the frozen HTML checksum.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "data" / "edition0042-enhanced-draft.html"
PAYLOAD_PATH = ROOT / "data" / "edition0042-proof-send.json"
EXPECTED_SHA256 = "e043f2c88984ca9250bbde7b34a3e71ae7eab93fd0591b2a59cf7e2290472255"


def main() -> int:
    html_bytes = HTML_PATH.read_bytes()
    actual_sha256 = hashlib.sha256(html_bytes).hexdigest()
    if actual_sha256 != EXPECTED_SHA256:
        raise RuntimeError(
            f"Edition 0042 HTML checksum changed: {actual_sha256}; proof send held"
        )

    html = html_bytes.decode("utf-8")
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    payload = {
        "from": "DTL Signal <signal@signal.dtlc.ai>",
        "to": ["paul.ford@gmail.com"],
        "subject": "[PROOF] DTL Signal | Edition 0042 | Final Format",
        "html": html,
        "text": text,
        "tags": [
            {"name": "message_type", "value": "proof"},
            {"name": "edition", "value": "0042"},
            {"name": "format", "value": "enhanced-v4"},
            {"name": "gate", "value": "final-format"},
        ],
        "idempotencyKey": f"dtl-signal-proof-0042-{actual_sha256[:16]}",
    }
    PAYLOAD_PATH.write_text(json.dumps(payload, ensure_ascii=False))
    print(PAYLOAD_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
