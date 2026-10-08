import unittest

from airtrajectory.execution_obligation import (
    build_execution_obligation_binding,
    reconcile_bound_execution_coverage,
    validate_execution_obligation_binding,
)


def evidence(execution_id):
    return {"execution_id": execution_id}


class ExecutionObligationBindingTests(unittest.TestCase):
    def test_binding_is_order_independent(self):
        a = build_execution_obligation_binding(
            source_kind="selected-test-plan",
            source_identity="suite:window-v1",
            source_revision="sha256:plan-1",
            expected_execution_ids=["exec-b", "exec-a"],
        )
        b = build_execution_obligation_binding(
            source_kind="selected-test-plan",
            source_identity="suite:window-v1",
            source_revision="sha256:plan-1",
            expected_execution_ids=["exec-a", "exec-b"],
        )
        self.assertEqual(a["binding_sha256"], b["binding_sha256"])
        self.assertEqual(a["expected_execution_ids"], ["exec-a", "exec-b"])

    def test_expected_set_tampering_is_detected(self):
        binding = build_execution_obligation_binding(
            source_kind="selected-test-plan",
            source_identity="suite:window-v1",
            source_revision="sha256:plan-1",
            expected_execution_ids=["exec-a", "exec-b"],
        )
        binding["expected_execution_ids"] = ["exec-a"]
        with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
            validate_execution_obligation_binding(binding)

    def test_source_revision_tampering_is_detected(self):
        binding = build_execution_obligation_binding(
            source_kind="selected-test-plan",
            source_identity="suite:window-v1",
            source_revision="sha256:plan-1",
            expected_execution_ids=["exec-a"],
        )
        binding["source"]["revision"] = "sha256:plan-2"
        with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
            validate_execution_obligation_binding(binding)

    def test_bound_reconciliation_preserves_missing_semantics(self):
        binding = build_execution_obligation_binding(
            source_kind="selected-test-plan",
            source_identity="suite:window-v1",
            source_revision="sha256:plan-1",
            expected_execution_ids=["exec-a", "exec-b"],
        )
        result = reconcile_bound_execution_coverage(
            binding,
            [evidence("exec-a")],
        )
        self.assertEqual(result["coverage_status"], "MISSING")
        self.assertEqual(result["missing_execution_ids"], ["exec-b"])
        self.assertEqual(
            result["obligation_binding_sha256"],
            binding["binding_sha256"],
        )
        self.assertEqual(
            result["obligation_source"]["revision"],
            "sha256:plan-1",
        )

    def test_binding_does_not_accept_duplicate_obligations(self):
        with self.assertRaisesRegex(ValueError, "duplicate execution_id"):
            build_execution_obligation_binding(
                source_kind="selected-test-plan",
                source_identity="suite:window-v1",
                source_revision="sha256:plan-1",
                expected_execution_ids=["exec-a", "exec-a"],
            )


if __name__ == "__main__":
    unittest.main()
