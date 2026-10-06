import hashlib
import json
from pathlib import Path
import unittest

from airtrajectory.layout import LayoutContract
from airtrajectory.physical import DriverCapabilities, PhysicalWindowDriver
from airtrajectory.trajectory import ActuatorFeedback, SensorReading
from airtrajectory.windowpilot_validation_preflight import (
    preflight_windowpilot_field_validation,
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
        "protocol_id": "wp-preflight-v1",
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
                "W1": 75.0, "W2": 35.0, "W3": 0.0,
                "D1": 100.0, "D2": 100.0,
            },
            "path_flow_kg_s": {},
        },
        {
            "step": 1,
            "simulation_time_s": 120.0,
            "co2_ppm": {"living": 1290.0, "bedroom": 905.0, "study": 805.0},
            "opening_pct": {
                "W1": 75.0, "W2": 35.0, "W3": 0.0,
                "D1": 100.0, "D2": 100.0,
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
            "max_sample_age_s": 10.0,
            "max_future_skew_s": 2.0,
        },
    }


class FakeDriver(PhysicalWindowDriver):
    def __init__(self, opening_id, co2, clock, site_id="site-a"):
        self.opening_id = opening_id
        self.co2 = float(co2)
        self.clock = clock
        self.site_id = site_id
        self.commands = 0
        self.sensor_offset_s = 0.0
        self.position_offset_s = 0.0

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
                timestamp=self.clock["now"] + self.sensor_offset_s,
                quality="sensor-measured",
                provenance={
                    "site_id": self.site_id,
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
                "timestamp": self.clock["now"] + self.position_offset_s,
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


class WindowPilotValidationPreflightTests(unittest.TestCase):
    def setUp(self):
        self.layout = LayoutContract.from_file(LAYOUT)
        self.clock = {"now": 1800000000.0}
        self.drivers = {
            "W1": FakeDriver("W1", 1290.0, self.clock),
            "W2": FakeDriver("W2", 905.0, self.clock),
            "W3": FakeDriver("W3", 805.0, self.clock),
        }

    def run_preflight(self, cfg=None, drivers=None):
        return preflight_windowpilot_field_validation(
            layout=self.layout,
            config=cfg or config(),
            drivers=drivers or self.drivers,
            protocol=protocol(),
            runtime_receipt=runtime(self.layout),
            clock_fn=lambda: self.clock["now"],
        )

    def test_preflight_passes_read_only_and_returns_hash_receipt(self):
        receipt = self.run_preflight()
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["physical_site_id"], "site-a")
        self.assertEqual(receipt["actuator_writes"], 0)
        self.assertEqual(len(receipt["preflight_receipt_sha256"]), 64)
        self.assertTrue(
            all(driver.commands == 0 for driver in self.drivers.values())
        )

    def test_tampered_runtime_receipt_is_rejected_before_sampling(self):
        run = runtime(self.layout)
        run["prediction_series"][0]["co2_ppm"]["living"] += 500.0
        with self.assertRaisesRegex(
            ValueError,
            "runtime receipt SHA-256 integrity",
        ):
            preflight_windowpilot_field_validation(
                layout=self.layout,
                config=config(),
                drivers=self.drivers,
                protocol=protocol(),
                runtime_receipt=run,
                clock_fn=lambda: self.clock["now"],
            )

    def test_stale_co2_is_rejected_before_sampling(self):
        self.drivers["W2"].sensor_offset_s = -30.0
        with self.assertRaisesRegex(RuntimeError, "CO2 reading is stale"):
            self.run_preflight()

    def test_future_position_timestamp_is_rejected(self):
        self.drivers["W1"].position_offset_s = 5.0
        with self.assertRaisesRegex(
            RuntimeError,
            "position timestamp is too far in the future",
        ):
            self.run_preflight()

    def test_template_source_placeholder_is_rejected(self):
        cfg = config()
        cfg["field_capture"]["source"]["serial"] = "replace-with-system-serial"
        with self.assertRaisesRegex(ValueError, "template placeholder"):
            self.run_preflight(cfg=cfg)

    def test_cross_site_endpoint_is_rejected(self):
        bad = dict(self.drivers)
        bad["W3"] = FakeDriver(
            "W3",
            805.0,
            self.clock,
            site_id="site-b",
        )
        with self.assertRaisesRegex(RuntimeError, "multiple physical sites"):
            self.run_preflight(drivers=bad)


if __name__ == "__main__":
    unittest.main()
