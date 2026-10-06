from pathlib import Path
import unittest

from airtrajectory.contam_field_capture import compile_field_capture_bundle
from airtrajectory.contam_field_validation import (
    validate_field_validation_protocol,
)
from airtrajectory.layout import LayoutContract
from airtrajectory.physical import DriverCapabilities, PhysicalWindowDriver
from airtrajectory.trajectory import ActuatorFeedback, SensorReading
from airtrajectory.windowpilot_field_capture import (
    collect_windowpilot_field_capture,
)


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"


def protocol():
    return {
        "schema_version": "0.1",
        "protocol_id": "windowpilot-field-v1",
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
    return {
        "schema_version": "0.1",
        "status": "ENGINEERING_RUNTIME_VERIFIED",
        "topology_id": layout.topology_id,
        "runtime_receipt_sha256": "r" * 64,
        "steps": 2,
        "prediction_series": [
            {"step": 0, "simulation_time_s": 60.0},
            {"step": 1, "simulation_time_s": 120.0},
        ],
    }


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
                "id": "windowpilot-site-a",
                "model": "CWDS-CA01-windowpilot-stack",
                "serial": "SITE-A",
                "calibration_ref": "CAL-SITE-A",
            },
            "co2_zone_sources": {
                "living": "W1",
                "bedroom": "W2",
                "study": "W3",
            },
        },
    }


class FakeRealDriver(PhysicalWindowDriver):
    def __init__(self, opening_id, zone_value, clock):
        self.opening_id = opening_id
        self.zone_value = float(zone_value)
        self.clock = clock
        self.commands = 0

    def capabilities(self):
        return DriverCapabilities(
            transport="rs485-verified",
            simulated=False,
            measured_position=True,
            sensor_types=("co2", "rain"),
        )

    def read_sensors(self):
        return [
            SensorReading(
                sensor_id=f"co2-{self.opening_id}",
                sensor_type="co2",
                value=self.zone_value,
                unit="ppm",
                timestamp=self.clock["now"],
                quality="sensor-measured",
                provenance={
                    "product_key": "CWDS-CA01",
                    "property": "airSensor.co2",
                    "site_id": "site-a",
                    "room_id": self.opening_id,
                    "device_instance_id": f"sensor-{self.opening_id}",
                },
            )
        ]

    def physical_readiness(self):
        return {
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
            }
        }

    def set_position(self, opening_id, target_pct):
        self.commands += 1
        return ActuatorFeedback(
            actuator_id=opening_id,
            timestamp=self.clock["now"],
            measured_position_pct=float(target_pct),
            quality="measured",
        )


class WindowPilotFieldCaptureTests(unittest.TestCase):
    def setUp(self):
        self.layout = LayoutContract.from_file(LAYOUT)
        self.clock = {"now": 1760000000.0}
        self.drivers = {
            "W1": FakeRealDriver("W1", 1290.0, self.clock),
            "W2": FakeRealDriver("W2", 905.0, self.clock),
            "W3": FakeRealDriver("W3", 805.0, self.clock),
        }

    def sleep(self, seconds):
        self.clock["now"] += float(seconds)

    def test_read_only_windowpilot_capture_aligns_without_fake_door_measurements(self):
        raw = collect_windowpilot_field_capture(
            layout=self.layout,
            config=config(),
            drivers=self.drivers,
            protocol=protocol(),
            runtime_receipt=runtime(self.layout),
            validation_id="wp-run-001",
            sleep_fn=self.sleep,
            clock_fn=lambda: self.clock["now"],
        )
        self.assertEqual(len(raw["records"]), 12)
        self.assertFalse(
            any(
                row["target_id"] in {"D1", "D2"}
                for row in raw["records"]
            )
        )
        self.assertTrue(all(driver.commands == 0 for driver in self.drivers.values()))
        self.assertEqual(
            raw["windowpilot_capture_provenance"]["measured_openings"],
            ["W1", "W2", "W3"],
        )
        self.assertEqual(
            raw["windowpilot_capture_provenance"]["fixed_opening_assumptions"],
            {"D1": 100.0, "D2": 100.0},
        )
        aligned = compile_field_capture_bundle(
            layout=self.layout,
            runtime_receipt=runtime(self.layout),
            protocol=protocol(),
            capture=raw,
        )
        self.assertEqual(len(aligned["samples"]), 2)
        self.assertEqual(
            set(aligned["samples"][0]["opening_pct"]),
            {"W1", "W2", "W3"},
        )
        self.assertEqual(
            len(aligned["windowpilot_capture_provenance"]["adapter_receipt_sha256"]),
            64,
        )

    def test_simulated_windowpilot_endpoint_is_rejected(self):
        class Simulated(FakeRealDriver):
            def capabilities(self):
                return DriverCapabilities(
                    transport="mock",
                    simulated=True,
                    measured_position=False,
                    sensor_types=("co2",),
                )
        bad = dict(self.drivers)
        bad["W2"] = Simulated("W2", 905.0, self.clock)
        with self.assertRaisesRegex(RuntimeError, "W2 is simulated"):
            collect_windowpilot_field_capture(
                layout=self.layout,
                config=config(),
                drivers=bad,
                protocol=protocol(),
                runtime_receipt=runtime(self.layout),
                validation_id="wp-run-002",
                sleep_fn=self.sleep,
                clock_fn=lambda: self.clock["now"],
            )

    def test_fixed_opening_config_must_match_protocol(self):
        bad = config()
        bad["fixed_openings"]["D2"] = 50.0
        with self.assertRaisesRegex(ValueError, "do not match"):
            collect_windowpilot_field_capture(
                layout=self.layout,
                config=bad,
                drivers=self.drivers,
                protocol=protocol(),
                runtime_receipt=runtime(self.layout),
                validation_id="wp-run-003",
                sleep_fn=self.sleep,
                clock_fn=lambda: self.clock["now"],
            )

    def test_unprovenanced_co2_is_rejected(self):
        class NoProvenance(FakeRealDriver):
            def read_sensors(self):
                return [
                    SensorReading(
                        sensor_id="co2-bad",
                        sensor_type="co2",
                        value=900.0,
                        unit="ppm",
                        timestamp=self.clock["now"],
                        quality="measured",
                        provenance={},
                    )
                ]
        bad = dict(self.drivers)
        bad["W2"] = NoProvenance("W2", 905.0, self.clock)
        with self.assertRaisesRegex(RuntimeError, "lacks ThingModel/site provenance"):
            collect_windowpilot_field_capture(
                layout=self.layout,
                config=config(),
                drivers=bad,
                protocol=protocol(),
                runtime_receipt=runtime(self.layout),
                validation_id="wp-run-004",
                sleep_fn=self.sleep,
                clock_fn=lambda: self.clock["now"],
            )


if __name__ == "__main__":
    unittest.main()
