import json
from pathlib import Path
import unittest

from airtrajectory.demo_runtime import DemoRuntimeSnapshot
from airtrajectory.layout import LayoutContract


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"


class DemoRuntimeSnapshotTests(unittest.TestCase):
    def _layout(self):
        return LayoutContract.from_file(LAYOUT)

    def test_one_snapshot_drives_web_physics_and_trajectory_context(self):
        snapshot = DemoRuntimeSnapshot.resolve(
            self._layout(),
            topology_revision=7,
            opening_positions={"W1": 0.8, "D1": 0.2},
            opening_states={"W1": 75, "W2": 25},
        )

        web = snapshot.web_payload()
        physics = snapshot.physics_input()
        traj = snapshot.trajectory_context()

        self.assertEqual(web["runtime"]["topology_revision"], 7)
        self.assertEqual(physics["topology_revision"], 7)
        self.assertEqual(traj["topology_revision"], 7)
        self.assertEqual(
            web["runtime"]["snapshot_sha256"],
            physics["demo_runtime_snapshot_sha256"],
        )
        self.assertEqual(
            physics["demo_runtime_snapshot_sha256"],
            traj["demo_runtime_snapshot_sha256"],
        )

        web_w1 = next(o for o in web["openings"] if o["id"] == "W1")
        physics_w1 = next(
            o for o in physics["openings"] if o["id"] == "W1"
        )
        self.assertEqual(web_w1["position_t"], 0.8)
        self.assertEqual(physics_w1["position_t"], 0.8)
        self.assertEqual(traj["opening_positions"]["W1"], 0.8)
        self.assertEqual(traj["opening_states"]["W1"], 75.0)

    def test_runtime_hash_changes_when_position_or_state_changes(self):
        layout = self._layout()
        a = DemoRuntimeSnapshot.resolve(layout)
        b = DemoRuntimeSnapshot.resolve(
            layout,
            opening_positions={"W1": 0.8},
        )
        c = DemoRuntimeSnapshot.resolve(
            layout,
            opening_states={"W1": 75},
        )
        self.assertNotEqual(a.sha256(), b.sha256())
        self.assertNotEqual(a.sha256(), c.sha256())

    def test_multiwindow_rollout_carries_same_snapshot_provenance(self):
        snapshot = DemoRuntimeSnapshot.resolve(
            self._layout(),
            topology_revision=3,
            opening_states={"W1": 0, "W2": 0, "W3": 0, "D1": 100, "D2": 100},
        )
        trajectory = snapshot.rollout_rule_policy(
            initial_co2={
                "living": 1400,
                "bedroom": 1300,
                "study": 900,
            },
            max_steps=3,
        )

        self.assertEqual(len(trajectory.steps), 3)
        self.assertEqual(
            trajectory.context["demo_runtime_snapshot_sha256"],
            snapshot.sha256(),
        )
        self.assertEqual(trajectory.context["topology_revision"], 3)
        self.assertEqual(
            set(trajectory.steps[0].executed_actions[i].opening_id for i in range(len(trajectory.steps[0].executed_actions))),
            {"W1", "W2", "W3", "D1", "D2"},
        )

    def test_unknown_runtime_opening_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unknown opening"):
            DemoRuntimeSnapshot.resolve(
                self._layout(),
                opening_states={"W404": 20},
            )


if __name__ == "__main__":
    unittest.main()
