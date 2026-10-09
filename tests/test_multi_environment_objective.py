"""Objective and multi-environment comparison safety regression suite."""
import copy
import json
import math
import unittest
from pathlib import Path

from airtrajectory.multi_environment_compare import compare_candidate_futures
from airtrajectory.objective import (
    ComfortBand, ObjectiveContract, PollutantGoal, compile_user_goal,
)


FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "multi_environment_conflict_v0.2.json"


def scenario():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def compare(payload):
    return compare_candidate_futures(
        payload["candidates"],
        objective=compile_user_goal(payload["user_goal"]),
        origin_openings=payload["origin_opening_pct"],
    )


class MultiEnvironmentObjectiveTests(unittest.TestCase):
    def test_three_user_goals_compile_to_inspectable_contracts(self):
        goals = [
            "卧室空气太闷。",
            "今天外面 PM2.5 很高，尽量改善 CO₂，但别大量吸进室外污染。",
            "晚上保持空气好一点，但不要太冷。",
        ]
        contracts = [compile_user_goal(goal) for goal in goals]
        self.assertEqual(
            [c.objective_id for c in contracts],
            ["bedroom_stuffy", "co2_vs_outdoor_pm25", "night_fresh_not_cold"],
        )
        self.assertEqual(
            contracts[1].as_dict()["decision_semantics"],
            "hard-constraints-then-lexicographic-priorities",
        )

    def test_tvoc_hcho_are_independent_priorities_with_explicit_units(self):
        obj = ObjectiveContract(
            objective_id="voc-hcho",
            pollutants={
                "tvoc_ug_m3": PollutantGoal("tvoc_ug_m3", target_max=300.0),
                "hcho_mg_m3": PollutantGoal("hcho_mg_m3", target_max=0.08),
            },
            priorities=("hcho_excess", "tvoc_excess", "movement"),
        )
        self.assertEqual(obj.as_dict()["priorities"], ["hcho_excess", "tvoc_excess", "movement"])
        self.assertEqual(obj.as_dict()["pollutants"]["hcho_mg_m3"]["target_max"], 0.08)
        with self.assertRaisesRegex(ValueError, "no declared objective metric"):
            ObjectiveContract(
                objective_id="missing-voc",
                pollutants={"hcho_mg_m3": PollutantGoal("hcho_mg_m3", 0.08)},
                priorities=("tvoc_excess",),
            )

    def test_tvoc_hcho_require_real_supplied_series_not_co2_imputation(self):
        payload = scenario()
        obj = ObjectiveContract(
            objective_id="voc-hcho",
            pollutants={
                "tvoc_ug_m3": PollutantGoal("tvoc_ug_m3", 300.0),
                "hcho_mg_m3": PollutantGoal("hcho_mg_m3", 0.08),
            },
            priorities=("hcho_excess", "tvoc_excess"),
        )
        with self.assertRaisesRegex(ValueError, "lacks tvoc_ug_m3"):
            compare_candidate_futures(
                payload["candidates"],
                objective=obj,
                origin_openings=payload["origin_opening_pct"],
            )

    def test_tvoc_hcho_policy_comparison_uses_matching_priority_keys(self):
        payload = scenario()
        obj = ObjectiveContract(
            objective_id="indoor-chemical",
            pollutants={
                "tvoc_ug_m3": PollutantGoal("tvoc_ug_m3", 300.0),
                "hcho_mg_m3": PollutantGoal("hcho_mg_m3", 0.08),
            },
            priorities=("hcho_excess", "tvoc_excess"),
        )
        for candidate in payload["candidates"]:
            zones = list(candidate["origin"]["co2_ppm"])
            candidate["origin"]["tvoc_ug_m3"] = {zone: 400.0 for zone in zones}
            candidate["origin"]["hcho_mg_m3"] = {zone: 0.10 for zone in zones}
            candidate["series_by_metric"]["tvoc_ug_m3"] = {
                zone: [400.0, 350.0, 250.0] for zone in zones
            }
            candidate["series_by_metric"]["hcho_mg_m3"] = {
                zone: [0.10, 0.09, 0.07] for zone in zones
            }
        report = compare_candidate_futures(
            payload["candidates"], objective=obj,
            origin_openings=payload["origin_opening_pct"],
        )
        self.assertTrue(report["results"])
        for row in report["results"]:
            self.assertIn("hcho_excess", row["metrics"])
            self.assertIn("tvoc_excess", row["metrics"])
        self.assertFalse(report["execution_authorized"])

    def test_unknown_goal_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "do not invent objective weights"):
            compile_user_goal("随便帮我调一下吧")

    def test_high_outdoor_pm25_rejects_large_open_and_preserves_hold(self):
        report = compare(scenario())
        by_label = {row["label"]: row for row in report["results"]}
        self.assertTrue(by_label["HOLD"]["feasible"])
        self.assertFalse(by_label["LARGE_OPEN"]["feasible"])
        self.assertIn(
            "pm25_ug_m3:peak>35", by_label["LARGE_OPEN"]["hard_violations"]
        )
        self.assertEqual(report["recommended"], ["SHORT_CROSSFLOW"])
        self.assertEqual(report["recommendation_basis"], ["co2_excess"])
        self.assertEqual(report["status"], "EXPLORATORY_COMPARISON")
        self.assertFalse(report["execution_authorized"])
        self.assertEqual(
            len({row["origin_sha256"] for row in report["results"]}), 1
        )
        self.assertEqual(report["time_grid_min"], [0, 5, 10])

    def test_mismatched_origin_rejected(self):
        payload = scenario()
        bad = payload["candidates"][1]
        bad["origin"]["co2_ppm"]["living"] = 1500
        bad["series_by_metric"]["co2_ppm"]["living"][0] = 1500
        with self.assertRaisesRegex(ValueError, "same origin"):
            compare(payload)

    def test_mismatched_time_grid_rejected(self):
        payload = scenario()
        payload["candidates"][1]["time_grid_min"] = [0, 4, 10]
        with self.assertRaisesRegex(ValueError, "same time grid"):
            compare(payload)

    def test_incomplete_or_inconsistent_metric_rejected(self):
        payload = scenario()
        payload["candidates"][1]["series_by_metric"]["co2_ppm"]["living"].pop()
        with self.assertRaisesRegex(ValueError, "common time grid"):
            compare(payload)

        payload = scenario()
        payload["candidates"][1]["series_by_metric"]["co2_ppm"]["living"][0] = 100
        with self.assertRaisesRegex(ValueError, "does not start at origin"):
            compare(payload)

        payload = scenario()
        del payload["candidates"][1]["series_by_metric"]["pm25_ug_m3"]
        with self.assertRaisesRegex(ValueError, "lacks pm25_ug_m3"):
            compare(payload)

    def test_nan_and_infinite_consequences_rejected(self):
        for invalid in [float("nan"), float("inf"), float("-inf")]:
            payload = scenario()
            payload["candidates"][1]["series_by_metric"]["pm25_ug_m3"]["living"][1] = invalid
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "finite"):
                    compare(payload)

    def test_missing_duration_and_rain_rejected(self):
        payload = scenario()
        del payload["candidates"][1]["duration_min"]
        with self.assertRaisesRegex(ValueError, "duration_min"):
            compare(payload)
        payload = scenario()
        del payload["candidates"][1]["rain"]
        with self.assertRaisesRegex(ValueError, "rain"):
            compare(payload)

    def test_missing_provenance_or_mixed_backend_rejected(self):
        payload = scenario()
        del payload["candidates"][1]["provenance"]
        with self.assertRaisesRegex(ValueError, "provenance"):
            compare(payload)
        payload = scenario()
        payload["candidates"][1]["provenance"]["backend"] = "claimed-other-backend"
        with self.assertRaisesRegex(ValueError, "incomparable evidence provenance"):
            compare(payload)
        payload = scenario()
        payload["candidates"][1]["provenance"]["engineering_truth"] = True
        with self.assertRaisesRegex(ValueError, "fixture cannot claim"):
            compare(payload)

    def test_duplicate_labels_or_missing_hold_rejected(self):
        payload = scenario()
        payload["candidates"][1]["label"] = "HOLD"
        with self.assertRaisesRegex(ValueError, "unique"):
            compare(payload)
        payload = scenario()
        payload["candidates"][0]["label"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "include simulated HOLD"):
            compare(payload)

    def test_invalid_opening_action_rejected(self):
        for value in [-1, 101, float("nan")]:
            payload = scenario()
            payload["candidates"][1]["actions"][0]["target_pct"] = value
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    compare(payload)

    def test_rain_blocks_opening_but_allows_closing(self):
        payload = scenario()
        for candidate in payload["candidates"]:
            candidate["origin"]["rain"] = True
            candidate["rain"] = True
        report = compare(payload)
        by_label = {row["label"]: row for row in report["results"]}
        self.assertTrue(by_label["HOLD"]["feasible"])
        self.assertFalse(by_label["SHORT_CROSSFLOW"]["feasible"])
        self.assertIn("rain:exterior-window-must-close", by_label["SHORT_CROSSFLOW"]["hard_violations"])
        self.assertEqual(report["recommended"], ["HOLD"])

        # If a window is already open, a rain-triggered closing action is safe.
        payload = scenario()
        for candidate in payload["candidates"]:
            candidate["origin"]["opening_pct"]["W1"] = 50
            candidate["origin"]["rain"] = True
            candidate["rain"] = True
        payload["origin_opening_pct"]["W1"] = 50
        payload["candidates"][0]["actions"][0]["target_pct"] = 50
        payload["candidates"][1]["actions"][0]["target_pct"] = 0
        payload["candidates"][2]["actions"][0]["target_pct"] = 0
        report = compare(payload)
        by_label = {row["label"]: row for row in report["results"]}
        self.assertFalse(by_label["HOLD"]["feasible"])
        self.assertIn(
            "rain:exterior-window-must-close", by_label["HOLD"]["hard_violations"]
        )
        self.assertFalse(by_label["LARGE_OPEN"]["feasible"])  # PM2.5 hard cap
        self.assertTrue(by_label["SHORT_CROSSFLOW"]["feasible"])

    def test_rain_interlock_does_not_block_interior_door(self):
        payload = scenario()
        payload["origin_opening_pct"]["D1"] = 0
        for candidate in payload["candidates"]:
            candidate["origin"]["opening_pct"]["D1"] = 0
            candidate["origin"]["opening_kind"]["D1"] = "door"
            candidate["origin"]["rain"] = True
            candidate["rain"] = True
        short = payload["candidates"][2]
        short["actions"][0]["target_pct"] = 0
        short["actions"].append({"opening_id": "D1", "target_pct": 100})
        report = compare(payload)
        by_label = {row["label"]: row for row in report["results"]}
        self.assertTrue(by_label["SHORT_CROSSFLOW"]["feasible"])
        self.assertEqual(report["recommended"], ["SHORT_CROSSFLOW"])

    def test_missing_opening_type_fails_closed(self):
        payload = scenario()
        del payload["candidates"][1]["origin"]["opening_kind"]
        with self.assertRaisesRegex(ValueError, "opening_kind"):
            compare(payload)

    def test_no_feasible_candidate_is_explicit(self):
        payload = scenario()
        for candidate in payload["candidates"]:
            candidate["origin"]["pm25_ug_m3"]["living"] = 40
            candidate["series_by_metric"]["pm25_ug_m3"]["living"][0] = 40
            candidate["series_by_metric"]["pm25_ug_m3"]["living"][1] = 42
            candidate["series_by_metric"]["pm25_ug_m3"]["living"][2] = 45
        report = compare(payload)
        self.assertEqual(report["status"], "NO_FEASIBLE_CANDIDATE")
        self.assertEqual(report["recommended"], [])
        self.assertFalse(report["execution_authorized"])

    def test_objective_rejects_nonfinite_and_undeclared_priorities(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            PollutantGoal("co2_ppm", math.nan)
        with self.assertRaisesRegex(ValueError, "finite"):
            ComfortBand("temperature_c", math.nan, 26)
        with self.assertRaisesRegex(ValueError, "finite"):
            ObjectiveContract("x", max_intervention_min=float("inf"))
        with self.assertRaisesRegex(ValueError, "no declared objective"):
            ObjectiveContract("x", priorities=("pm25_excess",))


if __name__ == "__main__":
    unittest.main()
