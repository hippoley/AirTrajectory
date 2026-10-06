import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from airtrajectory.contam_runtime_verification import (
    verify_engineering_contam_runtime,
)
from airtrajectory.demo_runtime import DemoRuntimeSnapshot
from airtrajectory.layout import LayoutContract


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"


class FakeEngineeringCx:
    def __init__(
        self,
        prj_file_path,
        wp_mode=0,
        cb_option=False,
        init_callback=None,
        *_,
    ):
        self.path = prj_file_path
        self.wp_mode = wp_mode
        self.cb_option = cb_option
        self.nZones = 3
        self.nPaths = 5
        self.nInputControls = 3
        self.nOutputControls = 0
        self.inputControls = [
            SimpleNamespace(name="W1_open"),
            SimpleNamespace(name="W2_open"),
            SimpleNamespace(name="W3_open"),
        ]
        self.outputControls = []
        self.controls = {}
        self.steps = 0
        self.ended = False
        self.ambient = {}
        if init_callback is not None:
            init_callback(self)

    def setAmbtPressure(self, value):
        self.ambient["pressure_pa"] = float(value)

    def setAmbtWindSpeed(self, value):
        self.ambient["wind_speed_m_s"] = float(value)

    def setAmbtWindDirection(self, value):
        self.ambient["wind_direction_deg"] = float(value)

    def setAmbtTemperature(self, value):
        self.ambient["temperature_k"] = float(value)

    def setAmbtMassFraction(self, number, value):
        self.ambient.setdefault("mass_fractions", {})[int(number)] = float(
            value
        )

    def setVerbosity(self, value):
        self.verbosity = value

    def setupSimulation(self, use_cosim=1):
        self.use_cosim = use_cosim
        return 0

    def getVersion(self):
        return "fake-engineering-contam"

    def getSimTimeStep(self):
        return 60

    def setInputControlValue(self, number, value):
        self.controls[int(number)] = float(value)

    def doSimStep(self, count):
        self.steps += int(count)

    def getZoneMassFraction(self, zone, contaminant):
        base = {1: 0.0018, 2: 0.0020, 3: 0.0017}[int(zone)]
        return base - self.steps * 0.00001

    def getPathFlow(self, path):
        return float(path) * 0.1

    def endSimulation(self):
        self.ended = True


def build_receipt(layout, prj_sha):
    snapshot = DemoRuntimeSnapshot.resolve(layout)
    return {
        "schema_version": "0.1",
        "status": "ENGINEERING_INPUTS_READY",
        "engineering_inputs_ready": True,
        "runtime_verified": False,
        "engineering_truth": False,
        "engineering_readiness": {
            "engineering_ready": True,
            "status": "ENGINEERING_READY",
        },
        "topology_id": layout.topology_id,
        "layout_contract_sha256": layout.sha256(),
        "demo_runtime_snapshot_sha256": snapshot.sha256(),
        "sha256": prj_sha,
        "zone_numbers": {
            "zone:bedroom": 1,
            "zone:living": 2,
            "zone:study": 3,
        },
        "path_numbers": {
            "path:D1": 1,
            "path:D2": 2,
            "path:W1": 3,
            "path:W2": 4,
            "path:W3": 5,
        },
        "control_numbers": {
            "control:W1": 1,
            "control:W2": 2,
            "control:W3": 3,
        },
        "input_control_names": {
            "W1": "W1_open",
            "W2": "W2_open",
            "W3": "W3_open",
        },
        "input_control_ranges": {
            "W1": {"closed_value": 0.01, "open_value": 1.0},
            "W2": {"closed_value": 0.01, "open_value": 1.0},
            "W3": {"closed_value": 0.01, "open_value": 1.0},
        },
        "initial_input_controls": {
            "1": {
                "opening_id": "W1",
                "name": "W1_open",
                "value": 0.01 + 0.99 * 0.65,
            },
            "2": {
                "opening_id": "W2",
                "name": "W2_open",
                "value": 0.01 + 0.99 * 0.35,
            },
            "3": {
                "opening_id": "W3",
                "name": "W3_open",
                "value": 0.01 + 0.99 * 0.55,
            },
        },
        "initial_co2_ppm": {
            "living": 1400.0,
            "bedroom": 900.0,
            "study": 800.0,
        },
        "contam_ambient": {
            "temperature_k": 298.15,
            "pressure_pa": 101325.0,
            "wind_speed_m_s": 1.5,
            "wind_direction_deg": 180.0,
            "mass_fractions": {"0": 0.00065},
        },
    }


