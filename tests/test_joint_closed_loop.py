import unittest
from types import SimpleNamespace

from airtrajectory.joint_closed_loop import (
    BackendContinuationCapability,
    ClosedLoopOrigin,
    RecedingHorizonCapabilityError,
    contam_receding_horizon_capability,
    normalize_action_vector,
    run_receding_horizon_joint,
)


class JointClosedLoopTests(unittest.TestCase):
    def initial_origin(self):
        return ClosedLoopOrigin(
            co2_ppm={"living": 1400, "bedroom": 900, "study": 800},
            opening_pct={"W1": 65, "W2": 35, "W3": 55, "D1": 100, "D2": 100},
        )

    def verified_capability(self):
        return BackendContinuationCapability(
            backend="test-plant",
            physics_fidelity="deterministic-test",
            state_reinjection_verified=True,
            continuation_mode="verified-step-continuation",
            evidence_boundary="unit-test plant",
        )

    def candidates(self, origin, step_index):
        self.assertIn("co2_ppm", origin)
        return [
            {
                "label": "balanced",
                "actions": [
                    {"opening_id": "W1", "target_pct": 75},
                    {"opening_id": "W2", "target_pct": 35},
                    {"opening_id": "W3", "target_pct": 35},
                ],
            },
            {
                "label": "low-motion",
                "actions": [
                    {"opening_id": "W1", "target_pct": 65},
                    {"opening_id": "W2", "target_pct": 35},
                    {"opening_id": "W3", "target_pct": 45},
                ],
            },
        ]

    def evaluator(self, origin, candidates, horizon, step_index):
        by_label = {candidate["label"]: candidate for candidate in candidates}
        selected = (
            by_label["balanced"]
            if origin["co2_ppm"]["living"] > 1200
            else by_label["low-motion"]
        )
        return {
            "selected_label": selected["label"],
            "selected_actions": selected["actions"],
            "objective_score": 1.0 + step_index / 10.0,
            "evidence": {
                "origin_living_ppm": origin["co2_ppm"]["living"],
                "prediction_horizon_steps": horizon,
            },
        }

    def executor(self, origin, actions, step_index):
        openings = dict(origin["opening_pct"])
        for action in actions:
            if action["kind"] == "opening":
                openings[action["opening_id"]] = action["target_pct"]
        co2 = dict(origin["co2_ppm"])
        co2["living"] -= 150
        co2["bedroom"] -= 20
        co2["study"] -= 10
        return {
            "co2_ppm": co2,
            "opening_pct": openings,
            "scalar_values": {},
            "source": "deterministic-test-plant",
            "step_index": step_index,
        }

    def test_verified_backend_replans_from_each_new_observation(self):
        receipt = run_receding_horizon_joint(
            initial_origin=self.initial_origin(),
            control_steps=3,
            prediction_horizon_steps=3,
            candidate_provider=self.candidates,
            evaluator=self.evaluator,
            executor=self.executor,
            capability=self.verified_capability(),
        )

        self.assertTrue(receipt["closed_loop_replanning_executed"])
        self.assertEqual(len(receipt["steps"]), 3)
        self.assertEqual(
            [step["origin"]["co2_ppm"]["living"] for step in receipt["steps"]],
            [1400.0, 1250.0, 1100.0],
        )
        self.assertEqual(
            [step["selected_label"] for step in receipt["steps"]],
            ["balanced", "balanced", "low-motion"],
        )
        self.assertEqual(
            receipt["steps"][0]["next_origin_sha256"],
            receipt["steps"][1]["origin_sha256"],
        )
        self.assertEqual(
            receipt["steps"][1]["next_origin_sha256"],
            receipt["steps"][2]["origin_sha256"],
        )
        self.assertEqual(len(receipt["receipt_sha256"]), 64)
        self.assertTrue(
            all(len(step["step_sha256"]) == 64 for step in receipt["steps"])
        )

    def test_current_real_contam_capability_fails_before_fake_second_replan(self):
        profile = SimpleNamespace(
            origin_state_mode="prj-initial-only",
            prj_initial_co2_ppm={
                "living": 1400,
                "bedroom": 900,
                "study": 800,
            },
        )
        capability = contam_receding_horizon_capability(profile)
        self.assertFalse(capability.state_reinjection_verified)

        with self.assertRaisesRegex(
            RecedingHorizonCapabilityError,
            "cannot claim receding-horizon CONTAM",
        ):
            run_receding_horizon_joint(
                initial_origin=self.initial_origin(),
                control_steps=2,
                prediction_horizon_steps=3,
                candidate_provider=self.candidates,
                evaluator=self.evaluator,
                executor=self.executor,
                capability=capability,
            )

    def test_current_contam_capability_still_allows_one_origin_plan(self):
        profile = SimpleNamespace(
            origin_state_mode="prj-initial-only",
            prj_initial_co2_ppm={"living": 1400},
        )
        receipt = run_receding_horizon_joint(
            initial_origin=self.initial_origin(),
            control_steps=1,
            prediction_horizon_steps=3,
            candidate_provider=self.candidates,
            evaluator=self.evaluator,
            executor=self.executor,
            capability=contam_receding_horizon_capability(profile),
        )
        self.assertFalse(receipt["closed_loop_replanning_executed"])
        self.assertFalse(
            receipt["backend_capability"]["state_reinjection_verified"]
        )

    def test_action_vector_rejects_duplicates_and_out_of_range_values(self):
        with self.assertRaisesRegex(ValueError, "duplicate action"):
            normalize_action_vector(
                [
                    {"opening_id": "W1", "target_pct": 50},
                    {"opening_id": "W1", "target_pct": 60},
                ]
            )
        with self.assertRaisesRegex(ValueError, "within"):
            normalize_action_vector(
                [{"opening_id": "W1", "target_pct": 101}]
            )

    def test_origin_hash_chain_changes_with_measured_state(self):
        receipt = run_receding_horizon_joint(
            initial_origin=self.initial_origin(),
            control_steps=2,
            prediction_horizon_steps=2,
            candidate_provider=self.candidates,
            evaluator=self.evaluator,
            executor=self.executor,
            capability=self.verified_capability(),
        )
        self.assertNotEqual(
            receipt["steps"][0]["origin_sha256"],
            receipt["steps"][1]["origin_sha256"],
        )
        self.assertEqual(
            receipt["steps"][0]["next_origin_sha256"],
            receipt["steps"][1]["origin_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
