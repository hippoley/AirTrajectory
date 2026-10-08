import copy
import json
from pathlib import Path
import unittest

from airtrajectory.execution_coverage import reconcile_execution_coverage
from airtrajectory.requirement_claim_coverage import reconcile_requirement_claim_coverage


ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "test-vectors" / "model-substitution-independence-v0.1.json"
MOCK = ROOT / "web" / "data" / "mock_physical_fallback.json"


class ModelSubstitutionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(VECTORS.read_text(encoding="utf-8"))

    def test_structural_verdicts_ignore_model_identity_and_narrative(self):
        for case in self.payload["cases"]:
            if case["kind"] == "execution_coverage":
                verdicts = []
                for variant in case["variants"]:
                    result = reconcile_execution_coverage(
                        case["expected_execution_ids"],
                        variant["records"],
                    )
                    verdicts.append(result)
                    self.assertEqual(result["coverage_status"], case["expected_status"])
                    if "expected_missing" in case:
                        self.assertEqual(
                            result["missing_execution_ids"],
                            case["expected_missing"],
                        )
                self.assertEqual(
                    [v["coverage_status"] for v in verdicts],
                    [case["expected_status"]] * len(verdicts),
                )

            elif case["kind"] == "requirement_claim_coverage":
                verdicts = []
                for variant in case["variants"]:
                    result = reconcile_requirement_claim_coverage(
                        case["expected_cr_ids"],
                        variant["claims"],
                    )
                    verdicts.append(result)
                    self.assertEqual(result["coverage_status"], case["expected_status"])
                self.assertEqual(
                    [v["coverage_status"] for v in verdicts],
                    [case["expected_status"]] * len(verdicts),
                )

    def test_untrusted_model_claim_cannot_promote_mock_to_physical_evidence(self):
        mock = json.loads(MOCK.read_text(encoding="utf-8"))
        case = next(
            item for item in self.payload["cases"]
            if item["kind"] == "physical_evidence_boundary"
        )

        mutated = copy.deepcopy(mock)
        mutated["model_assertion"] = case["untrusted_model_assertion"]

        self.assertIs(mutated["provenance"]["physical_evidence"], False)
        self.assertIs(mutated["provenance"]["engineering_truth"], False)
        self.assertTrue(
            all(step["evidence_class"] == "tau_sim" for step in mutated["trajectory"])
        )
        self.assertTrue(
            all(
                step["actuator_feedback"]["measured_position_pct"] is None
                for step in mutated["trajectory"]
            )
        )


if __name__ == "__main__":
    unittest.main()