class ContamRuntimeVerificationTests(unittest.TestCase):
    def setUp(self):
        self.layout = LayoutContract.from_file(LAYOUT)

    def test_verified_runtime_emits_separate_non_field_truth_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            prj = Path(tmp) / "engineering.prj"
            prj.write_text("engineering fixture", encoding="utf-8")
            sha = hashlib.sha256(prj.read_bytes()).hexdigest()
            receipt = verify_engineering_contam_runtime(
                layout=self.layout,
                prj_path=prj,
                build_receipt=build_receipt(self.layout, sha),
                steps=2,
                binding_factory=FakeEngineeringCx,
            )

        self.assertEqual(
            receipt["status"],
            "ENGINEERING_RUNTIME_VERIFIED",
        )
        self.assertTrue(receipt["engineering_inputs_ready"])
        self.assertTrue(receipt["runtime_verified"])
        self.assertTrue(receipt["engineering_model_verified"])
        self.assertFalse(receipt["field_validation_verified"])
        self.assertFalse(receipt["engineering_truth"])
        self.assertEqual(receipt["zone_count"], 3)
        self.assertEqual(receipt["path_count"], 5)
        self.assertEqual(receipt["steps"], 2)
        self.assertEqual(
            receipt["contam_version"],
            "fake-engineering-contam",
        )
        self.assertEqual(len(receipt["trajectory_sha256"]), 64)
        self.assertEqual(len(receipt["prediction_series"]), 2)
        self.assertEqual(len(receipt["prediction_series_sha256"]), 64)
        self.assertEqual(set(receipt["prediction_series"][0]["co2_ppm"]), {"living","bedroom","study"})
        self.assertEqual(set(receipt["prediction_series"][0]["opening_pct"]), {"W1","W2","W3","D1","D2"})
        self.assertEqual(len(receipt["runtime_receipt_sha256"]), 64)

    def test_prj_hash_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            prj = Path(tmp) / "engineering.prj"
            prj.write_text("engineering fixture", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "PRJ SHA-256"):
                verify_engineering_contam_runtime(
                    layout=self.layout,
                    prj_path=prj,
                    build_receipt=build_receipt(
                        self.layout,
                        "f" * 64,
                    ),
                    binding_factory=FakeEngineeringCx,
                )

    def test_snapshot_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            prj = Path(tmp) / "engineering.prj"
            prj.write_text("engineering fixture", encoding="utf-8")
            sha = hashlib.sha256(prj.read_bytes()).hexdigest()
            build = build_receipt(self.layout, sha)
            build["demo_runtime_snapshot_sha256"] = "0" * 64
            with self.assertRaisesRegex(
                ValueError,
                "runtime snapshot SHA-256 drift",
            ):
                verify_engineering_contam_runtime(
                    layout=self.layout,
                    prj_path=prj,
                    build_receipt=build,
                    binding_factory=FakeEngineeringCx,
                )

    def test_non_ready_build_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            prj = Path(tmp) / "engineering.prj"
            prj.write_text("engineering fixture", encoding="utf-8")
            sha = hashlib.sha256(prj.read_bytes()).hexdigest()
            build = build_receipt(self.layout, sha)
            build["status"] = "SOFTWARE_VERIFIED_ONLY"
            with self.assertRaisesRegex(
                ValueError,
                "not ENGINEERING_INPUTS_READY",
            ):
                verify_engineering_contam_runtime(
                    layout=self.layout,
                    prj_path=prj,
                    build_receipt=build,
                    binding_factory=FakeEngineeringCx,
                )


if __name__ == "__main__":
    unittest.main()
