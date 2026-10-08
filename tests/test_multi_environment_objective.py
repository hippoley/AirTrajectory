import unittest

from airtrajectory.multi_environment_compare import compare_candidate_futures
from airtrajectory.objective import compile_user_goal


def candidate(
    label,
    *,
    co2,
    pm25,
    temp,
    rh,
    target,
    duration,
):
    return {
        "label": label,
        "series_by_metric": {
            "co2_ppm": {"living": co2},
            "pm25_ug_m3": {"living": pm25},
            "temperature_c": {"living": temp},
            "relative_humidity_pct": {"living": rh},
        },
        "actions": [{"opening_id": "W1", "target_pct": target}],
        "duration_min": duration,
        "rain": False,
        "provenance": {"kind": "fixture", "engineering_truth": False},
    }


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
            [
                "bedroom_stuffy",
                "co2_vs_outdoor_pm25",
                "night_fresh_not_cold",
            ],
        )
        self.assertEqual(
            contracts[1].as_dict()["decision_semantics"],
            "hard-constraints-then-lexicographic-priorities",
        )

    def test_unknown_goal_fails_closed_instead_of_inventing_weights(self):
        with self.assertRaisesRegex(ValueError, "do not invent objective weights"):
            compile_user_goal("随便帮我调一下吧")

    def test_high_outdoor_pm25_makes_large_opening_infeasible(self):
        objective = compile_user_goal(
            "今天外面 PM2.5 很高，尽量改善 CO₂，但别大量吸进室外污染。"
        )
        candidates = [
            candidate(
                "HOLD",
                co2=[1450, 1440, 1430],
                pm25=[18, 18, 18],
                temp=[22, 22, 22],
                rh=[52, 52, 52],
                target=0,
                duration=10,
            ),
            candidate(
                "LARGE_OPEN",
                co2=[1200, 900, 760],
                pm25=[28, 41, 58],
                temp=[20, 17.5, 16],
                rh=[52, 50, 48],
                target=80,
                duration=10,
            ),
            candidate(
                "SHORT_CROSSFLOW",
                co2=[1320, 1120, 980],
                pm25=[20, 24, 29],
                temp=[21.5, 20.8, 20.3],
                rh=[52, 51, 50],
                target=25,
                duration=5,
            ),
        ]

        report = compare_candidate_futures(
            candidates,
            objective=objective,
            origin_openings={"W1": 0.0},
        )

        by_label = {row["label"]: row for row in report["results"]}
        self.assertTrue(by_label["HOLD"]["feasible"])
        self.assertFalse(by_label["LARGE_OPEN"]["feasible"])
        self.assertIn(
            "pm25_ug_m3:peak>35",
            by_label["LARGE_OPEN"]["hard_violations"],
        )
        self.assertEqual(report["recommended"], ["SHORT_CROSSFLOW"])
        self.assertEqual(
            report["recommendation_basis"],
            ["pm25_excess", "co2_excess"],
        )

    def test_rain_blocks_motion_but_not_hold(self):
        objective = compile_user_goal("卧室空气太闷。")
        hold = candidate(
            "HOLD",
            co2=[1300],
            pm25=[10],
            temp=[23],
            rh=[50],
            target=0,
            duration=5,
        )
        move = candidate(
            "MOVE",
            co2=[1000],
            pm25=[10],
            temp=[23],
            rh=[50],
            target=30,
            duration=5,
        )
        hold["rain"] = True
        move["rain"] = True

        report = compare_candidate_futures(
            [hold, move],
            objective=objective,
            origin_openings={"W1": 0.0},
        )
        by_label = {row["label"]: row for row in report["results"]}
        self.assertTrue(by_label["HOLD"]["feasible"])
        self.assertFalse(by_label["MOVE"]["feasible"])
        self.assertEqual(report["recommended"], ["HOLD"])


if __name__ == "__main__":
    unittest.main()
