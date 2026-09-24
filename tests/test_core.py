import unittest

from airtrajectory import (
    ActuatorFeedback, BuildingTopology, FastFlowField, OpeningEdge, SemanticAction,
    SensorReading, ToyMultizoneEnvironment, TransitionAction, ZoneNode,
    exhaustive_opening_search, fork_actions, rollout,
)


class CoreTests(unittest.TestCase):
    def topology(self):
        return BuildingTopology.from_parts(
            [ZoneNode("living", 45), ZoneNode("bedroom", 30)],
            [
                OpeningEdge("w1", "living", "OUTSIDE", "window", 1.2),
                OpeningEdge("door", "living", "bedroom", "door", 1.8),
                OpeningEdge("w2", "bedroom", "OUTSIDE", "window", 1.0),
            ],
        )

    def test_opening_reduces_co2(self):
        env = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 900})
        before, _ = env.reset()
        after, _, _, _, _ = env.step([TransitionAction("w1", 100)])
        self.assertLess(after["co2_ppm"]["living"], before["co2_ppm"]["living"])

    def test_rollout_preserves_learning_fields(self):
        env = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 900}, horizon_steps=4)
        def policy(_):
            return [TransitionAction("w1", 50), TransitionAction("door", 100)]
        trajectory = rollout(env, policy, "two-room", "fixed", max_steps=10)
        self.assertEqual(len(trajectory.steps), 4)
        self.assertEqual(trajectory.steps[0].proposed_actions, trajectory.steps[0].executed_actions)
        self.assertIn("co2_ppm", trajectory.steps[-1].next_observation)

    def test_physical_trajectory_schema_preserves_semantic_and_feedback_layers(self):
        env = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 900}, horizon_steps=1)
        trajectory = rollout(env, lambda _: [TransitionAction("w1", 50)], "two-room", "rule-v1", max_steps=1)
        step = trajectory.steps[0]
        step.semantic_actions.append(SemanticAction("window_group", "living_windows", "VENT", 50))
        step.sensor_readings.append(SensorReading("co2-living", "co2", 1400, "ppm", 1.0, "good"))
        step.actuator_feedback.append(ActuatorFeedback("actuator-w1", 2.0, measured_position_pct=48))
        payload = trajectory.to_dict()
        self.assertEqual(payload["schema_version"], "0.2")
        self.assertEqual(payload["steps"][0]["semantic_actions"][0]["command"], "VENT")
        self.assertEqual(payload["steps"][0]["actuator_feedback"][0]["measured_position_pct"], 48)
        self.assertIsNone(payload["steps"][0]["actuator_feedback"][0]["estimated_position_pct"])

    def test_feedback_separates_measured_and_estimated_position(self):
        feedback = ActuatorFeedback("actuator-w1", 1.0, estimated_position_pct=50, quality="estimated")
        self.assertIsNone(feedback.measured_position_pct)
        self.assertEqual(feedback.estimated_position_pct, 50)

    def test_invalid_topology_rejected(self):
        with self.assertRaises(ValueError):
            BuildingTopology.from_parts(
                [ZoneNode("living", 45)],
                [OpeningEdge("broken", "living", "missing", "door", 1.0)],
            )

    def test_forks_share_origin_and_restore_source(self):
        env = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 1100}, horizon_steps=20)
        env.reset()
        env.step([TransitionAction("door", 100)])
        origin = env.snapshot()
        branches = fork_actions(
            env,
            {
                "open25": [TransitionAction("w1", 25), TransitionAction("door", 100)],
                "open75": [TransitionAction("w1", 75), TransitionAction("door", 100)],
            },
            horizon_steps=5,
        )
        self.assertEqual(env.snapshot(), origin)
        self.assertLess(
            branches["open75"].observations[-1]["co2_ppm"]["living"],
            branches["open25"].observations[-1]["co2_ppm"]["living"],
        )

    def test_fast_field_is_deterministic_and_opening_sensitive(self):
        field = FastFlowField(self.topology())
        points = [(10.0, 20.0), (30.0, 40.0)]
        closed = field.sample(points, {"w1": 0, "door": 0, "w2": 0}, 25, 2.8)
        opened = field.sample(points, {"w1": 75, "door": 100, "w2": 25}, 25, 2.8)
        repeated = field.sample(points, {"w1": 75, "door": 100, "w2": 25}, 25, 2.8)
        self.assertEqual(opened, repeated)
        self.assertNotEqual(closed.vectors, opened.vectors)
        self.assertEqual(opened.backend, "fast-field-v1")

    def test_exhaustive_search_ranks_and_restores(self):
        env = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 1100}, horizon_steps=20)
        env.reset()
        env.step([TransitionAction("door", 100)])
        origin = env.snapshot()
        results = exhaustive_opening_search(
            env,
            ("w1", "w2"),
            levels=(0, 50, 100),
            fixed_actions=(TransitionAction("door", 100),),
            horizon_steps=5,
            top_k=3,
        )
        self.assertEqual(len(results), 3)
        self.assertEqual(env.snapshot(), origin)
        self.assertGreaterEqual(results[0].branch.return_value, results[1].branch.return_value)
        self.assertGreaterEqual(results[1].branch.return_value, results[2].branch.return_value)
        self.assertTrue(all(result.label.startswith("SEARCH · ") for result in results))

    def test_exhaustive_search_rejects_empty_openings(self):
        env = ToyMultizoneEnvironment(self.topology())
        env.reset()
        with self.assertRaises(ValueError):
            exhaustive_opening_search(env, (), top_k=1)


if __name__ == "__main__":
    unittest.main()
