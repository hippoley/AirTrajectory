import unittest
from pathlib import Path

from airtrajectory.demo_orchestrator import run_demo
from airtrajectory.demo_runtime import DemoRuntimeSnapshot
from airtrajectory.layout import LayoutContract
from airtrajectory.physical import DriverCapabilities
from airtrajectory.trajectory import ActuatorFeedback, SensorReading


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"


class Driver:
    def __init__(self, zone):
        self.zone = zone
        self.position = 0.0
        self.ts = 100.0

    def capabilities(self):
        return DriverCapabilities(
            transport="test",
            simulated=False,
            measured_position=True,
            sensor_types=("co2", "rain"),
        )

    def physical_readiness(self):
        return {
            "physical_write_ready": True,
            "write_blockers": [],
        }

    def read_sensors(self):
        self.ts += 1
        return [
            SensorReading(
                sensor_id=self.zone+"-co2",
                sensor_type="co2",
                value=1300.0,
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
        self.ts += 1
        self.position = float(target_pct)
        return ActuatorFeedback(
            actuator_id=opening_id,
            timestamp=self.ts,
            measured_position_pct=self.position,
            quality="measured",
        )


class DemoOrchestratorTests(unittest.TestCase):
    def snapshot(self):
        return DemoRuntimeSnapshot.resolve(
            LayoutContract.from_file(LAYOUT),
            topology_revision=9,
            opening_states={
                "W1": 0,
                "W2": 0,
                "W3": 0,
                "D1": 100,
                "D2": 100,
            },
        )

    def test_simulation_and_physical_share_snapshot_and_policy_identity(self):
        snap = self.snapshot()
        sim = run_demo(
            snap,
            mode="simulation",
            max_steps=1,
            initial_co2={
                "living": 1400,
                "bedroom": 1300,
                "study": 1250,
            },
        )
        physical = run_demo(
            snap,
            mode="physical",
            max_steps=1,
            drivers={
                "W1": Driver("living"),
                "W2": Driver("bedroom"),
                "W3": Driver("study"),
            },
            fixed_openings={"D1": 100, "D2": 100},
        )

        self.assertEqual(
            sim.trajectory.context["demo_runtime_snapshot_sha256"],
            physical.trajectory.context["demo_runtime_snapshot_sha256"],
        )
        self.assertEqual(sim.trajectory.policy_id, physical.trajectory.policy_id)
        self.assertEqual(sim.trajectory.environment_kind, "simulation")
        self.assertEqual(physical.trajectory.environment_kind, "physical")

    def test_physical_trajectory_preserves_sensor_and_actuator_evidence(self):
        result = run_demo(
            self.snapshot(),
            mode="physical",
            max_steps=1,
            drivers={
                "W1": Driver("living"),
                "W2": Driver("bedroom"),
                "W3": Driver("study"),
            },
            fixed_openings={"D1": 100, "D2": 100},
        )
        step = result.trajectory.steps[0]
        self.assertTrue(step.sensor_readings)
        self.assertTrue(step.next_sensor_readings)
        self.assertEqual(
            {f.actuator_id for f in step.actuator_feedback},
            {"W1", "W2", "W3"},
        )

    def test_physical_mode_requires_all_exterior_controllable_drivers(self):
        with self.assertRaisesRegex(ValueError, "missing drivers"):
            run_demo(
                self.snapshot(),
                mode="physical",
                max_steps=1,
                drivers={
                    "W1": Driver("living"),
                    "W2": Driver("bedroom"),
                },
            )


if __name__ == "__main__":
    unittest.main()
