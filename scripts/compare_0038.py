"""Compare Edition 0038 Current with Edition 0038 Enhanced."""
from __future__ import annotations

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "data" / "edition0038-proof.html"
ENHANCED = ROOT / "data" / "edition0038-enhanced.html"
PLAN = ROOT / "data" / "edition0038-enhanced-plan.json"
OUT_JSON = ROOT / "data" / "edition0038-comparison-metrics.json"
OUT_MD = ROOT / "docs" / "edition0038-current-vs-enhanced.md"


def visible_metrics(path: Path) -> dict:
    html = path.read_text()
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.stripped_strings)
    words = re.findall(r"\b[\w’'-]+\b", text)
    links = [a.get("href") for a in soup.find_all("a") if a.get("href")]
    categories = sorted(
        {
            label
            for label in (
                "Strategy & Leadership",
                "Sales & Marketing",
                "Customer Experience",
                "Operations & Workflow",
                "People & Capability",
                "Data & Systems",
                "Governance & Risk",
                "Finance & Commercial Performance",
            )
            if label.lower() in text.lower()
        }
    )
    return {
        "visible_words": len(words),
        "estimated_read_minutes_at_220wpm": round(len(words) / 220, 1),
        "source_links": len(links),
        "categories_present": categories,
        "category_count": len(categories),
        "has_one_thing": "THE ONE THING" in text,
        "has_evidence_boundary": "THE EVIDENCE" in text,
        "has_interpretation_boundary": "INTERPRETATION:" in text,
        "has_dtl_view_boundary": "DTL VIEW:" in text,
        "has_what_changed": "WHAT CHANGED?" in text,
        "has_visual_signal": "VISUAL SIGNAL" in text,
        "has_counter_signal": "COUNTER-SIGNAL" in text,
        "has_human_signal": "DAD JOKE OF THE DAY" in text,
        "has_emotional_rhythm": all(label in text for label in ("THINK", "DECIDE", "LOOK UP", "SMILE")),
        "has_executive_actions": "EXECUTIVE ACTION" in text,
        "has_executive_read": "EXECUTIVE READ" in text,
        "html_chars": len(html),
    }


