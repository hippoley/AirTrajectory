"""Cross-component offline replay test for the real-CONTAM benchmark artifact format."""
import copy
import unittest
from pathlib import Path

from airtrajectory.layout import LayoutContract
from airtrajectory.policy_benchmark import build_policy_benchmark_report
from examples.verify_contam_benchmark_artifact import verify_artifact

ROOT = Path(__file__).resolve().parents[1]


class BenchmarkArtifactReplayTests(unittest.TestCase):
    def setUp(self):
        import json
        self.layout = LayoutContract.from_file(ROOT / "web/data/home_topology.fixed.json")
        self.case = json.loads((ROOT / "examples/golden_case.multispace_joint_v1.json").read_text())
        self.actions = [
            {"kind": "opening", "opening_id": opening_id, "target_pct": pct}
            for opening_id, pct in (("W1", 65), ("W2", 35), ("W3", 55))
        ]
        common = {"living": [1350, 1300, 1250], "bedroom": [900, 890, 880], "study": [800, 790, 780]}
        self.branches = [
            {"label": label, "actions": copy.deepcopy(self.actions),
             "co2_series_by_zone": copy.deepcopy(common)}
            for label in ("HOLD", "INDEPENDENT", "JOINT:baseline")
        ]
        report = build_policy_benchmark_report(
            response={"branches": self.branches}, case=self.case,
            topology=self.layout.to_building_topology(),
        )
        self.artifact = {
            "marker": "REAL_CONTAM_JOINT_GOLDEN_CASE_EXECUTED",
            "golden_case": self.case,
            "trusted_for_promotion": False,
            "policy_benchmark": report,
            "branches": self.branches,
        }

    def test_offline_artifact_replay_passes_semantic_consistency(self):
        result = verify_artifact(self.artifact, self.layout)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["branches_verified"], 3)

    def test_modified_score_rejected_without_running_solver(self):
        bad = copy.deepcopy(self.artifact)
        bad["policy_benchmark"]["results"][0]["metrics"]["peak_co2_ppm"] = 0
        with self.assertRaisesRegex(ValueError, "independently rescored"):
            verify_artifact(bad, self.layout)

    def test_missing_solver_series_and_physical_promotion_rejected(self):
        bad = copy.deepcopy(self.artifact)
        del bad["branches"][0]["co2_series_by_zone"]
        with self.assertRaises(ValueError):
            verify_artifact(bad, self.layout)
        bad = copy.deepcopy(self.artifact)
        bad["trusted_for_promotion"] = True
        with self.assertRaisesRegex(ValueError, "physical promotion"):
            verify_artifact(bad, self.layout)


if __name__ == "__main__":
    unittest.main()
