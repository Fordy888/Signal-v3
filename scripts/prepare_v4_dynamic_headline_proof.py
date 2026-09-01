"""Prepare the exact dynamic-headline proof for Fordy's Gmail only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "data" / "v4-dynamic-headline-proof.html"
PAYLOAD_PATH = ROOT / "data" / "v4-dynamic-headline-proof-send.json"
EXPECTED_SHA256 = "56226e2f1f955cc137d9b621b07504732390924d25dcc1cada87797e91744f35"


def main() -> int:
    html_bytes = HTML_PATH.read_bytes()
    actual_sha256 = hashlib.sha256(html_bytes).hexdigest()
    if actual_sha256 != EXPECTED_SHA256:
        raise RuntimeError(
            f"Dynamic-headline HTML checksum changed: {actual_sha256}; proof send held"
        )

    html = html_bytes.decode("utf-8")
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    payload = {
        "from": "DTL Signal <signal@signal.dtlc.ai>",
        "to": ["paul.ford@gmail.com"],
        "subject": "[PROOF] DTL Signal v4 | Complete Revision + Remember The World",
        "html": html,
        "text": text,
        "tags": [
            {"name": "message_type", "value": "proof"},
            {"name": "edition", "value": "0044"},
            {"name": "format", "value": "enhanced-v4"},
            {"name": "gate", "value": "dynamic-headlines-image"},
        ],
        "idempotencyKey": f"dtl-signal-complete-proof-{actual_sha256[:16]}",
    }
    if payload["to"] != ["paul.ford@gmail.com"]:
        raise RuntimeError("Proof recipient boundary changed")
    PAYLOAD_PATH.write_text(json.dumps(payload, ensure_ascii=False))
    print(PAYLOAD_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
