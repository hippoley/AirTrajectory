import unittest

from airtrajectory.physical_handoff import (
    authorize_tau0_from_planner,
    build_physical_handoff_reconcile,
    extract_closed_loop_opening_action,
)


class PhysicalHandoffTests(unittest.TestCase):
    def closed_loop(self):
        return {
            "receipt": {
                "receipt_sha256": "a" * 64,
                "steps": [
                    {
                        "step_index": 0,
                        "step_sha256": "b" * 64,
                        "selected_label": "joint-balanced-medium",
                        "selected_actions": [
                            {
                                "kind": "opening",
                                "opening_id": "W1",
                                "target_pct": 75.0,
                            },
                            {
                                "kind": "opening",
                                "opening_id": "W2",
                                "target_pct": 35.0,
                            },
                        ],
                        "observation": {
                            "co2_ppm": {
                                "living": 909.74,
                                "bedroom": 905.925,
                            }
                        },
                    }
                ],
            }
        }

    def policy(self):
        return {
            "requested_excursion_pct": 5.0,
            "max_first_excursion_pct": 5.0,
        }

    def test_extracts_exact_planner_action_with_lineage(self):
        out = extract_closed_loop_opening_action(
            self.closed_loop(),
            step_index=0,
            opening_id="W1",
        )
        self.assertEqual(out["planned_target_pct"], 75.0)
        self.assertEqual(out["selected_label"], "joint-balanced-medium")
        self.assertEqual(out["closed_loop_receipt_sha256"], "a" * 64)
        self.assertEqual(len(out["planner_handoff_sha256"]), 64)

    def test_first_contact_authorization_preserves_planner_target_but_bounds_write(self):
        handoff = extract_closed_loop_opening_action(
            self.closed_loop(),
            step_index=0,
            opening_id="W1",
        )
        out = authorize_tau0_from_planner(
            handoff,
            acceptance_policy=self.policy(),
        )
        self.assertEqual(out["planned_target_pct"], 75.0)
        self.assertEqual(out["authorized_target_pct"], 5.0)
        self.assertFalse(out["planner_action_fully_authorized"])
        self.assertEqual(
            out["intervention"],
            "FIRST_CONTACT_BOUNDED_TO_COMMISSIONED_EXCURSION",
        )

    def test_reconcile_does_not_claim_full_execution_when_planner_was_bounded(self):
        handoff = extract_closed_loop_opening_action(
            self.closed_loop(),
            step_index=0,
            opening_id="W1",
        )
        authorization = authorize_tau0_from_planner(
            handoff,
            acceptance_policy=self.policy(),
        )
        out = build_physical_handoff_reconcile(
            planner_handoff=handoff,
            authorization=authorization,
            trajectory_step={
                "observation": {"co2_ppm": 1400.0},
                "next_observation": {"co2_ppm": 1392.0},
                "actuator_feedback": [
                    {
                        "actuator_id": "W1",
                        "timestamp": 10.0,
                        "measured_position_pct": 4.8,
                        "quality": "encoder-measured",
                    }
                ],
            },
            zone_id="living",
        )
        self.assertEqual(out["measured_position_pct"], 4.8)
        self.assertEqual(out["measured_co2_delta_ppm"], -8.0)
        self.assertAlmostEqual(
            out["measured_minus_predicted_zone_co2_ppm"],
            482.26,
        )
        self.assertFalse(out["planner_action_fully_executed"])
        self.assertEqual(len(out["physical_reconcile_sha256"]), 64)

    def test_too_small_planner_target_fails_before_motion(self):
        payload = self.closed_loop()
        payload["receipt"]["steps"][0]["selected_actions"][0]["target_pct"] = 1.0
        handoff = extract_closed_loop_opening_action(
            payload,
            step_index=0,
            opening_id="W1",
        )
        with self.assertRaisesRegex(RuntimeError, "below the 2% minimum Reality Delta"):
            authorize_tau0_from_planner(
                handoff,
                acceptance_policy=self.policy(),
            )

    def test_zero_or_close_planner_action_does_not_authorize_open_probe(self):
        payload = self.closed_loop()
        payload["receipt"]["steps"][0]["selected_actions"][0]["target_pct"] = 0
        handoff = extract_closed_loop_opening_action(
            payload,
            step_index=0,
            opening_id="W1",
        )
        with self.assertRaisesRegex(RuntimeError, "does not request positive opening"):
            authorize_tau0_from_planner(
                handoff,
                acceptance_policy=self.policy(),
            )

    def test_wrong_opening_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "exactly one opening action"):
            extract_closed_loop_opening_action(
                self.closed_loop(),
                step_index=0,
                opening_id="W9",
            )


if __name__ == "__main__":
    unittest.main()
