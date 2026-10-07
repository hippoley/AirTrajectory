"""Counterexample: membership integrity is not claim completeness.

This test intentionally demonstrates the current boundary of ExecutionEvidenceSet v0.1.
Both manifests are internally valid, even though one selectively omits a failing
execution before the set is built.
"""
import unittest

from airtrajectory.execution_evidence_set import (
    build_execution_evidence_set,
    validate_execution_evidence_set,
)


def record(execution_id, result):
    return {
        "schema_version": "0.1",
        "record_type": "execution-evidence-envelope-v0.1",
        "execution_id": execution_id,
        "parent_execution_id": None,
        "subject": {"kind": "case", "identity": execution_id, "version": "0.1"},
        "target": {"kind": "device", "identity": "device-1", "scope": None},
        "operation": {
            "kind": "test",
            "request_id": None,
            "ack_id": None,
            "mutation_expected": False,
            "parameters": {},
        },
        "harness_status": "COMPLETED",
        "result": result,
        "reason_code": None,
        "observations": [],
        "recovery": {
            "required": False,
            "performed": False,
            "status": "NOT_REQUIRED",
            "evidence_refs": [],
        },
        "verification": {
            "performed": result == "PASS",
            "status": "PASS" if result == "PASS" else "NOT_PERFORMED",
            "verifier": "fixture" if result == "PASS" else None,
            "evidence_refs": [],
        },
        "provenance": {},
        "artifact_refs": [],
        "evidence_boundary": "counterexample fixture",
        "extensions": {},
    }


class ClaimCompletenessCounterexampleTests(unittest.TestCase):
    def test_valid_manifest_can_still_omit_a_failing_execution(self):
        passing = record("exec-a", "PASS")
        failing = record("exec-b", "FAIL")

        complete = build_execution_evidence_set(
            [passing, failing],
            suite_id="suite-1",
        )
        selectively_omitted = build_execution_evidence_set(
            [passing],
            suite_id="suite-1",
        )

        # Both manifests are internally well-formed and tamper-evident.
        validate_execution_evidence_set(complete)
        validate_execution_evidence_set(selectively_omitted)

        # But they make different aggregate claims because v0.1 does not bind
        # the evidence set to an independently committed expected execution plan.
        self.assertEqual(complete["aggregate_result"], "FAIL")
        self.assertEqual(selectively_omitted["aggregate_result"], "PASS")
        self.assertNotEqual(
            complete["manifest_sha256"],
            selectively_omitted["manifest_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
