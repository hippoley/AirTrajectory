import unittest

from airtrajectory.multiwindow_physical import MultiWindowPhysicalEnvironment
from airtrajectory.physical import DriverCapabilities
from airtrajectory.topology import BuildingTopology, OpeningEdge, ZoneNode
from airtrajectory.trajectory import ActuatorFeedback, SensorReading, TransitionAction


class Driver:
    def __init__(self, zone, ready=True, simulated=False):
        self.zone = zone
        self.ready = ready
        self.simulated = simulated
        self.position = 0.0
        self.ts = 100.0

    def capabilities(self):
        return DriverCapabilities(
            transport="test",
            simulated=self.simulated,
            measured_position=True,
            sensor_types=("co2", "rain"),
        )

    def physical_readiness(self):
        return {
            "physical_write_ready": self.ready,
            "write_blockers": [] if self.ready else ["commissioning incomplete"],
        }

    def read_sensors(self):
        self.ts += 1.0
        return [
            SensorReading(
                sensor_id=self.zone+"-co2",
                sensor_type="co2",
                value=1300.0 if self.zone == "living" else 1100.0,
                unit="ppm",
                timestamp=self.ts,
                quality="measured",
            ),
            SensorReading(
                sensor_id=self.zone+"-rain",
                sensor_type="rain",
                value=0.0,
                unit="bool",
                timestamp=self.ts,
                quality="measured",
            ),
        ]

    def set_position(self, opening_id, target_pct):
        self.ts += 1.0
        self.position = float(target_pct)
        return ActuatorFeedback(
            actuator_id=opening_id,
            timestamp=self.ts,
            measured_position_pct=self.position,
            quality="measured",
        )


def topology():
    return BuildingTopology.from_parts(
        [
            ZoneNode("living", 75),
            ZoneNode("bedroom", 37.5),
        ],
        [
            OpeningEdge("W1", "living", "OUTSIDE", "window", 1.5),
            OpeningEdge("W2", "bedroom", "OUTSIDE", "window", 1.5),
            OpeningEdge("D1", "living", "bedroom", "door", 1.8),
        ],
    )


class MultiWindowPhysicalEnvironmentTests(unittest.TestCase):
    def test_two_real_windows_and_fixed_internal_door_form_one_observation(self):
        env = MultiWindowPhysicalEnvironment(
            topology(),
            {
                "W1": Driver("living"),
                "W2": Driver("bedroom"),
            },
            fixed_openings={"D1": 100},
        )
        obs, info = env.reset()

        self.assertEqual(set(obs["co2_ppm"]), {"living", "bedroom"})
        self.assertEqual(obs["opening_pct"]["D1"], 100)
        self.assertEqual(
            set(info["physical_opening_readiness"]),
            {"W1", "W2"},
        )

    def test_multiwindow_step_dispatches_each_action_to_its_driver(self):
        env = MultiWindowPhysicalEnvironment(
            topology(),
            {
                "W1": Driver("living"),
                "W2": Driver("bedroom"),
            },
            fixed_openings={"D1": 100},
        )
        env.reset()
        obs, reward, _, _, info = env.step([
            TransitionAction("W1", 75),
            TransitionAction("W2", 25),
            TransitionAction("D1", 100),
        ])

        self.assertEqual(obs["opening_pct"]["W1"], 75)
        self.assertEqual(obs["opening_pct"]["W2"], 25)
        self.assertEqual(obs["opening_pct"]["D1"], 100)
        self.assertEqual(len(info["actuator_feedback"]), 2)

    def test_one_unready_window_blocks_entire_physical_dispatch(self):
        env = MultiWindowPhysicalEnvironment(
            topology(),
            {
                "W1": Driver("living", ready=True),
                "W2": Driver("bedroom", ready=False),
            },
            fixed_openings={"D1": 100},
        )
        env.reset()
        with self.assertRaisesRegex(
            RuntimeError,
            "W2: commissioning incomplete",
        ):
            env.step([
                TransitionAction("W1", 75),
                TransitionAction("W2", 25),
            ])

    def test_fixed_door_cannot_be_silently_actuated(self):
        env = MultiWindowPhysicalEnvironment(
            topology(),
            {"W1": Driver("living")},
            fixed_openings={"D1": 100, "W2": 0},
        )
        with self.assertRaisesRegex(RuntimeError, "fixed opening D1 cannot move"):
            env.step([TransitionAction("D1", 50)])


if __name__ == "__main__":
    unittest.main()
