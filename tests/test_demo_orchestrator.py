import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

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



class FakeContamCx:
    def __init__(self, prj_file_path, wp_mode=0, cb_option=False, *_):
        self.path=prj_file_path
        self.nZones=3
        self.nPaths=5
        self.nInputControls=3
        self.nOutputControls=0
        self.inputControls=[
            SimpleNamespace(name="W1_open"),
            SimpleNamespace(name="W2_open"),
            SimpleNamespace(name="W3_open"),
        ]
        self.outputControls=[]
        self.controls={}
        self.steps=0
        self.ended=False
    def setupSimulation(self,use_cosim=1): self.use_cosim=use_cosim
    def getVersion(self): return "fake-contam"
    def getSimTimeStep(self): return 60
    def setInputControlValue(self,n,v): self.controls[n]=v
    def doSimStep(self,n): self.steps+=n
    def getZoneMF(self,z,c):
        return {1:0.0020,2:0.0018,3:0.0017}[z]-(self.steps*0.00001)
    def getPathFlow(self,p):
        return float(p)*0.1
    def endSimulation(self): self.ended=True

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

    def test_contam_backend_shares_snapshot_policy_and_symbolic_mappings(self):
        snap=self.snapshot()
        with tempfile.TemporaryDirectory() as d:
            prj=Path(d)/"demo.prj"
            prj.write_text("fixture")
            provenance={
                "sha256":"e"*64,
                "zone_numbers":{
                    "zone:bedroom":1,
                    "zone:living":2,
                    "zone:study":3,
                },
                "path_numbers":{
                    "path:D1":1,
                    "path:D2":2,
                    "path:W1":3,
                    "path:W2":4,
                    "path:W3":5,
                },
                "input_control_names":{
                    "W1":"W1_open",
                    "W2":"W2_open",
                    "W3":"W3_open",
                },
                "initial_co2_ppm":{"living":1400.0,"bedroom":1300.0,"study":1250.0},
            }
            result=run_demo(
                snap,
                mode="contam",
                max_steps=1,
                contam_prj_path=prj,
                contam_provenance=provenance,
                contam_binding_factory=FakeContamCx,
                fixed_openings={"D1":100,"D2":100},
            )
        self.assertEqual(result.trajectory.environment_kind,"contam")
        self.assertEqual(
            result.trajectory.context["demo_runtime_snapshot_sha256"],
            snap.sha256(),
        )
        self.assertEqual(
            result.trajectory.context["contam_path_numbers"]["W1"],
            3,
        )
        self.assertEqual(result.trajectory.steps[0].executed_actions[0].opening_id,"W1")
        self.assertEqual(result.trajectory.context["fixed_opening_ids"],["D1","D2"])
        self.assertEqual(result.trajectory.context["reset_info"]["warm_start_steps"],1)
        self.assertEqual(result.trajectory.context["reset_info"]["warm_start_opening_pct"],{"W1":100.0,"W2":100.0,"W3":100.0})
        self.assertEqual(result.trajectory.context["reset_info"]["restored_opening_pct"]["D1"],100.0)


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
