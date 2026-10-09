"""Partial physical dispatch is unresolved, not a successful trajectory."""
import time
import unittest

from airtrajectory.physical import DriverCapabilities
from airtrajectory.multiwindow_physical import (
    MultiWindowPhysicalEnvironment, PhysicalDispatchUnresolved,
)
from airtrajectory.topology import BuildingTopology, OpeningEdge, ZoneNode
from airtrajectory.trajectory import ActuatorFeedback, SensorReading, TransitionAction


class Driver:
    def __init__(self, *, fail=False, wrong_feedback=False):
        self.calls = []
        self.fail = fail
        self.wrong_feedback = wrong_feedback

    def capabilities(self):
        return DriverCapabilities("adversarial-test", True, True, ("co2", "rain"))

    def physical_readiness(self):
        return {"physical_write_ready": True, "write_blockers": []}

    def read_sensors(self):
        now = time.time()
        return [
            SensorReading("co2", "co2", 1200, "ppm", now),
            SensorReading("rain", "rain", 0, "bool", now),
        ]

    def set_position(self, opening_id, target_pct):
        self.calls.append((opening_id, target_pct))
        if self.fail:
            raise TimeoutError("ACK lost; device may still have moved")
        return ActuatorFeedback(
            "wrong-id" if self.wrong_feedback else opening_id,
            time.time(), measured_position_pct=target_pct,
        )


def topology():
    return BuildingTopology.from_parts(
        [ZoneNode("living", 80), ZoneNode("bed", 50)],
        [
            OpeningEdge("W1", "living", "OUTSIDE", "window", 1.5),
            OpeningEdge("W2", "bed", "OUTSIDE", "window", 1.5),
        ],
    )


class PartialDispatchTests(unittest.TestCase):
    def test_second_transport_failure_quarantines_and_reports_partial_effect(self):
        first, second = Driver(), Driver(fail=True)
        env = MultiWindowPhysicalEnvironment(topology(), {"W1": first, "W2": second})
        with self.assertRaises(PhysicalDispatchUnresolved) as caught:
            env.step([TransitionAction("W1", 10), TransitionAction("W2", 10)])
        error = caught.exception
        self.assertTrue(error.physical_effect_unresolved)
        self.assertEqual(error.attempted_openings, ("W1", "W2"))
        self.assertEqual(error.confirmed_feedback_openings, ("W1",))
        self.assertEqual(first.calls, [("W1", 10)])
        self.assertEqual(second.calls, [("W2", 10)])
        self.assertTrue(env.dispatch_unresolved)
        with self.assertRaisesRegex(RuntimeError, "no new writes"):
            env.step([TransitionAction("W1", 0)])
        self.assertEqual(first.calls, [("W1", 10)])
        env.reset()  # A sensor read is NOT a measured actuator reconciliation.
        self.assertTrue(env.dispatch_unresolved)

    def test_wrong_actuator_feedback_identity_quarantines(self):
        driver = Driver(wrong_feedback=True)
        env = MultiWindowPhysicalEnvironment(
            topology(), {"W1": driver}, fixed_openings={"W2": 0}
        )
        with self.assertRaises(PhysicalDispatchUnresolved) as caught:
            env.step([TransitionAction("W1", 5)])
        self.assertIn("identity mismatch", str(caught.exception))
        self.assertEqual(caught.exception.confirmed_feedback_openings, ())
        self.assertEqual(driver.calls, [("W1", 5)])
        self.assertTrue(env.dispatch_unresolved)

    def test_successful_dispatch_not_quarantined(self):
        first, second = Driver(), Driver()
        env = MultiWindowPhysicalEnvironment(topology(), {"W1": first, "W2": second})
        obs, _, _, _, _ = env.step([
            TransitionAction("W1", 10), TransitionAction("W2", 20)
        ])
        self.assertFalse(env.dispatch_unresolved)
        self.assertEqual(obs["opening_pct"]["W1"], 10)
        self.assertEqual(obs["opening_pct"]["W2"], 20)


if __name__ == "__main__":
    unittest.main()
