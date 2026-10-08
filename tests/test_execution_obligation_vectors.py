import copy
import json
import unittest
from pathlib import Path

from airtrajectory.execution_obligation import (
    build_execution_obligation_binding,
    validate_execution_obligation_binding,
)


VECTORS = Path(__file__).resolve().parents[1] / "test-vectors" / "execution-obligation-provenance-v0.1.json"


class ExecutionObligationPortableVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(VECTORS.read_text(encoding="utf-8"))

    def test_vectors_replay(self):
        for case in self.payload["cases"]:
            source = case["source"]
            if case["expected"] == "SAME_BINDING":
                a = build_execution_obligation_binding(
                    source_kind=source["kind"],
                    source_identity=source["identity"],
                    source_revision=source["revision"],
                    expected_execution_ids=case["expected_execution_ids_a"],
                )
                b = build_execution_obligation_binding(
                    source_kind=source["kind"],
                    source_identity=source["identity"],
                    source_revision=source["revision"],
                    expected_execution_ids=case["expected_execution_ids_b"],
                )
                self.assertEqual(a["binding_sha256"], b["binding_sha256"], case["id"])
                continue

            binding = build_execution_obligation_binding(
                source_kind=source["kind"],
                source_identity=source["identity"],
                source_revision=source["revision"],
                expected_execution_ids=case["expected_execution_ids"],
            )
            tampered = copy.deepcopy(binding)
            if "expected_execution_ids" in case["tamper"]:
                tampered["expected_execution_ids"] = case["tamper"]["expected_execution_ids"]
            if "source_revision" in case["tamper"]:
                tampered["source"]["revision"] = case["tamper"]["source_revision"]

            with self.assertRaises(ValueError, msg=case["id"]):
                validate_execution_obligation_binding(tampered)


if __name__ == "__main__":
    unittest.main()
