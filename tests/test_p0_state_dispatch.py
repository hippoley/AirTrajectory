"""P0 adversarial regressions: no invalid batch may start a physical write."""
import math
import time
import unittest

from airtrajectory.physical import DriverCapabilities, PhysicalWindowEnvironment
from airtrajectory.multiwindow_physical import MultiWindowPhysicalEnvironment
from airtrajectory.topology import BuildingTopology, OpeningEdge, ZoneNode
from airtrajectory.trajectory import ActuatorFeedback, SensorReading, TransitionAction


def topology():
    return BuildingTopology.from_parts(
        [ZoneNode("living", 80), ZoneNode("bedroom", 45)],
        [
            OpeningEdge("W1", "living", "OUTSIDE", "window", 1.2),
            OpeningEdge("W2", "bedroom", "OUTSIDE", "window", 1.2),
            OpeningEdge("D1", "living", "bedroom", "door", 1.5),
        ],
    )


class RecordingDriver:
    def __init__(self, *, rain=0, duplicate=False, future=False, stale=False):
        self.calls = []
        self.rain = rain
        self.duplicate = duplicate
        self.future = future
        self.stale = stale

    def capabilities(self):
        return DriverCapabilities("adversarial-test", True, True, ("co2", "rain"))

    def physical_readiness(self):
        return {"physical_write_ready": True, "write_blockers": []}

    def read_sensors(self):
        ts = time.time() + (600 if self.future else -600 if self.stale else 0)
        rows = [
            SensorReading("c", "co2", 1100, "ppm", ts),
        ]
        if self.duplicate:
            rows.append(SensorReading("c2", "co2", 1300, "ppm", ts))
        if self.rain is not None:
            rows.append(SensorReading("r", "rain", self.rain, "bool", ts))
        return rows

    def set_position(self, opening_id, target_pct):
        self.calls.append((opening_id, target_pct))
        return ActuatorFeedback(opening_id, time.time(), measured_position_pct=target_pct)


class P0StateAndDispatchTests(unittest.TestCase):
    def test_duplicate_topology_ids_fail_before_mapping(self):
        with self.assertRaisesRegex(ValueError, "duplicate zone"):
            BuildingTopology.from_parts([ZoneNode("A", 50), ZoneNode("A", 70)], [])
        with self.assertRaisesRegex(ValueError, "duplicate opening"):
            BuildingTopology.from_parts(
                [ZoneNode("A", 50)],
                [OpeningEdge("W", "A", "OUTSIDE", "window", 1),
                 OpeningEdge("W", "A", "OUTSIDE", "window", 2)],
            )

    def test_nonfinite_topology_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            BuildingTopology.from_parts([ZoneNode("A", float("nan"))], [])
        with self.assertRaisesRegex(ValueError, "finite"):
            BuildingTopology.from_parts(
                [ZoneNode("A", 50)],
                [OpeningEdge("W", "A", "OUTSIDE", "window", float("inf"))],
            )

    def test_invalid_actuator_numbers_rejected_at_construction(self):
        for invalid in [float("nan"), float("inf"), True]:
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "finite numeric"):
                    TransitionAction("W1", invalid)
                with self.assertRaisesRegex(ValueError, "finite numeric"):
                    ActuatorFeedback("W1", time.time(), measured_position_pct=invalid)

    def test_single_window_prevalidates_entire_batch(self):
        driver = RecordingDriver()
        env = PhysicalWindowEnvironment(driver, "W1")
        with self.assertRaisesRegex(RuntimeError, "at most one action"):
            env.step([TransitionAction("W1", 5), TransitionAction("W2", 20)])
        self.assertEqual(driver.calls, [])

    def test_single_window_rejects_future_and_duplicate_sensors(self):
        for kwargs, expected in [
            ({"future": True}, "future sensor timestamp"),
            ({"duplicate": True}, "duplicate co2"),
            ({"rain": 2}, "rain sensor"),
        ]:
            with self.subTest(kwargs=kwargs):
                driver = RecordingDriver(**kwargs)
                env = PhysicalWindowEnvironment(driver, "W1")
                with self.assertRaisesRegex(RuntimeError, expected):
                    env.reset()
                self.assertEqual(driver.calls, [])

    def test_multiwindow_duplicate_and_unknown_action_prevent_all_writes(self):
        a, b = RecordingDriver(), RecordingDriver()
        env = MultiWindowPhysicalEnvironment(topology(), {"W1": a, "W2": b})
        for actions, expected in [
            ([TransitionAction("W1", 10), TransitionAction("W1", 20)], "duplicate"),
            ([TransitionAction("W1", 10), TransitionAction("BAD", 20)], "no physical driver"),
        ]:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex((ValueError, KeyError), expected):
                    env.step(actions)
                self.assertEqual(a.calls, [])
                self.assertEqual(b.calls, [])

    def test_multiwindow_missing_rain_never_authorizes_exterior_open(self):
        a = RecordingDriver(rain=None)
        env = MultiWindowPhysicalEnvironment(
            topology(), {"W1": a}, fixed_openings={"W2": 0, "D1": 100}
        )
        with self.assertRaisesRegex(RuntimeError, "missing rain"):
            env.step([TransitionAction("W1", 25)])
        self.assertEqual(a.calls, [])

    def test_multiwindow_stale_or_future_rain_blocks_before_write(self):
        for kwargs, expected in [
            ({"stale": True}, "stale sensor timestamp"),
            ({"future": True}, "future sensor timestamp"),
        ]:
            with self.subTest(kwargs=kwargs):
                a = RecordingDriver(**kwargs)
                env = MultiWindowPhysicalEnvironment(
                    topology(), {"W1": a}, fixed_openings={"W2": 0, "D1": 100}
                )
                with self.assertRaisesRegex(RuntimeError, expected):
                    env.step([TransitionAction("W1", 25)])
                self.assertEqual(a.calls, [])

    def test_multiwindow_rain_allows_safe_closing(self):
        a = RecordingDriver(rain=1)
        env = MultiWindowPhysicalEnvironment(
            topology(), {"W1": a}, fixed_openings={"W2": 0, "D1": 100},
            initial_openings={"W1": 25},
        )
        env.step([TransitionAction("W1", 0)])
        self.assertEqual(a.calls, [("W1", 0)])

    def test_multiwindow_rejects_invalid_initial_positions(self):
        with self.assertRaisesRegex(ValueError, "invalid initial"):
            MultiWindowPhysicalEnvironment(
                topology(), {"W1": RecordingDriver()}, initial_openings={"W1": math.nan}
            )


if __name__ == "__main__":
    unittest.main()
