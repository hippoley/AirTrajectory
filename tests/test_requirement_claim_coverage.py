import unittest

from airtrajectory.requirement_claim_coverage import (
    reconcile_requirement_claim_coverage,
)


def claim(cr_id, outcome):
    return {"cr_id": cr_id, "outcome": outcome}


class RequirementClaimCoverageTests(unittest.TestCase):
    def test_complete_when_every_expected_requirement_has_an_explicit_outcome(self):
        result = reconcile_requirement_claim_coverage(
            ["MARGO-APP-APPDESC-001", "MARGO-APP-REG-002"],
            [
                claim("MARGO-APP-REG-002", "NOT_SATISFIED"),
                claim("MARGO-APP-APPDESC-001", "SATISFIED"),
            ],
        )
        self.assertEqual(result["coverage_status"], "COMPLETE")
        self.assertEqual(result["missing_cr_ids"], [])

    def test_unsatisfied_is_not_missing_when_explicitly_reported(self):
        result = reconcile_requirement_claim_coverage(
            ["MARGO-DEV-MGMT-001"],
            [claim("MARGO-DEV-MGMT-001", "NOT_SATISFIED")],
        )
        self.assertEqual(result["coverage_status"], "COMPLETE")

    def test_omitted_requirement_is_missing(self):
        result = reconcile_requirement_claim_coverage(
            ["MARGO-WFM-MGMT-001", "MARGO-WFM-MGMT-002"],
            [claim("MARGO-WFM-MGMT-001", "SATISFIED")],
        )
        self.assertEqual(result["coverage_status"], "MISSING")
        self.assertEqual(result["missing_cr_ids"], ["MARGO-WFM-MGMT-002"])

    def test_claim_without_outcome_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "explicit outcome"):
            reconcile_requirement_claim_coverage(
                ["MARGO-APP-APPDESC-001"],
                [{"cr_id": "MARGO-APP-APPDESC-001"}],
            )

    def test_unexpected_requirement_is_reported(self):
        result = reconcile_requirement_claim_coverage(
            ["MARGO-APP-APPDESC-001"],
            [
                claim("MARGO-APP-APPDESC-001", "SATISFIED"),
                claim("MARGO-APP-REG-999", "SATISFIED"),
            ],
        )
        self.assertEqual(result["coverage_status"], "UNEXPECTED")
        self.assertEqual(result["unexpected_cr_ids"], ["MARGO-APP-REG-999"])


if __name__ == "__main__":
    unittest.main()
