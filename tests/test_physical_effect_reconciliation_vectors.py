import json
from pathlib import Path
import unittest

from airtrajectory.physical_effect_reconciliation import reconcile_physical_effect


ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "test-vectors" / "physical-effect-reconciliation-v0.1.json"


class PhysicalEffectReconciliationVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(VECTORS.read_text(encoding="utf-8"))

    def test_portable_vectors_match_runtime_reconciliation(self):
        for case in self.payload["cases"]:
            with self.subTest(case=case["id"]):
                result = reconcile_physical_effect(
                    logical_effect_id=case["id"],
                    intended_target_pct=case["target_pct"],
                    observation=case["observation"],
                    tolerance_pct=1.0,
                )
                self.assertEqual(result["status"], case["expected"])
                self.assertEqual(result["reason"], case["expected_reason"])


if __name__ == "__main__":
    unittest.main()
