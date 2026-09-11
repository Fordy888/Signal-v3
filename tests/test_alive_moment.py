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

    def test_ai_image_is_rejected(self):
        candidate = copy.deepcopy(self.moment)
        candidate["is_ai_generated"] = True
        with self.assertRaises(AliveMomentError):
            validate_alive_moment(candidate, [])

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


if __name__ == "__main__":
    unittest.main()