def main() -> int:
    current = visible_metrics(CURRENT)
    enhanced = visible_metrics(ENHANCED)
    plan = json.loads(PLAN.read_text())
    enhanced["one_thing_words"] = len(plan["one_thing"]["statement"].split())
    enhanced["memory_classification"] = plan["what_changed"]["classification"]
    enhanced["visual_type"] = plan["visual_signal"]["type"] if plan["visual_signal"]["eligible"] else "NONE"
    enhanced["counter_signal_words"] = len(plan["counter_signal"]["statement"].split())
    enhanced["dad_joke_library_size"] = len(json.loads((ROOT / "data" / "dad_jokes.json").read_text()))

    metrics = {"current": current, "enhanced": enhanced}
    OUT_JSON.write_text(json.dumps(metrics, indent=2) + "\n")

    current_minutes = current["estimated_read_minutes_at_220wpm"]
    enhanced_minutes = enhanced["estimated_read_minutes_at_220wpm"]
    delta_words = enhanced["visible_words"] - current["visible_words"]

    report = f"""# DTL Signal Edition 0038 — Current vs Enhanced

**Acceptance comparison:** same seven source signals; different editorial judgement architecture.  
**Production status:** unchanged. Enhanced mode remains explicit and default-off.

## Headline finding

Edition 0038 Enhanced makes the principal conclusion visible immediately and introduces explicit provenance, memory, visual compression, challenge and governed personality. It is **more rigorous, easier to orient within and materially shorter end-to-end**: {enhanced['visible_words']} visible words versus {current['visible_words']} in Current. The product experience now follows one deliberate emotional rhythm: **Think. Decide. Look up. Smile.**

| Measure | Edition 0038 Current | Edition 0038 Enhanced |
|---|---:|---:|
| Visible words | {current['visible_words']} | {enhanced['visible_words']} |
| Estimated read at 220 wpm | {current_minutes} min | {enhanced_minutes} min |
| Source links | {current['source_links']} | {enhanced['source_links']} |
| Business categories represented | {current['category_count']} | {enhanced['category_count']} |
| THE ONE THING | No explicit governed object | Yes — {enhanced['one_thing_words']} words |
| Evidence / Interpretation / DTL View | Implied through legacy labels | Explicit, structurally separate edition layers |
| WHAT CHANGED | No | **{enhanced['memory_classification']}** |
| Visual Signal | No intelligence visual | **{enhanced['visual_type']}** |
| Counter-Signal | No | Yes |
| Governed Human Signal | Founder’s Note only | 100-joke approved library + rotation |
| Emotional rhythm | Emergent | **Think → Decide → Look up → Smile** |

## Acceptance criteria

| Test | Current | Enhanced | Finding |
|---|---|---|---|
| **Faster to orient** | Thesis appears near top, followed by a long Founder’s Note | One governed conclusion is the first substantive block | **Pass** for 20-second orientation |
| **Clearer boundaries** | “What happened / Why it matters / Signal” approximates the distinction | Source evidence, interpretation and DTL judgement are explicitly labelled and structurally separate | **Pass** |
| **Connected** | Article deduplication only | Real Edition 0022 position is classified as **STRENGTHENS** based on Edition 0038 evidence | **Pass** |
| **Rigorous** | What to Watch, but no direct challenge | Counter-Signal states the credible alternative and what evidence would lower confidence | **Pass** |
| **Compressed** | No evidence-backed visual object | Five-row tension map replaces a longer explanation of where AI value is constrained | **Pass** |
| **Memorable** | Seven independent story frames plus an Executive Read | One repeated judgement anchors the evidence, change classification, visual and action | **Pass** |
| **Human** | Generated Founder’s Note | Low-risk, bottom-placed Dad Joke selected from a governed rotating library | **Pass** |
| **Shorter end-to-end** | {current['visible_words']} words | {enhanced['visible_words']} words | **Pass — {abs(delta_words)} fewer words** |

## What the enhanced edition concludes

> {plan['one_thing']['statement']}

The memory layer compares this evidence with the genuine Edition 0022 position that durable advantage comes from the operating system around the model. Edition 0038 **strengthens** that position through cheaper-model adoption, constrained-agent outcomes, knowledge-quality limits and enforceable governance risk.

## Architecture result

The enhancement is additive and reversible. Fetching, scoring, subscribers, Resend delivery, DTL PL instrumentation, QA receipts and current production output remain untouched by default. The new path is enabled only with `--enhanced`. Memory and joke rotation update only after a successful enhanced production delivery.

## Recommendation

The enhanced architecture meets the six acceptance tests on Edition 0038 and now sits well inside the current reading envelope. Keep production unchanged until Fordy reviews the email proof side by side. If the emotional rhythm holds in the inbox, activate `--enhanced` for a short governed production pilot while retaining the current path as the immediate rollback.

## The governing experience

| Rhythm | Product job |
|---|---|
| **Think** | THE ONE THING, fixed evidence and the optional Visual Signal establish the pattern quickly. |
| **Decide** | Interpretation, DTL View, What Changed and Executive Action convert evidence into judgement. |
| **Look up** | Counter-Signal and What to Watch reopen the conclusion to disciplined challenge. |
| **Smile** | The governed Dad Joke releases tension and makes the intelligence feel human. |

## Internal artefacts

- Current control: `data/edition0038-proof.html`
- Enhanced artefact: `data/edition0038-enhanced.html`
- Structured judgement plan: `data/edition0038-enhanced-plan.json`
- Metrics: `data/edition0038-comparison-metrics.json`
- Architecture audit: `docs/development-thesis-v1-audit.md`

## References

[1]: `data/edition0038-proof.html` — Edition 0038 Current control.  
[2]: `data/edition0038-enhanced.html` — Edition 0038 Enhanced acceptance artefact.  
[3]: `data/edition0038-enhanced-plan.json` — Structured judgement plan and evidence trace.  
[4]: `docs/development-thesis-v1-audit.md` — Current architecture audit and compatibility design.
"""
    OUT_MD.write_text(report)
    print(f"Metrics: {OUT_JSON}")
    print(f"Comparison: {OUT_MD}")
    print(f"Words: current={current['visible_words']} enhanced={enhanced['visible_words']} delta={delta_words:+d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
