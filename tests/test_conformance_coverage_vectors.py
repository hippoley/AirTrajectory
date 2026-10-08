import json
from pathlib import Path
import unittest

from airtrajectory.execution_coverage import reconcile_execution_coverage
from airtrajectory.requirement_claim_coverage import (
    reconcile_requirement_claim_coverage,
)


VECTORS = Path(__file__).resolve().parents[1] / "test-vectors" / "conformance-coverage-v0.1.json"


class ConformanceCoverageVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(VECTORS.read_text(encoding="utf-8"))

    def test_all_vectors_match_frozen_semantics(self):
        for vector in self.payload["vectors"]:
            with self.subTest(vector=vector["id"]):
                if vector["kind"] == "execution_coverage":
                    observed = [
                        {"execution_id": execution_id}
                        for execution_id in vector["observed_execution_ids"]
                    ]
                    result = reconcile_execution_coverage(
                        vector["expected_execution_ids"],
                        observed,
                    )
                    self.assertEqual(result["coverage_status"], vector["expected_status"])
                    if "expected_missing" in vector:
                        self.assertEqual(
                            result["missing_execution_ids"],
                            vector["expected_missing"],
                        )
                    if "expected_unexpected" in vector:
                        self.assertEqual(
                            result["unexpected_execution_ids"],
                            vector["expected_unexpected"],
                        )
                elif vector["kind"] == "requirement_claim_coverage":
                    result = reconcile_requirement_claim_coverage(
                        vector["expected_cr_ids"],
                        vector["claims"],
                    )
                    self.assertEqual(result["coverage_status"], vector["expected_status"])
                    if "expected_missing" in vector:
                        self.assertEqual(result["missing_cr_ids"], vector["expected_missing"])
                else:
                    self.fail(f"unsupported vector kind: {vector['kind']}")


if __name__ == "__main__":
    unittest.main()
