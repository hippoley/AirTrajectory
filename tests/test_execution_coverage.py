import unittest

from airtrajectory.execution_coverage import reconcile_execution_coverage


def evidence(execution_id):
    return {"execution_id": execution_id}


class ExecutionCoverageTests(unittest.TestCase):
    def test_complete_coverage(self):
        result = reconcile_execution_coverage(
            ["exec-a", "exec-b"],
            [evidence("exec-b"), evidence("exec-a")],
        )
        self.assertEqual(result["coverage_status"], "COMPLETE")
        self.assertEqual(result["missing_execution_ids"], [])
        self.assertEqual(result["unexpected_execution_ids"], [])

    def test_missing_execution_is_not_not_evaluated(self):
        result = reconcile_execution_coverage(
            ["exec-a", "exec-b"],
            [evidence("exec-a")],
        )
        self.assertEqual(result["coverage_status"], "MISSING")
        self.assertEqual(result["missing_execution_ids"], ["exec-b"])

    def test_unexpected_execution_is_reported(self):
        result = reconcile_execution_coverage(
            ["exec-a"],
            [evidence("exec-a"), evidence("exec-x")],
        )
        self.assertEqual(result["coverage_status"], "UNEXPECTED")
        self.assertEqual(result["unexpected_execution_ids"], ["exec-x"])

    def test_missing_dominates_unexpected(self):
        result = reconcile_execution_coverage(
            ["exec-a", "exec-b"],
            [evidence("exec-a"), evidence("exec-x")],
        )
        self.assertEqual(result["coverage_status"], "MISSING")
        self.assertEqual(result["missing_execution_ids"], ["exec-b"])
        self.assertEqual(result["unexpected_execution_ids"], ["exec-x"])

    def test_duplicate_expected_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate execution_id"):
            reconcile_execution_coverage(
                ["exec-a", "exec-a"],
                [evidence("exec-a")],
            )


if __name__ == "__main__":
    unittest.main()
