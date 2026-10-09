from pathlib import Path
import copy
import json
import unittest

from airtrajectory.layout import LayoutContract
from airtrajectory.policy_benchmark import (
    build_policy_benchmark_report,
    build_required_benchmark_candidates,
    verify_policy_benchmark_report,
)


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"
CASE = ROOT / "examples" / "golden_case.multispace_joint_v1.json"


class PolicyBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.topology = LayoutContract.from_file(LAYOUT).to_building_topology()
        self.case = json.loads(CASE.read_text(encoding="utf-8"))

    def test_required_candidates_include_hold_independent_and_joint(self):
        rows = build_required_benchmark_candidates(self.case, self.topology)
        labels = [row["label"] for row in rows]

        self.assertEqual(labels[0], "HOLD")
        self.assertEqual(labels[1], "INDEPENDENT")
        self.assertTrue(any(label.startswith("JOINT:") for label in labels))

        hold = rows[0]
        hold_targets = {
            action["opening_id"]: action["target_pct"]
            for action in hold["actions"]
        }
        self.assertEqual(
            hold_targets,
            {"W1": 65.0, "W2": 35.0, "W3": 55.0},
        )

    def test_report_is_multi_metric_and_not_scalar_only(self):
        response = {
            "branches": [
                {
                    "label": "HOLD",
                    "actions": [
                        {"kind": "opening", "opening_id": "W1", "target_pct": 65},
                        {"kind": "opening", "opening_id": "W2", "target_pct": 35},
                        {"kind": "opening", "opening_id": "W3", "target_pct": 55},
                    ],
                    "co2_series_by_zone": {
                        "living": [1380, 1360, 1340],
                        "bedroom": [900, 900, 900],
                        "study": [800, 800, 800],
                    },
                    "return": -3.0,
                },
                {
                    "label": "INDEPENDENT",
                    "actions": [
                        {"kind": "opening", "opening_id": "W1", "target_pct": 75},
                        {"kind": "opening", "opening_id": "W2", "target_pct": 35},
                        {"kind": "opening", "opening_id": "W3", "target_pct": 55},
                    ],
                    "co2_series_by_zone": {
                        "living": [1300, 1200, 1100],
                        "bedroom": [900, 900, 900],
                        "study": [800, 800, 800],
                    },
                    "return": -2.0,
                },
                {
                    "label": "JOINT:path-a",
                    "actions": [
                        {"kind": "opening", "opening_id": "W1", "target_pct": 55},
                        {"kind": "opening", "opening_id": "W2", "target_pct": 0},
                        {"kind": "opening", "opening_id": "W3", "target_pct": 55},
                    ],
                    "co2_series_by_zone": {
                        "living": [1250, 1050, 950],
                        "bedroom": [900, 880, 860],
                        "study": [800, 820, 830],
                    },
                    "return": -1.0,
                },
            ]
        }

        report = build_policy_benchmark_report(
            response=response,
            case=self.case,
            topology=self.topology,
        )

        self.assertTrue(verify_policy_benchmark_report(
            report=report, response=response, case=self.case, topology=self.topology,
        ))
        modified = copy.deepcopy(report)
        modified["results"][-1]["metrics"]["peak_co2_ppm"] = 0
        with self.assertRaisesRegex(ValueError, "independently rescored"):
            verify_policy_benchmark_report(
                report=modified, response=response, case=self.case, topology=self.topology,
            )
        self.assertEqual(report["benchmark"], "airtrajectory-policy-benchmark-v0.1")
        self.assertEqual(
            report["required_baselines"],
            ["HOLD", "INDEPENDENT", "JOINT"],
        )
        self.assertIn("JOINT:path-a", report["pareto_frontier"])
        joint = next(
            row for row in report["results"] if row["label"] == "JOINT:path-a"
        )
        self.assertIn("mean_co2_auc_ppm_s", joint["metrics"])
        self.assertIn("peak_co2_ppm", joint["metrics"])
        self.assertIn("zone_seconds_above_threshold", joint["metrics"])
        self.assertIn("actuator_movement_pct_sum", joint["metrics"])
        self.assertEqual(
            joint["metric_availability"]["prediction_error"],
            "unavailable",
        )
        self.assertEqual(
            report["ranking_policy"],
            "none; inspect metrics and Pareto frontier",
        )
        self.assertEqual(
            report["metric_parameters"]["iaq_threshold_ppm_by_zone"],
            {"bedroom": 1000.0, "living": 1000.0, "study": 1000.0},
        )
        self.assertEqual(
            report["metric_parameters"]["trajectory_integral"],
            "trapezoidal-origin-plus-rollout",
        )
        self.assertEqual(
            report["metric_parameters"]["threshold_duration"],
            "discrete-sample-hold-post-step",
        )

    def test_report_rejects_missing_hold(self):
        response = {
            "branches": [
                {
                    "label": "INDEPENDENT",
                    "actions": [],
                    "co2_series_by_zone": {
                        "living": [1000],
                        "bedroom": [900],
                        "study": [800],
                    },
                },
                {
                    "label": "JOINT:x",
                    "actions": [],
                    "co2_series_by_zone": {
                        "living": [900],
                        "bedroom": [900],
                        "study": [800],
                    },
                },
            ]
        }
        with self.assertRaisesRegex(ValueError, "HOLD"):
            build_policy_benchmark_report(
                response=response,
                case=self.case,
                topology=self.topology,
            )


if __name__ == "__main__":
    unittest.main()
