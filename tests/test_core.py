import unittest

from airtrajectory import (
    BuildingTopology, OpeningEdge, ToyMultizoneEnvironment, TransitionAction,
    ZoneNode, fork_actions, rollout,
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
        self.assertEqual(branches["open25"].observations[0]["step"], branches["open75"].observations[0]["step"])
        self.assertLess(
            branches["open75"].observations[-1]["co2_ppm"]["living"],
            branches["open25"].observations[-1]["co2_ppm"]["living"],
        )
        self.assertNotEqual(branches["open25"].return_value, branches["open75"].return_value)


if __name__ == "__main__":
    unittest.main()
