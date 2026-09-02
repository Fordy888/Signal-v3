from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "data" / "final-founder-led-proof.html"
MANIFEST_PATH = ROOT / "data" / "final-founder-led-proof-manifest.json"
OUTPUT_PATH = ROOT / "data" / "final-founder-led-proof-send.json"


def main() -> None:
    html = HTML_PATH.read_text()
    manifest = json.loads(MANIFEST_PATH.read_text())
    digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
    if digest != manifest["html_sha256"]:
        raise SystemExit(
            f"Proof checksum mismatch: expected {manifest['html_sha256']}, got {digest}"
        )

    recipient = manifest["proof_recipient"]
    if recipient.lower() != "paul.ford@gmail.com":
        raise SystemExit("Proof recipient boundary failed")
    if manifest.get("subscriber_send") is not False:
        raise SystemExit("Manifest does not declare a no-subscriber proof")

    payload = {
        "from": "DTL Signal <signal@signal.dtlc.ai>",
        "to": [recipient],
        "subject": "[PROOF] DTL Signal | 60% AI-in-Business + 40% Big Business | Edition 0046",
        "html": html,
        "text": (
            "DTL Signal 60/40 proof. Founder’s Note leads; DTL Signal Newsroom presents "
            "three AI-in-business and two major-business stories; Focus on the Numbers "
            "follows with three AI-in-business and two major-business figures. All ten "
            "sources are distinct. Remember the World uses the authentic coral-aligned "
            "Quang Phu Cau photograph; the Daily Dad Joke remains the final content beat."
        ),
        "idempotencyKey": f"dtl-signal-final-founder-led-{digest[:32]}",
        "tags": [
            {"name": "message_type", "value": "signal"},
            {"name": "edition", "value": "0046"},
            {"name": "edition_type", "value": "daily"},
            {"name": "format", "value": "enhanced-v4-focus-numbers"},
            {"name": "delivery_mode", "value": "proof"},
            {"name": "release_id", "value": "focus-numbers-60-40-v1"},
        ],
    }
    if len(payload["to"]) != 1:
        raise SystemExit("Proof payload must have exactly one recipient")
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False) + "\n")
    print(f"Prepared {OUTPUT_PATH}")
    print(f"Recipient count: {len(payload['to'])}")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
