import hashlib
import json
from pathlib import Path
import unittest

from airtrajectory.layout import LayoutContract
from airtrajectory.physical import DriverCapabilities, PhysicalWindowDriver
from airtrajectory.trajectory import ActuatorFeedback, SensorReading
from airtrajectory.windowpilot_validation_pipeline import (
    run_windowpilot_field_validation,
)


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"


def sha(payload):
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def protocol():
    return {
        "schema_version": "0.1",
        "protocol_id": "wp-pipeline-v1",
        "topology_id": "demo.fixed-three-room.v1",
        "min_samples": 2,
        "co2": {
            "zones": ["living", "bedroom", "study"],
            "rmse_ppm_max": 50.0,
            "mae_ppm_max": 40.0,
        },
        "opening_position": {
            "openings": ["W1", "W2", "W3"],
            "fixed_openings": {"D1": 100.0, "D2": 100.0},
            "mae_pct_max": 2.0,
        },
        "alignment": {
            "sampling_interval_s": 60.0,
            "max_skew_s": 5.0,
            "aggregation": "nearest",
            "accepted_qualities": ["measured"],
        },
        "approval": {
            "approved": True,
            "approved_by": "Engineer A",
            "approved_role": "HVAC validation lead",
            "approved_at": "2026-10-06T07:00:00Z",
        },
    }


def runtime(layout):
    series = [
        {
            "step": 0,
            "simulation_time_s": 60.0,
            "co2_ppm": {"living": 1290.0, "bedroom": 905.0, "study": 805.0},
            "opening_pct": {
                "W1": 75.0, "W2": 35.0, "W3": 0.0, "D1": 100.0, "D2": 100.0
            },
            "path_flow_kg_s": {},
        },
        {
            "step": 1,
            "simulation_time_s": 120.0,
            "co2_ppm": {"living": 1290.0, "bedroom": 905.0, "study": 805.0},
            "opening_pct": {
                "W1": 75.0, "W2": 35.0, "W3": 0.0, "D1": 100.0, "D2": 100.0
            },
            "path_flow_kg_s": {},
        },
    ]
    payload = {
        "schema_version": "0.1",
        "verifier": "contam-engineering-runtime-verifier",
        "status": "ENGINEERING_RUNTIME_VERIFIED",
        "topology_id": layout.topology_id,
        "layout_contract_sha256": layout.sha256(),
        "runtime_verified": True,
        "engineering_model_verified": True,
        "field_validation_verified": False,
        "engineering_truth": False,
        "steps": 2,
        "prediction_series": series,
        "prediction_series_sha256": sha(series),
    }
    return {**payload, "runtime_receipt_sha256": sha(payload)}


def config():
    return {
        "schema_version": "0.1",
        "topology_id": "demo.fixed-three-room.v1",
        "windowpilot_endpoints": {
            "W1": {"base_url": "http://w1"},
            "W2": {"base_url": "http://w2"},
            "W3": {"base_url": "http://w3"},
        },
        "fixed_openings": {"D1": 100.0, "D2": 100.0},
        "field_capture": {
            "source": {
                "kind": "site-sensor-system",
                "id": "site-a",
                "model": "CWDS-CA01-windowpilot-stack",
                "serial": "SITE-A",
                "calibration_ref": "CAL-A",
            },
            "co2_zone_sources": {
                "living": "W1",
                "bedroom": "W2",
                "study": "W3",
            },
        },
    }


class FakeDriver(PhysicalWindowDriver):
    def __init__(self, opening_id, co2, clock):
        self.opening_id = opening_id
        self.co2 = co2
        self.clock = clock
        self.commands = 0

    def capabilities(self):
        return DriverCapabilities(
            "rs485-verified",
            False,
            True,
            ("co2", "rain"),
        )

    def read_sensors(self):
        return [
            SensorReading(
                sensor_id=f"co2-{self.opening_id}",
                sensor_type="co2",
                value=self.co2,
                unit="ppm",
                timestamp=self.clock["now"],
                quality="sensor-measured",
                provenance={
                    "site_id": "site-a",
                    "product_key": "CWDS-CA01",
                    "property": "airSensor.co2",
                    "device_instance_id": f"sensor-{self.opening_id}",
                },
            )
        ]

    def physical_readiness(self):
        return {
            "hardware_identity": {
                "identity_sha256": {
                    "W1": "1" * 64,
                    "W2": "2" * 64,
                    "W3": "3" * 64,
                }[self.opening_id],
            },
            "latest_position_feedback": {
                "position_pct": {
                    "W1": 75.0,
                    "W2": 35.0,
                    "W3": 0.0,
                }[self.opening_id],
                "timestamp": self.clock["now"],
                "measured": True,
                "quality": "encoder-measured",
                "source": f"encoder-{self.opening_id}",
            },
        }

    def set_position(self, opening_id, target_pct):
        self.commands += 1
        return ActuatorFeedback(
            actuator_id=opening_id,
            timestamp=self.clock["now"],
            measured_position_pct=float(target_pct),
            quality="measured",
        )


class WindowPilotValidationPipelineTests(unittest.TestCase):
    def test_one_command_windowpilot_pipeline_passes_without_actuation(self):
        layout = LayoutContract.from_file(LAYOUT)
        clock = {"now": 1800000000.0}
        drivers = {
            "W1": FakeDriver("W1", 1290.0, clock),
            "W2": FakeDriver("W2", 905.0, clock),
            "W3": FakeDriver("W3", 805.0, clock),
        }

        def sleep(seconds):
            clock["now"] += float(seconds)

        receipt, capture, aligned = run_windowpilot_field_validation(
            layout=layout,
            config=config(),
            drivers=drivers,
            protocol=protocol(),
            runtime_receipt=runtime(layout),
            validation_id="wp-pipeline-run-001",
            sleep_fn=sleep,
            clock_fn=lambda: clock["now"],
        )

        self.assertEqual(receipt["status"], "FIELD_VALIDATION_PASSED")
        self.assertTrue(receipt["field_validation_verified"])
        self.assertTrue(receipt["engineering_truth"])
        self.assertTrue(all(driver.commands == 0 for driver in drivers.values()))
        self.assertEqual(len(capture["records"]), 12)
        self.assertEqual(len(aligned["samples"]), 2)
        self.assertEqual(len(receipt["pipeline_receipt_sha256"]), 64)
        self.assertEqual(
            receipt["windowpilot_capture_sha256"],
            aligned["windowpilot_capture_provenance"][
                "adapter_receipt_sha256"
            ],
        )


if __name__ == "__main__":
    unittest.main()
