import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "adapters" / "modelica-buildings-v0.1.json"


class ModelicaBuildingsCapabilityTests(unittest.TestCase):
    def test_operable_door_is_supported_but_exterior_window_fails_closed(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        supported = manifest["supported_semantics"]

        self.assertEqual(supported["internal_door"]["status"], "supported")
        self.assertIn(
            "Buildings.Airflow.Multizone.DoorOperable",
            supported["internal_door"]["preferred_models"],
        )
        self.assertEqual(
            supported["internal_door"]["opening_signal"],
            "y in [0,1]",
        )

        self.assertEqual(
            supported["exterior_window"]["status"],
            "unresolved",
        )
        self.assertEqual(
            supported["exterior_window"]["preferred_models"],
            [],
        )
        rules = "\n".join(manifest["fail_closed_rules"])
        self.assertIn("do not compile an exterior window path", rules)

    def test_manifest_does_not_claim_simulation_execution(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertIn("no Modelica simulation", manifest["evidence_boundary"])


if __name__ == "__main__":
    unittest.main()
