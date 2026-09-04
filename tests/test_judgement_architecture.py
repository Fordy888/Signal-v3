from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime
from html import escape
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from src.enhanced_renderer import render_enhanced_email
from src.human_signal import load_jokes, select_joke
from src.judgement_plan import (
    JudgementPlanError,
    add_final_attempt_action_fallback,
    allocate_focus_numbers_content_mix,
    complete_ai_focus_reader_copy,
    generate_judgement_plan,
    normalise_word_bound_fields,
    prepare_content_mix_evidence,
    prepare_focus_number_evidence,
    recover_missing_focus_figures,
    validate_judgement_plan,
)
from src.signal_memory import apply_memory_update
from src.visual_signal import render_visual_signal


ROOT = Path(__file__).resolve().parents[1]
FOCUS_SOURCE_IDS = {f"S{i:02d}" for i in range(1, 11)}


def valid_plan() -> dict:
    return {
        "editorial_revision": "dynamic-headlines-v1",
        "one_thing": {
            "statement": "AI advantage is moving from model choice to operating discipline.",
            "business_implication": "Leaders should fund governance, knowledge quality and workflow design before adding more models.",
            "confidence": "HIGH",
            "evidence_ids": ["S01", "S03", "S06"],
        },
        "evidence_items": [
            {
                "source_ids": [f"S0{i}"],
                "category": category,
                "action_tag": "OPPORTUNITY" if i == 4 else ("WATCH" if i > 1 else "ACT"),
                "headline": headline,
                "evidence": "A source-backed fact remains separate from judgement.",
            }
            for i, (category, headline) in enumerate(
                [
                    ("Operations & Workflow", "Constrained agents outperform autonomous ones"),
                    ("Finance & Commercial Performance", "Infrastructure costs are moving up"),
                    ("Strategy & Leadership", "Cheaper models are winning buyers"),
                    ("Sales & Marketing", "AI products still need sales teams"),
                    ("People & Capability", "AI pressure is reaching wages"),
                    ("Data & Systems", "Messy knowledge breaks reliable agents"),
                    ("Governance & Risk", "Opaque automation creates regulatory risk"),
                ],
                1,
            )
        ],
        "interpretation_headline": "The advantage now comes from redesigning the work",
        "interpretation": "The collective evidence indicates that AI value is being limited by operating discipline more than access to models.",
        "founders_note": {
            "headline": "AI is infrastructure now. Price it that way.",
            "body": (
                "The stack is getting boring. That's a good sign. When serious buyers start focusing on "
                "billing flexibility, cost controls and operating discipline rather than magic, the technology "
                "is settling into its real role. Infrastructure. Commodity. Table stakes. The edge is no longer "
                "access because everyone has access. The edge is judgement about where to deploy it, which "
                "constraint it removes, and what that frees up. Most businesses are still asking whether they "
                "should use AI. The smarter question is where it produces a measurable business advantage. "
                "The technology is not the strategy. It never was. That is the whole game now. — Paul"
            ),
        },
        "what_changed": {
            "position_id": "ai-advantage-operating-system",
            "classification": "STRENGTHENS",
            "headline": "This is no longer a pilot story",
            "prior_position": "The operating system around AI matters more than model choice.",
            "current_position": "New evidence strengthens the operating-discipline thesis.",
            "explanation": "Constrained agents, cheaper models and data-quality failures point in the same direction.",
            "confidence": "HIGH",
        },
        "visual_signal": {
            "eligible": True,
            "type": "TENSION_MAP",
            "title": "Where AI advantage is moving",
            "subtitle": "Capability is abundant; operating discipline is scarce.",
            "rows": [
                {"label": "Model access", "status": "SUPPORTED", "detail": "Cheaper capable models are widening access."},
                {"label": "Knowledge quality", "status": "CONSTRAINED", "detail": "Messy documents limit reliability."},
                {"label": "Governance", "status": "EXPOSED", "detail": "Opaque automated decisions create risk."},
            ],
        },
        "counter_signal": {
            "headline": "Premium capability may still win specialist work",
            "statement": "Premium model capability may still dominate in high-value specialist work.",
            "would_change_view_if": "Enterprises demonstrate materially higher commercial returns from premium autonomous models than constrained workflows.",
            "confidence_effect": "That evidence would weaken the operating-discipline thesis.",
        },
        "executive_actions": [
            {
                "action_tag": "ACT",
                "headline": "Map the work AI can touch",
                "instruction": "Review one process for data quality, permission and human judgement before expanding it.",
            }
        ],
        "executive_read": {
            "dtl_view": "The next AI advantage is operational, not theatrical.",
            "watch_headline": "Look for proof beyond technology teams",
            "watch_items": ["Whether premium models produce measurable commercial returns."],
        },
        "memory_update": {
            "position_id": "ai-advantage-operating-system",
            "theme": "AI commercial advantage",
            "statement": "Operating discipline is becoming the binding constraint on AI value.",
            "confidence": "HIGH",
            "supporting_source_ids": ["S01", "S03", "S06"],
        },
    }


def focus_numbers_plan() -> dict:
    plan = valid_plan()
    plan["editorial_revision"] = "focus-on-the-numbers-v1"
    plan.pop("one_thing")
    plan.pop("visual_signal")
    plan["evidence_items"] = plan["evidence_items"][:5]
    for index, item in enumerate(plan["evidence_items"], 6):
        item["source_ids"] = [f"S{index:02d}"]
        item["mix_classification"] = "AI_BUSINESS" if index <= 8 else "MAJOR_BUSINESS"
        if item["mix_classification"] == "AI_BUSINESS":
            item["headline"] = f"AI {item['headline']}"
            item["evidence"] = "AI is changing a source-backed enterprise decision and commercial outcome."
            item["ai_business_connection"] = "AI changes a real operating decision, commercial outcome or workforce process."
        else:
            item["headline"] = "Capital costs are changing strategy" if index == 9 else "Hiring pressure is reaching wages"
            item["evidence"] = (
                "Higher financing costs are changing company investment decisions."
                if index == 9
                else "Employer demand is changing wages and workforce planning."
            )
    plan["founders_note"]["body"] = (
        "The most useful business stories usually have a number hiding inside them. Revenue, price, wages, customers and investment tell us whether change is real or merely interesting. This edition puts those figures in the open. Do not chase every headline. Find the number that changes a decision, then ask what it means for your business today. — Paul"
    )
    plan["focus_numbers"] = [
        {
            "source_ids": ["S01"],
            "entity": "SpaceX",
            "number": "$400 billion valuation",
            "meaning": "The new valuation raises the price of competing for private capital and specialist talent.",
        },
        {
            "source_ids": ["S02"],
            "entity": "Xero",
            "number": "$3 million remuneration increase",
            "meaning": "The rise puts performance, pay and shareholder value under the same governance lens.",
        },
        {
            "source_ids": ["S03"],
            "entity": "Australian retailers",
            "number": "20% quarterly growth",
            "meaning": "Faster growth shifts attention from demand generation to fulfilment capacity and margin discipline.",
        },
        {
            "source_ids": ["S04"],
            "entity": "Enterprise software",
            "number": "$12 billion invested",
            "meaning": "Capital is moving toward tools that can demonstrate operating savings rather than novelty.",
        },
        {
            "source_ids": ["S05"],
            "entity": "Australian employers",
            "number": "8,000 roles added",
            "meaning": "Hiring demand points to where confidence is returning and where capability gaps may widen.",
        },
    ]
    for index, item in enumerate(plan["focus_numbers"], 1):
        item["mix_classification"] = "AI_BUSINESS" if index <= 3 else "MAJOR_BUSINESS"
        if item["mix_classification"] == "AI_BUSINESS":
            item["meaning"] = f"AI {item['meaning']}"
            item["ai_business_connection"] = "AI changes a real operating decision, commercial outcome or workforce process."
    return plan


