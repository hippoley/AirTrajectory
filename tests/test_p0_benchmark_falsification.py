"""P0 benchmark falsification: never certify incomparable or fabricated branches."""
import copy
import json
from pathlib import Path
import unittest

from airtrajectory.layout import LayoutContract
from airtrajectory.policy_benchmark import (
    build_policy_benchmark_report, build_required_benchmark_candidates,
)

ROOT = Path(__file__).resolve().parents[1]


class BenchmarkFailClosedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.topology = LayoutContract.from_file(
            ROOT / "web/data/home_topology.fixed.json"
        ).to_building_topology()
        cls.case = json.loads(
            (ROOT / "examples/golden_case.multispace_joint_v1.json").read_text()
        )

    def response(self):
        rows = build_required_benchmark_candidates(self.case, self.topology)
        return {"branches": [
            {
                "label": row["label"],
                "actions": [
                    {"kind": "opening", **action} for action in row["actions"]
                ],
                "co2_series_by_zone": {
                    "living": [1380, 1350, 1320],
                    "bedroom": [900, 890, 880],
                    "study": [800, 790, 780],
                },
            }
            for row in rows
        ]}

    def evaluate(self, response):
        return build_policy_benchmark_report(
            response=response, case=self.case, topology=self.topology,
        )

    def test_good_same_origin_hold_is_scored(self):
        report = self.evaluate(self.response())
        self.assertTrue(report["same_origin"])
        self.assertTrue(report["same_horizon"])
        self.assertEqual(report["horizon_steps"], 3)
        self.assertEqual(
            next(x for x in report["results"] if x["label"]=="HOLD")
            ["metrics"]["actuator_movement_pct_sum"], 0,
        )

    def test_duplicate_policy_labels_rejected(self):
        response = self.response()
        response["branches"].append(copy.deepcopy(response["branches"][0]))
        with self.assertRaisesRegex(ValueError, "unique"):
            self.evaluate(response)

    def test_fabricated_hold_action_rejected(self):
        response = self.response()
        response["branches"][0]["actions"][0]["target_pct"] = 100
        with self.assertRaisesRegex(ValueError, "HOLD cannot change"):
            self.evaluate(response)

    def test_missing_hold_opening_rejected(self):
        response = self.response()
        response["branches"][0]["actions"].pop()
        with self.assertRaisesRegex(ValueError, "cover all exterior"):
            self.evaluate(response)

    def test_mismatched_horizon_rejected(self):
        response = self.response()
        response["branches"][1]["co2_series_by_zone"]["living"].pop()
        with self.assertRaisesRegex(ValueError, "horizon"):
            self.evaluate(response)

    def test_nonfinite_or_negative_co2_rejected(self):
        for invalid in [float("nan"), float("inf"), -1]:
            with self.subTest(invalid=invalid):
                response = self.response()
                response["branches"][1]["co2_series_by_zone"]["living"][1] = invalid
                with self.assertRaisesRegex(ValueError, "CO2"):
                    self.evaluate(response)

    def test_nonfinite_opening_target_rejected(self):
        response = self.response()
        response["branches"][1]["actions"][0]["target_pct"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite numeric"):
            self.evaluate(response)


if __name__ == "__main__":
    unittest.main()
