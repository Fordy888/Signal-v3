import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.alive_moment import AliveMomentError, resolve_alive_moment_path, validate_alive_moment, verify_alive_moment_asset


ROOT = Path(__file__).resolve().parents[1]


class AliveMomentTests(unittest.TestCase):
    def setUp(self):
        self.moment = json.loads((ROOT / "data" / "fixtures" / "alive_moment_0038.json").read_text())

    def test_valid_real_licensed_seasonal_moment_passes(self):
        self.assertEqual(validate_alive_moment(self.moment, []), self.moment)

    def test_edition_0047_featured_picture_passes_against_prior_quang_phu_cau(self):
        candidate = json.loads(
            (ROOT / "data" / "fixtures" / "alive_moment_0047.json").read_text()
        )
        previous = json.loads(
            (ROOT / "data" / "fixtures" / "alive_moment_0046.json").read_text()
        )
        self.assertEqual(
            validate_alive_moment(
                candidate,
                [previous],
                expected_edition_id="0047",
                expected_date="2026-09-04",
            ),
            candidate,
        )

    def test_edition_0048_public_domain_welders_pass_against_recent_images(self):
        candidate = json.loads(
            (ROOT / "data" / "fixtures" / "alive_moment_0048.json").read_text()
        )
        history = [
            json.loads((ROOT / "data" / "fixtures" / name).read_text())
            for name in ("alive_moment_0046.json", "alive_moment_0047.json")
        ]

        self.assertEqual(
            validate_alive_moment(
                candidate,
                history,
                expected_edition_id="0048",
                expected_date="2026-09-07",
            ),
            candidate,
        )
        self.assertEqual(candidate["licence_type"], "PUBLIC DOMAIN")
        self.assertEqual(candidate["dominant_colour_family"], "neutral")
        self.assertFalse(candidate["is_ai_generated"])

    def test_edition_0049_public_domain_reef_passes_against_recent_images(self):
        candidate = json.loads(
            (ROOT / "data" / "alive_moments" / "2026-09-08.json").read_text()
        )
        history = [
            json.loads((ROOT / "data" / "fixtures" / name).read_text())
            for name in (
                "alive_moment_0046.json",
                "alive_moment_0047.json",
                "alive_moment_0048.json",
            )
        ]
        self.assertEqual(
            validate_alive_moment(
                candidate,
                history,
                expected_edition_id="0049",
                expected_date="2026-09-08",
            ),
            candidate,
        )
        self.assertEqual("PUBLIC DOMAIN", candidate["licence_type"])
        self.assertEqual("aqua", candidate["dominant_colour_family"])
        self.assertFalse(candidate["is_ai_generated"])

    def test_hosted_image_bytes_must_match_governed_checksum(self):
        payload = b"verified-image-bytes"
        moment = {
            "image_url": "https://images.example.com/verified.jpg",
            "image_sha256": hashlib.sha256(payload).hexdigest(),
        }
        response = Mock(
            content=payload,
            headers={"Content-Type": "image/jpeg"},
        )
        response.raise_for_status.return_value = None
        fetch = Mock(return_value=response)
        result = verify_alive_moment_asset(moment, fetch=fetch)
        self.assertEqual(moment["image_sha256"], result["sha256"])
        self.assertEqual(len(payload), result["bytes"])
        fetch.assert_called_once_with(moment["image_url"], timeout=20)

    def test_hosted_image_substitution_is_rejected(self):
        response = Mock(
            content=b"substituted-image-bytes",
            headers={"Content-Type": "image/jpeg"},
        )
        response.raise_for_status.return_value = None
        with self.assertRaises(AliveMomentError):
            verify_alive_moment_asset(
                {
                    "image_url": "https://images.example.com/verified.jpg",
                    "image_sha256": "0" * 64,
                },
                fetch=Mock(return_value=response),
            )

    def test_daily_path_template_resolves_by_edition_date(self):
        self.assertEqual(
            resolve_alive_moment_path(
                ROOT,
                "data/alive_moments/{date}.json",
                edition_id="0047",
                edition_date="2026-09-04",
            ),
            ROOT / "data" / "alive_moments" / "2026-09-04.json",
        )

    def test_invalid_daily_path_template_is_rejected(self):
        with self.assertRaises(AliveMomentError):
            resolve_alive_moment_path(
                ROOT,
                "data/alive_moments/{unknown}.json",
                edition_id="0047",
                edition_date="2026-09-04",
            )

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
