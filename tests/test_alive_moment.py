import copy
import copy
import json
import unittest
from pathlib import Path

from src.alive_moment import AliveMomentError, validate_alive_moment


ROOT = Path(__file__).resolve().parents[1]


class AliveMomentTests(unittest.TestCase):
    def setUp(self):
        self.moment = json.loads((ROOT / "data" / "fixtures" / "alive_moment_0038.json").read_text())

    def test_valid_real_licensed_seasonal_moment_passes(self):
        self.assertEqual(validate_alive_moment(self.moment, []), self.moment)

    def test_real_licensed_human_craft_moment_passes(self):
        moment = json.loads(
            (ROOT / "data" / "fixtures" / "alive_moment_0044.json").read_text()
        )
        history = [{"image_source_url": self.moment["image_source_url"], "location": "Moorea", "category": "marine_life"}]
        self.assertEqual(
            validate_alive_moment(
                moment,
                history,
                expected_edition_id="0044",
                expected_date="2026-09-01",
            ),
            moment,
        )

    def test_ai_image_is_rejected(self):
        candidate = copy.deepcopy(self.moment)
        candidate["is_ai_generated"] = True
        with self.assertRaises(AliveMomentError):
            validate_alive_moment(candidate, [])

    def test_candidate_requires_an_approved_natural_colour_family(self):
        candidate = json.loads(
            (ROOT / "data" / "fixtures" / "alive_moment_0044.json").read_text()
        )
        candidate["dominant_colour_family"] = "purple"
        with self.assertRaises(AliveMomentError):
            validate_alive_moment(candidate, [])

    def test_quang_phu_cau_is_recorded_as_naturally_coral_without_image_manipulation(self):
        candidate = json.loads(
            (ROOT / "data" / "fixtures" / "alive_moment_0044.json").read_text()
        )
        self.assertEqual(candidate["dominant_colour_family"], "coral")
        self.assertIn("not been recoloured or tinted", candidate["colour_harmony_note"])

    def test_uncertain_licence_is_rejected(self):
        candidate = copy.deepcopy(self.moment)
        candidate["licence_type"] = "UNKNOWN"
        with self.assertRaises(AliveMomentError):
            validate_alive_moment(candidate, [])

    def test_place_image_mismatch_is_rejected(self):
        candidate = copy.deepcopy(self.moment)
        candidate["location"] = "Sydney"
        candidate["country"] = "Australia"
        with self.assertRaises(AliveMomentError):
            validate_alive_moment(candidate, [])

    def test_out_of_season_claim_is_rejected(self):
        candidate = copy.deepcopy(self.moment)
        candidate["date"] = "2026-02-24"
        with self.assertRaises(AliveMomentError):
            validate_alive_moment(candidate, [])

    def test_recent_location_or_species_is_rejected(self):
        history = [{"location": "Moorea", "species": "Megaptera novaeangliae", "category": "marine_life"}]
        with self.assertRaises(AliveMomentError):
            validate_alive_moment(self.moment, history)

    def test_exact_delivered_image_is_rejected_even_if_candidate_metadata_changes(self):
        history = [{"image_source_url": self.moment["image_source_url"]}]
        candidate = copy.deepcopy(self.moment)
        candidate["location"] = "Bora Bora"
        candidate["image_location"] = "Bora Bora, French Polynesia"
        candidate["species"] = "Different species"
        candidate["category"] = "human_life"
        with self.assertRaises(AliveMomentError):
            validate_alive_moment(candidate, history)

    def test_candidate_must_match_the_current_edition_and_date(self):
        with self.assertRaises(AliveMomentError):
            validate_alive_moment(
                self.moment,
                [],
                expected_edition_id="0044",
                expected_date="2026-09-01",
            )


if __name__ == "__main__":
    unittest.main()
