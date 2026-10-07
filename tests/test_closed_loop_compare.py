import unittest

from airtrajectory.closed_loop_compare import (
    compare_closed_loop_modes,
    score_realized_closed_loop,
)


def receipt(rows):
    steps = []
    for index, row in enumerate(rows):
        steps.append(
            {
                "step_index": index,
                "origin": {
                    "co2_ppm": row["origin_co2"],
                    "opening_pct": row["origin_openings"],
                },
                "observation": {
                    "co2_ppm": row["co2"],
                    "opening_pct": row["openings"],
                },
                "selected_label": row["label"],
            }
        )
    return {"steps": steps, "receipt_sha256": "a" * 64}


WEIGHTS = {
    "mean_excess_1000": 0.01,
    "max_excess_1200": 0.02,
    "high_co2_zone_steps": 1.0,
    "mean_room_imbalance": 0.005,
    "movement_pct_sum": 0.02,
}


class ClosedLoopCompareTests(unittest.TestCase):
    def test_score_uses_only_realized_states_and_actual_movement(self):
        data = receipt(
            [
                {
                    "origin_co2": {"a": 1400, "b": 900},
                    "co2": {"a": 1000, "b": 850},
                    "origin_openings": {"W1": 10, "W2": 20},
                    "openings": {"W1": 30, "W2": 20},
                    "label": "joint",
                },
                {
                    "origin_co2": {"a": 1000, "b": 850},
                    "co2": {"a": 800, "b": 750},
                    "origin_openings": {"W1": 30, "W2": 20},
                    "openings": {"W1": 30, "W2": 0},
                    "label": "independent",
                },
            ]
        )
        out = score_realized_closed_loop(
            data,
            iaq_reference_ppm=1000,
            high_co2_ppm=1200,
            objective_weights=WEIGHTS,
        )
        self.assertEqual(out["metrics"]["control_steps"], 2)
        self.assertEqual(out["metrics"]["movement_pct_sum"], 40.0)
        self.assertEqual(out["metrics"]["selected_labels"], ["joint", "independent"])
        self.assertEqual(out["metrics"]["high_co2_zone_steps"], 0)
        self.assertEqual(len(out["score_sha256"]), 64)

    def test_comparison_reports_win_without_forcing_it(self):
        adaptive = receipt(
            [
                {
                    "origin_co2": {"a": 1400, "b": 900},
                    "co2": {"a": 900, "b": 850},
                    "origin_openings": {"W1": 10},
                    "openings": {"W1": 20},
                    "label": "joint",
                }
            ]
        )
        independent = receipt(
            [
                {
                    "origin_co2": {"a": 1400, "b": 900},
                    "co2": {"a": 1100, "b": 850},
                    "origin_openings": {"W1": 10},
                    "openings": {"W1": 40},
                    "label": "independent",
                }
            ]
        )
        out = compare_closed_loop_modes(
            adaptive_receipt=adaptive,
            independent_receipt=independent,
            iaq_reference_ppm=1000,
            high_co2_ppm=1200,
            objective_weights=WEIGHTS,
        )
        self.assertEqual(out["outcome"], "WIN")
        self.assertGreater(out["objective_improvement"], 0)
        self.assertEqual(len(out["comparison_sha256"]), 64)

    def test_mismatched_control_horizons_are_rejected(self):
        one = receipt(
            [{
                "origin_co2": {"a": 900},
                "co2": {"a": 800},
                "origin_openings": {"W1": 0},
                "openings": {"W1": 10},
                "label": "a",
            }]
        )
        two = receipt(
            [
                {
                    "origin_co2": {"a": 900},
                    "co2": {"a": 800},
                    "origin_openings": {"W1": 0},
                    "openings": {"W1": 10},
                    "label": "a",
                },
                {
                    "origin_co2": {"a": 800},
                    "co2": {"a": 700},
                    "origin_openings": {"W1": 10},
                    "openings": {"W1": 10},
                    "label": "a",
                },
            ]
        )
        with self.assertRaisesRegex(ValueError, "same control step count"):
            compare_closed_loop_modes(
                adaptive_receipt=one,
                independent_receipt=two,
                iaq_reference_ppm=1000,
                high_co2_ppm=1200,
                objective_weights=WEIGHTS,
            )


if __name__ == "__main__":
    unittest.main()