def focus_numeric_evidence(numeric_ids: set[str] | None = None) -> list[dict]:
    eligible = numeric_ids if numeric_ids is not None else set(FOCUS_SOURCE_IDS)
    items: list[dict] = []
    for index, source_id in enumerate(sorted(FOCUS_SOURCE_IDS), 11):
        is_ai = source_id in {"S01", "S02", "S03", "S06", "S07", "S08"}
        if source_id in eligible:
            evidence = (
                f"AI revenue increased {index}% as enterprise customers expanded contracted work."
                if is_ai
                else f"Revenue increased {index}% as customers expanded contracted work."
            )
        else:
            evidence = (
                "AI changed the enterprise workflow without a published figure."
                if is_ai
                else "The company discussed its strategy without publishing a figure."
            )
        items.append({
            "source_id": source_id,
            "title": f"Source {source_id} business result",
            "evidence": evidence,
            "scoring_reason": "Commercially material business evidence.",
        })
    return items


class JudgementArchitectureTests(unittest.TestCase):
    def test_valid_plan_passes_contract(self) -> None:
        plan = valid_plan()
        self.assertIs(validate_judgement_plan(plan, {f"S0{i}" for i in range(1, 8)}), plan)

    def test_focus_numbers_plan_requires_exactly_five_sourced_defining_figures(self) -> None:
        plan = focus_numbers_plan()
        self.assertIs(validate_judgement_plan(plan, FOCUS_SOURCE_IDS), plan)
        for invalid in (plan["focus_numbers"][:4], plan["focus_numbers"] + [plan["focus_numbers"][0]]):
            candidate = focus_numbers_plan()
            candidate["focus_numbers"] = invalid
            with self.assertRaises(JudgementPlanError):
                validate_judgement_plan(candidate, FOCUS_SOURCE_IDS)

    def test_focus_number_rejects_unsourced_or_non_numeric_copy(self) -> None:
        for field, value in (("source_ids", ["S99"]), ("number", "meaningful growth")):
            plan = focus_numbers_plan()
            plan["focus_numbers"][0][field] = value
            with self.assertRaises(JudgementPlanError):
                validate_judgement_plan(plan, FOCUS_SOURCE_IDS)

    def test_focus_numeric_pool_marks_only_explicit_eligible_figures(self) -> None:
        evidence = [
            {"source_id": "S01", "evidence": "Revenue rose 20% in the quarter."},
            {"source_id": "S02", "evidence": "Profit reached $4.2 billion."},
            {"source_id": "S03", "evidence": "The company added 8,000 roles."},
            {"source_id": "S04", "evidence": "The 2026 strategy names three priorities."},
            {"source_id": "S05", "evidence": "Management described stronger demand."},
        ]

        prepared, eligible = prepare_focus_number_evidence(evidence)

        self.assertEqual(eligible, {"S01", "S02", "S03"})
        by_id = {item["source_id"]: item for item in prepared}
        self.assertTrue(by_id["S01"]["focus_number_eligible"])
        self.assertIn("20%", by_id["S01"]["focus_number_candidate"])
        self.assertTrue(by_id["S02"]["focus_number_eligible"])
        self.assertIn("$4.2 billion", by_id["S02"]["focus_number_candidate"])
        self.assertFalse(by_id["S04"]["focus_number_eligible"])
        self.assertNotIn("focus_number_candidate", by_id["S04"])

    def test_focus_validation_rejects_source_outside_preverified_numeric_pool(self) -> None:
        plan = focus_numbers_plan()
        plan["focus_numbers"][0]["source_ids"] = ["S10"]
        with self.assertRaisesRegex(JudgementPlanError, "without pre-verified numeric evidence"):
            validate_judgement_plan(
                plan,
                FOCUS_SOURCE_IDS,
                {"S01", "S02", "S03", "S04", "S05"},
            )

    def test_focus_planner_holds_before_model_when_fewer_than_five_numeric_sources(self) -> None:
        evidence = focus_numeric_evidence({"S01", "S02", "S03", "S04"})
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.md"
            prompt_path.write_text(
                "editorial_revision focus-on-the-numbers-v1\n"
                "{EVIDENCE_ITEMS}\n{FOCUS_NUMBER_SOURCE_IDS}\n{SIGNAL_MEMORY}"
            )
            with patch("src.judgement_plan.Anthropic") as anthropic:
                with self.assertRaisesRegex(JudgementPlanError, "at least five distinct source records"):
                    generate_judgement_plan(evidence, {}, prompt_path)
        anthropic.assert_not_called()

    def test_focus_planner_exposes_and_enforces_preverified_numeric_pool(self) -> None:
        plan = focus_numbers_plan()
        response = SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(plan))])
        client = SimpleNamespace(messages=SimpleNamespace(create=Mock(return_value=response)))
        evidence = focus_numeric_evidence({"S01", "S02", "S03", "S04", "S05", "S06"})

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.md"
            prompt_path.write_text(
                "editorial_revision focus-on-the-numbers-v1\n"
                "{EVIDENCE_ITEMS}\n{FOCUS_NUMBER_SOURCE_IDS}\n{SIGNAL_MEMORY}"
            )
            with patch("src.judgement_plan.Anthropic", return_value=client), patch.dict(
                "os.environ", {"ANTHROPIC_API_KEY": "test-key"}
            ):
                result = generate_judgement_plan(evidence, {}, prompt_path)

        self.assertEqual(client.messages.create.call_count, 1)
        prompt_text = client.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn('"focus_number_eligible": true', prompt_text)
        self.assertIn('"S05"', prompt_text)
        self.assertIs(
            validate_judgement_plan(
                result,
                FOCUS_SOURCE_IDS,
                {"S01", "S02", "S03", "S04", "S05", "S06"},
            ),
            result,
        )

    def test_missing_focus_figure_recovers_from_same_selected_source_only(self) -> None:
        plan = focus_numbers_plan()
        plan["focus_numbers"][0]["number"] = "meaningful growth"
        evidence = [
            {
                "source_id": "S01",
                "title": "SpaceX valuation rises",
                "evidence": "SpaceX reached a $400 billion valuation after its latest transaction.",
            },
            {
                "source_id": "S02",
                "title": "Unrelated company result",
                "evidence": "An unrelated company reported $999 billion in revenue.",
            },
        ]

        repaired, repairs = recover_missing_focus_figures(plan, evidence)

        recovered = repaired["focus_numbers"][0]["number"]
        self.assertIn("$400 billion", recovered)
        self.assertNotIn("$999 billion", recovered)
        self.assertIn(recovered, evidence[0]["evidence"])
        self.assertEqual(repaired["focus_numbers"][0]["source_ids"], ["S01"])
        self.assertEqual(repaired["focus_numbers"][0]["number_recovered_from_source"], "S01")
        self.assertIn("focus_numbers[0].number", repairs)

    def test_missing_focus_figure_remains_hard_hold_without_same_source_number(self) -> None:
        plan = focus_numbers_plan()
        plan["focus_numbers"][0]["number"] = "meaningful growth"
        evidence = [{
            "source_id": "S01",
            "title": "SpaceX valuation discussion",
            "evidence": "The company discussed valuation without publishing an explicit figure.",
        }]

        repaired, repairs = recover_missing_focus_figures(plan, evidence)

        self.assertEqual(repairs, [])
        self.assertEqual(repaired["focus_numbers"][0]["number"], "meaningful growth")
        with self.assertRaisesRegex(JudgementPlanError, "must contain a defining figure"):
            validate_judgement_plan(repaired, FOCUS_SOURCE_IDS)

    def test_missing_focus_figure_does_not_recover_from_multiple_or_duplicate_sources(self) -> None:
        for evidence, source_ids in (
            ([{"source_id": "S01", "evidence": "Revenue reached $4 billion."}], ["S01", "S02"]),
            ([
                {"source_id": "S01", "evidence": "Revenue reached $4 billion."},
                {"source_id": "S01", "evidence": "Revenue reached $5 billion."},
            ], ["S01"]),
        ):
            with self.subTest(source_ids=source_ids, evidence_count=len(evidence)):
                plan = focus_numbers_plan()
                plan["focus_numbers"][0]["number"] = "meaningful growth"
                plan["focus_numbers"][0]["source_ids"] = source_ids
                repaired, repairs = recover_missing_focus_figures(plan, evidence)
                self.assertEqual(repairs, [])
                self.assertEqual(repaired["focus_numbers"][0]["number"], "meaningful growth")

    def test_focus_revision_rejects_newsroom_and_number_source_overlap(self) -> None:
        plan = focus_numbers_plan()
        plan["evidence_items"][0]["source_ids"] = plan["focus_numbers"][0]["source_ids"]
        with self.assertRaisesRegex(JudgementPlanError, "must use distinct sources"):
            validate_judgement_plan(plan, FOCUS_SOURCE_IDS)

    def test_focus_revision_requires_exact_sixty_forty_mix_in_each_section(self) -> None:
        plan = focus_numbers_plan()
        self.assertIs(validate_judgement_plan(plan, FOCUS_SOURCE_IDS), plan)
        for direction in ("too_few_ai", "too_many_ai"):
            with self.subTest(direction=direction):
                candidate = focus_numbers_plan()
                if direction == "too_few_ai":
                    candidate["focus_numbers"][2]["mix_classification"] = "MAJOR_BUSINESS"
                    candidate["focus_numbers"][2].pop("ai_business_connection")
                    candidate["focus_numbers"][2]["meaning"] = (
                        "Faster growth shifts attention from demand generation to fulfilment capacity and margin discipline."
                    )
                else:
                    candidate["evidence_items"][3]["mix_classification"] = "AI_BUSINESS"
                    candidate["evidence_items"][3]["headline"] = "AI changes capital allocation"
                    candidate["evidence_items"][3]["evidence"] = (
                        "AI is changing a real company investment decision and commercial outcome."
                    )
                    candidate["evidence_items"][3]["ai_business_connection"] = (
                        "AI changes a real operating decision, commercial outcome or workforce process."
                    )
                with self.assertRaisesRegex(JudgementPlanError, "exactly 3 AI_BUSINESS"):
                    validate_judgement_plan(candidate, FOCUS_SOURCE_IDS)

    def test_source_substance_classification_builds_independent_six_four_pools(self) -> None:
        prepared, verified = prepare_content_mix_evidence(focus_numeric_evidence())

        self.assertEqual(
            {source_id for source_id, value in verified.items() if value == "AI_BUSINESS"},
            {"S01", "S02", "S03", "S06", "S07", "S08"},
        )
        self.assertEqual(
            {source_id for source_id, value in verified.items() if value == "MAJOR_BUSINESS"},
            {"S04", "S05", "S09", "S10"},
        )
        by_id = {item["source_id"]: item for item in prepared}
        self.assertEqual(by_id["S01"]["verified_mix_classification"], "AI_BUSINESS")
        self.assertEqual(by_id["S04"]["verified_mix_classification"], "MAJOR_BUSINESS")

    def test_exact_section_mix_is_allocated_before_planner_generation(self) -> None:
        evidence = focus_numeric_evidence()
        prepared, focus_eligible = prepare_focus_number_evidence(evidence)
        prepared, verified = prepare_content_mix_evidence(prepared)

        allocation = allocate_focus_numbers_content_mix(prepared, focus_eligible, verified)

        self.assertEqual(allocation["focus_numbers"], ["S01", "S02", "S03", "S04", "S05"])
        self.assertEqual(allocation["newsroom"], ["S06", "S07", "S08", "S09", "S10"])
        self.assertEqual(
            [verified[source_id] for source_id in allocation["focus_numbers"]],
            ["AI_BUSINESS", "AI_BUSINESS", "AI_BUSINESS", "MAJOR_BUSINESS", "MAJOR_BUSINESS"],
        )
        self.assertEqual(
            [verified[source_id] for source_id in allocation["newsroom"]],
            ["AI_BUSINESS", "AI_BUSINESS", "AI_BUSINESS", "MAJOR_BUSINESS", "MAJOR_BUSINESS"],
        )

    def test_allocation_holds_before_model_when_focus_lacks_major_numeric_evidence(self) -> None:
        evidence = focus_numeric_evidence({"S01", "S02", "S03", "S04"})
        prepared, focus_eligible = prepare_focus_number_evidence(evidence)
        prepared, verified = prepare_content_mix_evidence(prepared)

        with self.assertRaisesRegex(JudgementPlanError, "at least 2 independently verified MAJOR_BUSINESS"):
            allocate_focus_numbers_content_mix(prepared, focus_eligible, verified)

    def test_preallocated_section_sources_cannot_be_substituted_by_planner(self) -> None:
        evidence = focus_numeric_evidence()
        prepared, focus_eligible = prepare_focus_number_evidence(evidence)
        prepared, verified = prepare_content_mix_evidence(prepared)
        allocation = allocate_focus_numbers_content_mix(prepared, focus_eligible, verified)
        plan = focus_numbers_plan()

        self.assertIs(
            validate_judgement_plan(
                plan,
                FOCUS_SOURCE_IDS,
                focus_eligible,
                verified,
                allocation,
            ),
            plan,
        )
        plan["focus_numbers"][3]["source_ids"] = ["S09"]
        plan["evidence_items"][3]["source_ids"] = ["S04"]
        with self.assertRaisesRegex(JudgementPlanError, "does not match the preallocated"):
            validate_judgement_plan(
                plan,
                FOCUS_SOURCE_IDS,
                focus_eligible,
                verified,
                allocation,
            )

    def test_planner_receives_and_obeys_preallocated_section_sources(self) -> None:
        plan = focus_numbers_plan()
        response = SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(plan))])
        client = SimpleNamespace(messages=SimpleNamespace(create=Mock(return_value=response)))

        with patch("src.judgement_plan.Anthropic", return_value=client), patch.dict(
            "os.environ", {"ANTHROPIC_API_KEY": "test-key"}
        ):
            result = generate_judgement_plan(
                focus_numeric_evidence(),
                {},
                ROOT / "prompts" / "judgement_planner_prompt.md",
            )

        self.assertEqual(client.messages.create.call_count, 1)
        self.assertEqual(
            [item["source_ids"][0] for item in result["evidence_items"]],
            ["S06", "S07", "S08", "S09", "S10"],
        )
        self.assertEqual(
            [item["source_ids"][0] for item in result["focus_numbers"]],
            ["S01", "S02", "S03", "S04", "S05"],
        )
        prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn('Preallocated Newsroom source IDs\n\n["S06", "S07", "S08", "S09", "S10"]', prompt)
        self.assertIn('Preallocated Focus on the Numbers source IDs\n\n["S01", "S02", "S03", "S04", "S05"]', prompt)

    def test_planner_labels_cannot_reclassify_independently_verified_source(self) -> None:
        plan = focus_numbers_plan()
        plan["evidence_items"][3]["mix_classification"] = "AI_BUSINESS"
        plan["evidence_items"][3]["ai_business_connection"] = (
            "AI changes a real operating decision, commercial outcome or workforce process."
        )
        _, verified = prepare_content_mix_evidence(focus_numeric_evidence())

        with self.assertRaisesRegex(JudgementPlanError, "verified as MAJOR_BUSINESS"):
            validate_judgement_plan(plan, FOCUS_SOURCE_IDS, FOCUS_SOURCE_IDS, verified)

    def test_focus_planner_holds_before_model_when_independent_mix_pool_is_too_ai_heavy(self) -> None:
        evidence = focus_numeric_evidence()
        for item in evidence:
            if item["source_id"] in {"S04", "S05", "S09"}:
                item["evidence"] = "AI revenue increased 20% as enterprise customers expanded."
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.md"
            prompt_path.write_text(
                "editorial_revision focus-on-the-numbers-v1\n"
                "{EVIDENCE_ITEMS}\n{FOCUS_NUMBER_SOURCE_IDS}\n"
                "{AI_BUSINESS_SOURCE_IDS}\n{MAJOR_BUSINESS_SOURCE_IDS}\n{SIGNAL_MEMORY}"
            )
            with patch("src.judgement_plan.Anthropic") as anthropic:
                with self.assertRaisesRegex(JudgementPlanError, "six independently verified AI-business"):
                    generate_judgement_plan(evidence, {}, prompt_path)
        anthropic.assert_not_called()

    def test_unknown_source_is_rejected(self) -> None:
        plan = valid_plan()
        plan["evidence_items"][0]["source_ids"] = ["S99"]
        with self.assertRaises(JudgementPlanError):
            validate_judgement_plan(plan, {f"S0{i}" for i in range(1, 8)})

    def test_invalid_change_classification_is_rejected(self) -> None:
        plan = valid_plan()
        plan["what_changed"]["classification"] = "NEW"
        with self.assertRaises(JudgementPlanError):
            validate_judgement_plan(plan, {f"S0{i}" for i in range(1, 8)})

    def test_founders_note_requires_established_format_and_inline_signoff(self) -> None:
        plan = valid_plan()
        plan["founders_note"]["body"] = "Compressed CEO view without the established founder format."
        with self.assertRaises(JudgementPlanError):
            validate_judgement_plan(plan, {f"S0{i}" for i in range(1, 8)})

    def test_word_bound_normaliser_repairs_copy_without_weakening_structure(self) -> None:
        plan = valid_plan()
        plan["interpretation"] = " ".join(["interpretation"] * 60)
        plan["evidence_items"][0]["headline"] = "one two three four five six seven eight nine ten"
        plan["founders_note"]["body"] = " ".join(["Founder"] * 190) + " — Paul"

        normalised, repairs = normalise_word_bound_fields(plan)

        self.assertEqual(len(normalised["interpretation"].split()), 55)
        self.assertEqual(len(normalised["evidence_items"][0]["headline"].split()), 8)
        self.assertLessEqual(len(normalised["founders_note"]["body"].split()), 180)
        self.assertTrue(normalised["founders_note"]["body"].endswith("— Paul"))
        self.assertIn("interpretation", repairs)
        self.assertIn("evidence_items[0].headline", repairs)
        self.assertIn("founders_note.body", repairs)
        self.assertIs(
            validate_judgement_plan(normalised, {f"S0{i}" for i in range(1, 8)}),
            normalised,
        )

    def test_focus_revision_caps_founders_note_at_half_the_previous_maximum(self) -> None:
        plan = focus_numbers_plan()
        plan["founders_note"]["body"] = " ".join(["Founder"] * 120) + " — Paul"
        normalised, repairs = normalise_word_bound_fields(plan)
        self.assertLessEqual(len(normalised["founders_note"]["body"].split()), 90)
        self.assertIn("founders_note.body", repairs)

    def test_focus_number_normaliser_preserves_defining_figure_after_verbose_lead_in(self) -> None:
        plan = focus_numbers_plan()
        plan["focus_numbers"][0]["number"] = (
            "Annual recurring revenue from AI and data products increased sharply to $1.2 billion"
        )

        normalised, repairs = normalise_word_bound_fields(plan)
        number = normalised["focus_numbers"][0]["number"]

        self.assertLessEqual(len(number.split()), 10)
        self.assertRegex(number, r"\d")
        self.assertIn("$1.2 billion", number)
        self.assertIn("focus_numbers[0].number", repairs)
        self.assertIs(validate_judgement_plan(normalised, FOCUS_SOURCE_IDS), normalised)

    def test_focus_revision_normalises_every_safe_presentation_bound(self) -> None:
        plan = focus_numbers_plan()
        plan["evidence_items"][0]["headline"] = (
            "AI changes business operations before " + " ".join(["growth"] * 6)
        )
        plan["evidence_items"][0]["evidence"] = (
            "AI changes enterprise operations and commercial outcomes "
            + " ".join(["evidence"] * 26)
        )
        plan["evidence_items"][0]["ai_business_connection"] = " ".join(["impact"] * 33)
        plan["focus_numbers"][0]["entity"] = " ".join(["company"] * 8)
        plan["focus_numbers"][0]["number"] = (
            "Annual recurring revenue from AI and data products increased sharply to $1.2 billion"
        )
        plan["focus_numbers"][0]["meaning"] = " ".join(["meaning"] * 30)
        plan["focus_numbers"][0]["ai_business_connection"] = " ".join(["connection"] * 34)
        plan["interpretation"] = " ".join(["interpretation"] * 60)
        plan["interpretation_headline"] = " ".join(["why"] * 12)
        plan["founders_note"]["headline"] = " ".join(["founder"] * 14)
        plan["founders_note"]["body"] = " ".join(["Founder"] * 100) + " — Paul"
        plan["counter_signal"]["headline"] = " ".join(["counter"] * 12)
        plan["counter_signal"]["statement"] = " ".join(["counter"] * 70)
        plan["counter_signal"]["would_change_view_if"] = " ".join(["evidence"] * 50)
        plan["executive_actions"] = [dict(plan["executive_actions"][0]) for _ in range(4)]
        plan["executive_actions"][0]["headline"] = " ".join(["action"] * 8)
        plan["executive_actions"][0]["instruction"] = " ".join(["instruction"] * 25)
        plan["executive_read"]["dtl_view"] = " ".join(["view"] * 80)
        plan["executive_read"]["watch_headline"] = " ".join(["watch"] * 12)
        plan["executive_read"]["watch_items"] = [" ".join(["proof"] * 36)]

        normalised, repairs = normalise_word_bound_fields(plan)

        expected_repairs = {
            "evidence_items[0].headline",
            "evidence_items[0].evidence",
            "evidence_items[0].ai_business_connection",
            "focus_numbers[0].entity",
            "focus_numbers[0].number",
            "focus_numbers[0].meaning",
            "focus_numbers[0].ai_business_connection",
            "interpretation",
            "interpretation_headline",
            "founders_note.headline",
            "founders_note.body",
            "counter_signal.headline",
            "counter_signal.statement",
            "counter_signal.would_change_view_if",
            "executive_actions",
            "executive_actions[0].headline",
            "executive_actions[0].instruction",
            "executive_read.dtl_view",
            "executive_read.watch_headline",
            "executive_read.watch_items[0]",
        }
        self.assertTrue(expected_repairs.issubset(set(repairs)))
        self.assertEqual(len(normalised["executive_actions"]), 3)
        self.assertRegex(normalised["focus_numbers"][0]["number"], r"\d")
        self.assertIs(validate_judgement_plan(normalised, FOCUS_SOURCE_IDS), normalised)

    def test_headline_normaliser_removes_dangling_endings_and_validator_blocks_them(self) -> None:
        plan = focus_numbers_plan()
        plan["evidence_items"][0]["headline"] = "AI renewal agent covers every account not just"
        plan["counter_signal"]["headline"] = "AI governance gap is now a commercial liability not a"
        plan["executive_read"]["watch_headline"] = "Track AI correction time in your"

        with self.assertRaisesRegex(JudgementPlanError, "complete phrase|incomplete"):
            validate_judgement_plan(plan, FOCUS_SOURCE_IDS)

        normalised, repairs = normalise_word_bound_fields(plan)
        self.assertEqual(normalised["evidence_items"][0]["headline"], "AI renewal agent covers every account")
        self.assertEqual(normalised["counter_signal"]["headline"], "AI governance gap is now a commercial liability")
        self.assertEqual(normalised["executive_read"]["watch_headline"], "Track AI correction time")
        self.assertIn("evidence_items[0].headline", repairs)
        self.assertIn("counter_signal.headline", repairs)
        self.assertIn("executive_read.watch_headline", repairs)
        self.assertIs(validate_judgement_plan(normalised, FOCUS_SOURCE_IDS), normalised)

    def test_watch_headline_rejects_and_repairs_live_moving_above_fragment(self) -> None:
        plan = focus_numbers_plan()
        plan["executive_read"]["watch_headline"] = "Enterprise AI scaling success rate moving above"

        with self.assertRaisesRegex(JudgementPlanError, "incomplete"):
            validate_judgement_plan(plan, FOCUS_SOURCE_IDS)

        normalised, repairs = normalise_word_bound_fields(plan)
        self.assertEqual(
            normalised["executive_read"]["watch_headline"],
            "Enterprise AI scaling success rate",
        )
        self.assertIn("executive_read.watch_headline", repairs)
        self.assertIs(validate_judgement_plan(normalised, FOCUS_SOURCE_IDS), normalised)

    def test_major_business_reader_copy_cannot_gain_ai_angle(self) -> None:
        plan = focus_numbers_plan()
        plan["focus_numbers"][3]["meaning"] = (
            "AI tools turn the investment into a faster enterprise workflow."
        )
        _, verified = prepare_content_mix_evidence(focus_numeric_evidence())

        with self.assertRaisesRegex(JudgementPlanError, "must not introduce an AI-led angle"):
            validate_judgement_plan(plan, FOCUS_SOURCE_IDS, FOCUS_SOURCE_IDS, verified)

    def test_ai_business_reader_copy_must_keep_ai_subject_and_business_consequence(self) -> None:
        plan = focus_numbers_plan()
        plan["focus_numbers"][0]["meaning"] = "The result is notable."
        plan["focus_numbers"][0]["entity"] = "SpaceX"
        _, verified = prepare_content_mix_evidence(focus_numeric_evidence())

        with self.assertRaisesRegex(JudgementPlanError, "explicit AI subject"):
            validate_judgement_plan(plan, FOCUS_SOURCE_IDS, FOCUS_SOURCE_IDS, verified)

    def test_ai_focus_reader_copy_completion_uses_only_its_selected_source(self) -> None:
        plan = focus_numbers_plan()
        plan["focus_numbers"][0]["entity"] = "SpaceX"
        plan["focus_numbers"][0]["meaning"] = "The result is notable."
        evidence = focus_numeric_evidence()

        repaired, repairs = complete_ai_focus_reader_copy(plan, evidence)

        self.assertEqual(
            repaired["focus_numbers"][0]["meaning"],
            "AI revenue increased 11% as enterprise customers expanded contracted work.",
        )
        self.assertEqual(
            repaired["focus_numbers"][0]["reader_copy_completed_from_source"],
            "S01",
        )
        self.assertIn("focus_numbers[0].meaning", repairs)
        _, verified = prepare_content_mix_evidence(evidence)
        allocation = allocate_focus_numbers_content_mix(
            evidence,
            FOCUS_SOURCE_IDS,
            verified,
        )
        self.assertIs(
            validate_judgement_plan(
                repaired,
                FOCUS_SOURCE_IDS,
                FOCUS_SOURCE_IDS,
                verified,
                allocation,
            ),
            repaired,
        )

    def test_ai_focus_reader_copy_completion_never_borrows_another_source(self) -> None:
        plan = focus_numbers_plan()
        plan["focus_numbers"][0]["entity"] = "SpaceX"
        plan["focus_numbers"][0]["meaning"] = "The result is notable."
        evidence = focus_numeric_evidence()
        evidence[0]["evidence"] = "The company discussed strategy without publishing a quantified operating result."
        evidence[0]["title"] = "Company strategy update"
        evidence[0]["scoring_reason"] = "General update."

        repaired, repairs = complete_ai_focus_reader_copy(plan, evidence)

        self.assertEqual(repairs, [])
        self.assertEqual(repaired["focus_numbers"][0]["meaning"], "The result is notable.")
        self.assertNotIn("reader_copy_completed_from_source", repaired["focus_numbers"][0])

    def test_major_business_focus_copy_is_never_modified_by_ai_completion(self) -> None:
        plan = focus_numbers_plan()
        original = copy.deepcopy(plan["focus_numbers"][3])

        repaired, repairs = complete_ai_focus_reader_copy(plan, focus_numeric_evidence())

        self.assertEqual(repairs, [])
        self.assertEqual(repaired["focus_numbers"][3], original)

    def test_planner_final_attempt_completes_live_ai_focus_reader_copy(self) -> None:
        plan = focus_numbers_plan()
        plan["focus_numbers"][0]["entity"] = "SpaceX"
        plan["focus_numbers"][0]["meaning"] = "The result is notable."
        response = SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(plan))])
        client = SimpleNamespace(messages=SimpleNamespace(create=Mock(return_value=response)))
        evidence = focus_numeric_evidence()

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.md"
            prompt_path.write_text("{EVIDENCE_ITEMS}\n{SIGNAL_MEMORY}")
            with patch("src.judgement_plan.Anthropic", return_value=client), patch(
                "src.judgement_plan.time.sleep"
            ), patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                result = generate_judgement_plan(evidence, {}, prompt_path)

        self.assertEqual(client.messages.create.call_count, 3)
        self.assertEqual(
            result["focus_numbers"][0]["meaning"],
            "AI revenue increased 11% as enterprise customers expanded contracted work.",
        )
        self.assertEqual(
            result["focus_numbers"][0]["reader_copy_completed_from_source"],
            "S01",
        )

    def test_final_attempt_normalisation_keeps_substantive_failures_hard(self) -> None:
        for path in ("newsroom_connection", "focus_connection", "numeric_figure"):
            with self.subTest(path=path):
                plan = focus_numbers_plan()
                if path == "newsroom_connection":
                    plan["evidence_items"][0]["ai_business_connection"] = ""
                elif path == "focus_connection":
                    plan["focus_numbers"][0]["ai_business_connection"] = ""
                else:
                    plan["focus_numbers"][0]["number"] = "meaningful growth"
                normalised, _ = normalise_word_bound_fields(plan)
                with self.assertRaises(JudgementPlanError):
                    validate_judgement_plan(normalised, FOCUS_SOURCE_IDS)

    def test_planner_final_attempt_repairs_live_overlong_ai_business_connections(self) -> None:
        plan = focus_numbers_plan()
        plan["evidence_items"][0]["ai_business_connection"] = " ".join(["impact"] * 34)
        plan["focus_numbers"][0]["ai_business_connection"] = " ".join(["connection"] * 35)
        response = SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(plan))])
        client = SimpleNamespace(messages=SimpleNamespace(create=Mock(return_value=response)))
        evidence = focus_numeric_evidence()

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.md"
            prompt_path.write_text("{EVIDENCE_ITEMS}\n{SIGNAL_MEMORY}")
            with patch("src.judgement_plan.Anthropic", return_value=client), patch(
                "src.judgement_plan.time.sleep"
            ), patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                result = generate_judgement_plan(evidence, {}, prompt_path)

        self.assertEqual(client.messages.create.call_count, 3)
        self.assertLessEqual(len(result["evidence_items"][0]["ai_business_connection"].split()), 28)
        self.assertLessEqual(len(result["focus_numbers"][0]["ai_business_connection"].split()), 28)
        self.assertIs(validate_judgement_plan(result, FOCUS_SOURCE_IDS), result)

    def test_planner_final_attempt_repairs_live_overlong_focus_number(self) -> None:
        plan = focus_numbers_plan()
        plan["focus_numbers"][0]["number"] = (
            "Annual recurring revenue from AI and data products increased sharply to $1.2 billion"
        )
        response = SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(plan))])
        client = SimpleNamespace(messages=SimpleNamespace(create=Mock(return_value=response)))
        evidence = focus_numeric_evidence()

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.md"
            prompt_path.write_text("{EVIDENCE_ITEMS}\n{SIGNAL_MEMORY}")
            with patch("src.judgement_plan.Anthropic", return_value=client), patch(
                "src.judgement_plan.time.sleep"
            ), patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                result = generate_judgement_plan(evidence, {}, prompt_path)

        repaired_number = result["focus_numbers"][0]["number"]
        self.assertEqual(client.messages.create.call_count, 3)
        self.assertLessEqual(len(repaired_number.split()), 10)
        self.assertRegex(repaired_number, r"\d")
        self.assertIn("$1.2 billion", repaired_number)

    def test_planner_final_attempt_recovers_live_missing_focus_figure_from_selected_source(self) -> None:
        plan = focus_numbers_plan()
        plan["focus_numbers"][0]["number"] = "meaningful growth"
        response = SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(plan))])
        client = SimpleNamespace(messages=SimpleNamespace(create=Mock(return_value=response)))
        evidence = [
            {
                "source_id": source_id,
                "title": "SpaceX valuation rises" if source_id == "S01" else f"Source {source_id}",
                "evidence": (
                    "SpaceX reached a $400 billion valuation after its latest transaction."
                    if source_id == "S01"
                    else f"Revenue increased {index}% as customers expanded contracted work."
                ),
            }
            for index, source_id in enumerate(sorted(FOCUS_SOURCE_IDS), 11)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.md"
            prompt_path.write_text("{EVIDENCE_ITEMS}\n{SIGNAL_MEMORY}")
            with patch("src.judgement_plan.Anthropic", return_value=client), patch(
                "src.judgement_plan.time.sleep"
            ), patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                result = generate_judgement_plan(evidence, {}, prompt_path)

        self.assertEqual(client.messages.create.call_count, 3)
        self.assertIn("$400 billion", result["focus_numbers"][0]["number"])
        self.assertEqual(result["focus_numbers"][0]["number_recovered_from_source"], "S01")
        self.assertIs(validate_judgement_plan(result, FOCUS_SOURCE_IDS), result)

    def test_planner_final_attempt_adds_source_bound_action_when_model_returns_none(self) -> None:
        plan = focus_numbers_plan()
        plan["executive_actions"] = []
        response = SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(plan))])
        client = SimpleNamespace(messages=SimpleNamespace(create=Mock(return_value=response)))
        evidence = focus_numeric_evidence()

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.md"
            prompt_path.write_text("{EVIDENCE_ITEMS}\n{SIGNAL_MEMORY}")
            with patch("src.judgement_plan.Anthropic", return_value=client), patch(
                "src.judgement_plan.time.sleep"
            ), patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                result = generate_judgement_plan(evidence, {}, prompt_path)

        self.assertEqual(client.messages.create.call_count, 3)
        self.assertEqual(len(result["executive_actions"]), 1)
        action = result["executive_actions"][0]
        self.assertTrue(action["fallback_generated"])
        self.assertEqual(action["source_ids"], ["S06"])
        self.assertLessEqual(len(action["headline"].split()), 6)
        self.assertLessEqual(len(action["instruction"].split()), 20)
        self.assertIs(validate_judgement_plan(result, FOCUS_SOURCE_IDS), result)

    def test_final_attempt_action_fallback_preserves_existing_actions(self) -> None:
        plan = focus_numbers_plan()
        repaired, repairs = add_final_attempt_action_fallback(plan)
        self.assertEqual(repairs, [])
        self.assertEqual(repaired["executive_actions"], plan["executive_actions"])

    def test_planner_final_attempt_normalises_superficial_word_overruns(self) -> None:
        plan = valid_plan()
        plan["interpretation"] = " ".join(["interpretation"] * 60)
        plan["evidence_items"][0]["headline"] = "one two three four five six seven eight nine"
        response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(plan))]
        )
        client = SimpleNamespace(messages=SimpleNamespace(create=Mock(return_value=response)))
        evidence = [{"source_id": f"S0{i}"} for i in range(1, 8)]

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.md"
            prompt_path.write_text("{EVIDENCE_ITEMS}\n{SIGNAL_MEMORY}")
            with patch("src.judgement_plan.Anthropic", return_value=client), patch(
                "src.judgement_plan.time.sleep"
            ), patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                result = generate_judgement_plan(evidence, {}, prompt_path)

        self.assertEqual(client.messages.create.call_count, 3)
        self.assertEqual(len(result["interpretation"].split()), 55)
        self.assertEqual(len(result["evidence_items"][0]["headline"].split()), 8)

    def test_visual_signal_is_optional_and_governed(self) -> None:
        self.assertEqual(render_visual_signal({"eligible": False, "type": "NONE", "rows": []}), "")
        rendered = render_visual_signal(valid_plan()["visual_signal"])
        self.assertIn("VISUAL SIGNAL", rendered)
        self.assertIn("THE SHIFT", render_visual_signal(valid_plan()["visual_signal"], dynamic_headlines=True))
        self.assertIn("Knowledge quality", rendered)

    def test_joke_library_has_100_and_rotation_blocks_recent(self) -> None:
        jokes = load_jokes(ROOT / "data" / "dad_jokes.json")
        self.assertEqual(len(jokes), 100)
        first = select_joke(jokes, 38, [])
        second = select_joke(jokes, 38, [first["id"]])
        self.assertNotEqual(first["id"], second["id"])

    def test_memory_update_records_position_movement(self) -> None:
        plan = valid_plan()
        memory = {"version": 1, "positions": [], "events": []}
        updated = apply_memory_update(
            memory,
            plan["memory_update"],
            plan["what_changed"],
            edition_number=38,
            delivered_at="2026-08-24T06:06:00+10:00",
        )
        self.assertEqual(updated["positions"][0]["confidence"], "HIGH")
        self.assertEqual(updated["events"][0]["classification"], "STRENGTHENS")

    def test_renderer_follows_intelligence_sequence_and_boundaries(self) -> None:
        rendered_plan = focus_numbers_plan()
        internal_categories = [
            "venture_capital",
            "opportunity_radar",
            "ai_market_signals",
            "enterprise_adoption",
            "workforce_change",
        ]
        for item, category in zip(rendered_plan["evidence_items"], internal_categories):
            item["category"] = category
        sources = json.loads((ROOT / "data" / "fixtures" / "edition0038_evidence.json").read_text())
        existing_ids = {source["source_id"] for source in sources}
        for index in range(1, 11):
            source_id = f"S{index:02d}"
            if source_id not in existing_ids:
                sources.append({
                    "source_id": source_id,
                    "source": f"Source {index}",
                    "url": f"https://example.com/source-{index}",
                })
        joke = load_jokes(ROOT / "data" / "dad_jokes.json")[0]
        html = render_enhanced_email(
            rendered_plan,
            sources,
            joke,
            edition_number=38,
            generated_at=datetime(2026, 8, 24, 6, 6, tzinfo=ZoneInfo("Australia/Brisbane")),
            alive_moment=json.loads((ROOT / "data" / "fixtures" / "alive_moment_0038.json").read_text()),
        )
        signature = ["THINK.", "DECIDE.", "LOOK UP.", "SMILE."]
        signature_positions = [html.index(label) for label in signature]
        self.assertEqual(signature_positions, sorted(signature_positions))
        self.assertLess(signature_positions[-1], html.index("FOUNDER'S NOTE"))
        sequence = [
            "FOUNDER'S NOTE",
            "AI is infrastructure now. Price it that way.",
            "— Paul",
            "DTL SIGNAL NEWSROOM — READ THIS",
            "YOUR SIGNAL AT A GLANCE",
            focus_numbers_plan()["evidence_items"][0]["headline"],
            "FOCUS ON THE NUMBERS",
            "SpaceX",
            "$400 billion valuation",
            "WHY IT MATTERS",
            focus_numbers_plan()["interpretation_headline"],
            "WHAT TO DO NOW",
            focus_numbers_plan()["executive_actions"][0]["headline"],
            "THE OTHER SIDE",
            focus_numbers_plan()["counter_signal"]["headline"],
            "WATCH FOR THIS",
            "REMEMBER THE WORLD",
            "DAD JOKE OF THE DAY",
        ]
        positions = [html.index(label) for label in sequence]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("THE EVIDENCE", html)
        self.assertEqual(html.count("DTL SIGNAL NEWSROOM — READ THIS"), 1)
        self.assertNotIn("TODAY'S NEWSROOM", html)
        self.assertNotIn("Be smart — read this.", html)
        self.assertNotIn("THE ONE THING", html)
        self.assertNotIn("THE SHIFT", html)
        self.assertNotIn("WHAT CHANGED", html)
        self.assertEqual(html.count("FOCUS ON THE NUMBERS"), 1)
        self.assertEqual(html.count("Source:"), 5)
        for category in internal_categories:
            self.assertNotIn(category, html)
        selected_ids = {
            source_id
            for item in (
                focus_numbers_plan()["evidence_items"]
                + focus_numbers_plan()["focus_numbers"]
            )
            for source_id in item["source_ids"]
        }
        for source in sources:
            if source["source_id"] in selected_ids:
                self.assertEqual(html.count(source["url"]), 1)
        self.assertEqual(html.count("YOUR SIGNAL AT A GLANCE"), 1)
        self.assertEqual(html.count("THINK."), 1)
        self.assertEqual(html.count("DECIDE."), 1)
        self.assertEqual(html.count("LOOK UP."), 1)
        self.assertEqual(html.count("SMILE."), 1)
        self.assertIn('<span style="color:#C43F2C;">THINK.</span>', html)
        self.assertIn('<span style="color:#966300;">DECIDE.</span>', html)
        self.assertIn('<span style="color:#2B7F8C;">LOOK UP.</span>', html)
        self.assertIn('<span style="color:#0B7F78;">SMILE.</span>', html)
        self.assertIn("ACT NOW", html)
        self.assertIn("WATCH CLOSELY", html)
        self.assertIn("OPPORTUNITY", html)
        self.assertIn("Decision or action", html)
        self.assertIn("Developing change", html)
        self.assertIn("Opening to explore", html)
        self.assertIn("background:#E8533A", html)
        self.assertIn("background:#E6A817", html)
        self.assertIn("background:#17A398", html)
        self.assertNotIn("EXECUTIVE READ", html)
        self.assertNotIn("INTERPRETATION", html)
        self.assertNotIn("WHAT CHANGED?", html)
        self.assertNotIn("EXECUTIVE ACTION / WATCH", html)
        self.assertNotIn("COUNTER-SIGNAL", html)
        self.assertIn("FOUNDER'S NOTE", html)
        self.assertEqual(html.count("FOUNDER'S NOTE"), 1)
        self.assertIn(focus_numbers_plan()["founders_note"]["headline"], html)
        self.assertIn(escape(focus_numbers_plan()["founders_note"]["body"]), html)
        self.assertEqual(html.count("— Paul"), 1)
        self.assertNotIn("CEO VIEW", html)
        self.assertNotIn("Do something different today … Paul", html)
        self.assertNotIn("WE ARE ALIVE", html)
        self.assertNotIn("Signal learns. Every open, every click, every skip trains the next edition.", html)
        self.assertIn('<table width="100%" cellpadding="0" cellspacing="0" style="width:100%;margin:0;">', html)
        self.assertIn('width="820"', html)
        self.assertIn('max-width:820px', html)
        self.assertIn('color:#6B7280;text-align:left;', html)
        self.assertIn("PF::SIGNAL-0038 // 24.08.2026 // 06:06 AEST", html)
        self.assertIn('color:#17A398;letter-spacing:1px;">Edition 0038', html)
        self.assertIn('font-size:12px;color:#17A398;letter-spacing:1.5px', html)
        self.assertIn('border-top:2px solid #4ECDC4;padding-top:14px;', html)
        self.assertIn('padding:18px 40px 22px 40px;', html)
        self.assertNotIn('color:#aaa;letter-spacing:2px;text-transform:uppercase;">THINK</p>', html)
        self.assertNotIn('color:#aaa;letter-spacing:2px;text-transform:uppercase;">DECIDE</p>', html)
        self.assertNotIn('color:#aaa;letter-spacing:2px;text-transform:uppercase;">LOOK UP</p>', html)
        self.assertNotIn('color:#aaa;letter-spacing:2px;text-transform:uppercase;">SMILE</p>', html)
        self.assertIn('color:#17A398;text-decoration:underline;">→ dtlc.ai</a>', html)
        self.assertNotIn("opacity:", html)
        self.assertIn("Financial Times (via Simon Willison)", html)
        self.assertNotIn("Simon Willison / Financial Times", html)
        self.assertIn("Photo: Charles J. Sharp · Wikimedia Commons", html)
        self.assertIn('text-decoration:underline;">CC BY-SA 4.0</a>', html)
        self.assertNotIn(">source</a>", html)
        self.assertNotIn(">licence</a>", html)
        self.assertEqual(html.count("DAD JOKE OF THE DAY"), 1)
        self.assertLess(html.index("DAD JOKE OF THE DAY"), html.index("PF::SIGNAL-0038"))

    def test_dynamic_reader_language_rejects_internal_codes_and_jargon(self) -> None:
        for field, value in (
            (("what_changed", "explanation"), "S01 and S02 now confirm the pattern."),
            (("interpretation",), "The CRM UI is becoming optional."),
            (("counter_signal", "headline"), "SoR control may slow adoption"),
        ):
            plan = valid_plan()
            container = plan
            for key in field[:-1]:
                container = container[key]
            container[field[-1]] = value
            with self.assertRaises(JudgementPlanError):
                validate_judgement_plan(plan, {f"S0{i}" for i in range(1, 8)})

        focus_plan = focus_numbers_plan()
        focus_plan["focus_numbers"][0]["meaning"] = "S01 proves the CRM change."
        with self.assertRaises(JudgementPlanError):
            validate_judgement_plan(focus_plan, FOCUS_SOURCE_IDS)

    def test_historical_plan_can_still_render_locked_v4(self) -> None:
        plan = valid_plan()
        plan.pop("editorial_revision")
        plan.pop("interpretation_headline")
        plan["what_changed"].pop("headline")
        plan["counter_signal"].pop("headline")
        plan["executive_actions"] = ["Audit one workflow before expanding it."]
        plan["executive_read"].pop("watch_headline")
        validated = validate_judgement_plan(plan, {f"S0{i}" for i in range(1, 8)})
        self.assertIs(validated, plan)


if __name__ == "__main__":
    unittest.main()
