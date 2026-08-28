from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "data" / "edition0042-enhanced-draft.html"
REPORT_PATH = ROOT / "data" / "edition0042-link-check.json"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and values.get("href", "").startswith("https://"):
            self.urls.append(("link", str(values["href"])))
        if tag == "img" and values.get("src", "").startswith("https://"):
            self.urls.append(("image", str(values["src"])))


def main() -> int:
    parser = LinkParser()
    parser.feed(HTML_PATH.read_text())
    unique = list(dict.fromkeys(parser.urls))
    session = requests.Session()
    session.headers.update({"User-Agent": "DTL-Signal-QA/1.0 (+https://dtlc.ai/signal)"})
    results = []
    failures = []
    for kind, url in unique:
        try:
            response = session.get(url, timeout=25, allow_redirects=True, stream=True)
            ok = response.status_code < 400
            result = {
                "kind": kind,
                "url": url,
                "status": response.status_code,
                "final_url": response.url,
                "ok": ok,
            }
            response.close()
        except requests.RequestException as exc:
            result = {
                "kind": kind,
                "url": url,
                "status": None,
                "final_url": None,
                "ok": False,
                "error": type(exc).__name__,
            }
        results.append(result)
        if not result["ok"]:
            failures.append(result)

    REPORT_PATH.write_text(json.dumps({"results": results, "failures": failures}, indent=2) + "\n")
    print(f"Checked {len(results)} unique HTTPS targets; failures={len(failures)}")
    for item in failures:
        print(f"FAIL {item['status']} {item['url']}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
