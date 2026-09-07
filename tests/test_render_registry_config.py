from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class RenderRegistryContainmentTests(unittest.TestCase):
    def test_all_signal_blueprints_are_registry_required_and_dry_run_contained(self) -> None:
        raw = (ROOT / "render.yaml").read_text(encoding="utf-8")
        config = yaml.safe_load(raw)
        services = config["services"]
        self.assertEqual({"dtl-signal", "dtl-signal-proof"}, {s["name"] for s in services})
        self.assertNotIn("0047", raw)
        self.assertNotIn("SIGNAL_TARGET_RELEASE_ID", raw)
        self.assertNotIn("SIGNAL_EXPECTED_APPROVED_PROOF_SHA256", raw)
        for service in services:
            command = service["startCommand"]
            self.assertIn("--dry-run", command)
            self.assertNotIn("--send", command)
            self.assertNotIn("--deliver-release", command)
            env = {row["key"]: row for row in service["envVars"]}
            self.assertEqual("1", env["SIGNAL_REGISTRY_REQUIRED"]["value"])
            self.assertFalse(env["SIGNAL_REGISTRY_DATABASE_URL"]["sync"])


if __name__ == "__main__":
    unittest.main()
