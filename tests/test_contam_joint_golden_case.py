import json
import unittest
from pathlib import Path

from airtrajectory.contam_joint_golden_case import (
    build_strategy_candidates,
    compare_independent_vs_joint,
    independent_action_vector,
    normalize_golden_case,
    score_strategy_branch,
)
from airtrajectory.layout import LayoutContract


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"
CASE = ROOT / "examples" / "golden_case.multispace_joint_v1.json"


def load_case():
    return json.loads(CASE.read_text(encoding="utf-8"))


def branch(label, actions, series):
    zones = sorted(series)
    steps = len(next(iter(series.values())))
    return {
        "label": label,
        "actions": [
            {
                "kind": "opening",
                "opening_id": opening_id,
                "target_pct": float(target),
            }
            for opening_id, target in sorted(actions.items())
        ],
        "end_co2_ppm_by_zone": {
            zone: float(series[zone][-1]) for zone in zones
        },
        "co2_series_by_zone": {
            zone: [float(v) for v in series[zone]]
            for zone in zones
        },
        "opening_pct_series": [
            {opening_id: float(target) for opening_id, target in sorted(actions.items())}
            for _ in range(steps)
        ],
    }


class ContamJointGoldenCaseTests(unittest.TestCase):
    def setUp(self):
        self.layout = LayoutContract.from_file(LAYOUT)
        self.topology = self.layout.to_building_topology()
        self.case = load_case()

    def test_case_matches_fixed_topology_and_expected_real_origin(self):
        normalized = normalize_golden_case(self.case, self.topology)
        self.assertEqual(
            normalized["topology_id"],
            "demo.fixed-three-room.v1",
        )
        self.assertEqual(
            normalized["origin"]["co2_ppm"],
            {"bedroom": 900.0, "living": 1400.0, "study": 800.0},
        )
        self.assertEqual(
            normalized["origin"]["opening_pct"],
            {"D1": 100.0, "D2": 100.0, "W1": 65.0, "W2": 35.0, "W3": 55.0},
        )
        self.assertEqual(normalized["time_step_s"], 60)
        self.assertEqual(normalized["horizon_steps"], 3)
        self.assertFalse(normalized["engineering_truth"])
        self.assertEqual(len(normalized["golden_case_sha256"]), 64)

    def test_independent_baseline_is_derived_from_existing_rule(self):
        actions = independent_action_vector(self.case, self.topology)
        self.assertEqual(
            actions,
            {"W1": 75.0, "W2": 35.0, "W3": 0.0},
        )
        candidates = build_strategy_candidates(self.case, self.topology)
        self.assertEqual(candidates[0]["label"], "independent-reference")
        self.assertEqual(
            {
                item["opening_id"]: item["target_pct"]
                for item in candidates[0]["actions"]
            },
            actions,
        )

    def test_branch_scoring_uses_all_zone_series_and_movement(self):
        row = score_strategy_branch(
            branch(
                "candidate",
                {"W1": 75, "W2": 35, "W3": 0},
                {
                    "living": [1300, 1220, 1140],
                    "bedroom": [910, 900, 890],
                    "study": [810, 805, 800],
                },
            ),
            case=self.case,
            topology=self.topology,
        )
        self.assertEqual(row["metrics"]["high_co2_zone_steps"], 2)
        self.assertEqual(row["metrics"]["movement_pct_sum"], 65.0)
        self.assertGreater(row["metrics"]["mean_room_imbalance_ppm"], 0)
        self.assertGreater(row["objective_score"], 0)

    def test_joint_win_is_reported_when_global_objective_improves(self):
        independent_actions = {"W1": 75, "W2": 35, "W3": 0}
        joint_actions = {"W1": 75, "W2": 55, "W3": 55}
        response = {
            "branches": [
                branch(
                    "independent-reference",
                    independent_actions,
                    {
                        "living": [1320, 1260, 1210],
                        "bedroom": [920, 915, 910],
                        "study": [810, 805, 800],
                    },
                ),
                branch(
                    "joint-balanced-high",
                    joint_actions,
                    {
                        "living": [1240, 1150, 1060],
                        "bedroom": [900, 870, 840],
                        "study": [790, 760, 735],
                    },
                ),
            ]
        }
        receipt = compare_independent_vs_joint(
            response=response,
            case=self.case,
            topology=self.topology,
            prj_sha256="a" * 64,
        )
        self.assertEqual(receipt["joint_vs_independent_outcome"], "WIN")
        self.assertEqual(receipt["selected"]["label"], "joint-balanced-high")
        self.assertTrue(receipt["non_regression"])
        self.assertGreater(receipt["objective_improvement"], 0)
        self.assertEqual(len(receipt["comparison_sha256"]), 64)

    def test_tie_is_not_relabelled_as_joint_win(self):
        actions = {"W1": 75, "W2": 35, "W3": 0}
        series = {
            "living": [1200, 1150, 1100],
            "bedroom": [900, 890, 880],
            "study": [800, 790, 780],
        }
        response = {
            "branches": [
                branch("independent-reference", actions, series),
                branch("joint-copy", actions, series),
            ]
        }
        receipt = compare_independent_vs_joint(
            response=response,
            case=self.case,
            topology=self.topology,
        )
        self.assertEqual(receipt["joint_vs_independent_outcome"], "TIE")
        self.assertEqual(receipt["selected"]["label"], "independent-reference")
        self.assertEqual(receipt["objective_improvement"], 0.0)
        self.assertTrue(receipt["non_regression"])

    def test_incomplete_zone_series_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "complete co2_series_by_zone"):
            score_strategy_branch(
                {
                    "label": "bad",
                    "actions": [
                        {"kind": "opening", "opening_id": "W1", "target_pct": 75},
                        {"kind": "opening", "opening_id": "W2", "target_pct": 35},
                        {"kind": "opening", "opening_id": "W3", "target_pct": 0},
                    ],
                    "co2_series_by_zone": {
                        "living": [1200, 1100, 1000],
                    },
                },
                case=self.case,
                topology=self.topology,
            )


if __name__ == "__main__":
    unittest.main()
