"""Negative tests for non-finite opening overrides at runtime handoff."""
import json
import unittest
from pathlib import Path
from airtrajectory.layout import LayoutContract
from airtrajectory.demo_runtime import DemoRuntimeSnapshot

FIXTURE = Path(__file__).resolve().parents[1] / "web/data/home_topology.fixed.json"


class NonfiniteRuntimeOverrideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = LayoutContract.from_dict(json.loads(FIXTURE.read_text(encoding="utf-8")))
        cls.opening_id = cls.layout.openings[0].id

    def test_reject_nonfinite_position(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=repr(value)):
                with self.assertRaisesRegex(ValueError, "position must be between"):
                    DemoRuntimeSnapshot.resolve(self.layout, opening_positions={self.opening_id: value})

    def test_reject_nonfinite_state(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=repr(value)):
                with self.assertRaisesRegex(ValueError, "state must be between"):
                    DemoRuntimeSnapshot.resolve(self.layout, opening_states={self.opening_id: value})

    def test_finite_boundary_values_still_work(self):
        for position in (0.0, 1.0):
            for state in (0.0, 100.0):
                snapshot = DemoRuntimeSnapshot.resolve(
                    self.layout, opening_positions={self.opening_id: position},
                    opening_states={self.opening_id: state})
                self.assertEqual(snapshot.opening_positions[self.opening_id], position)
                self.assertEqual(snapshot.opening_states[self.opening_id], state)


if __name__ == "__main__":
    unittest.main()
