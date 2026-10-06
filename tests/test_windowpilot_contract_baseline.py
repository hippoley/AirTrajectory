import copy
import unittest

from airtrajectory.windowpilot_contract_baseline import (
    compare_windowpilot_contract_baseline,
    freeze_windowpilot_contract_baseline,
)
from airtrajectory.windowpilot_contract_probe import probe_windowpilot_config


def payloads(*, identity="a", site_id="site-a", transport="rs485", extra_state=False, co2=850.0, timestamp=1800000000.0):
    state = {
        "thing_model": {
            "sensors": {"co2_ppm": co2},
            "sensor_timestamps": {"co2_ppm": timestamp},
            "sensor_evidence": {
                "co2_ppm": {
                    "measured": True,
                    "timestamp": timestamp,
                    "source": "sensor-1",
                    "thingmodel_binding": {
                        "site_id": site_id,
                        "room_id": "living",
                    },
                }
            },
        }
    }
    if extra_state:
        state["thing_model"]["firmware"] = {"version": "2.0"}
    return {
        "/api/capabilities": {
            "execution": {
                "simulated": False,
                "measured_position": True,
                "transport": transport,
            }
        },
        "/api/physical-readiness": {
            "hardware_identity": {"identity_sha256": identity * 64},
            "latest_position_feedback": {
                "measured": True,
                "position_pct": 42.0,
                "timestamp": timestamp,
                "quality": "encoder-measured",
                "source": "encoder-1",
            },
        },
        "/api/state": state,
    }


def factory(mapping):
    def build(endpoint_id, spec):
        endpoint_payloads = mapping[endpoint_id]

        def request(method, path, body):
            return endpoint_payloads[path]

        return request

    return build


def report(mapping, *, clock=1800000001.0):
    config = {
        "windowpilot_endpoints": {
            endpoint_id: {"base_url": f"http://{endpoint_id.lower()}"}
            for endpoint_id in sorted(mapping)
        }
    }
    return probe_windowpilot_config(
        config=config,
        request_json_factory=factory(mapping),
        clock_fn=lambda: clock,
    )


class WindowPilotContractBaselineTests(unittest.TestCase):
    def baseline(self):
        first = report(
            {
                "W1": payloads(identity="1", site_id="site-a"),
                "W2": payloads(identity="2", site_id="site-a"),
            }
        )
        return freeze_windowpilot_contract_baseline(
            first,
            baseline_id="site-a-contract-v1",
        )

    def test_dynamic_measurements_and_timestamps_do_not_create_drift(self):
        baseline = self.baseline()
        current = report(
            {
                "W1": payloads(
                    identity="1",
                    site_id="site-a",
                    co2=975.0,
                    timestamp=1800000090.0,
                ),
                "W2": payloads(
                    identity="2",
                    site_id="site-a",
                    co2=640.0,
                    timestamp=1800000091.0,
                ),
            },
            clock=1800000100.0,
        )
        result = compare_windowpilot_contract_baseline(
            baseline=baseline,
            current_report=current,
        )
        self.assertEqual(result["status"], "MATCH")
        self.assertEqual(result["contract_drift_count"], 0)
        self.assertEqual(result["instance_drift_count"], 0)

    def test_shape_change_is_contract_drift(self):
        baseline = self.baseline()
        current = report(
            {
                "W1": payloads(
                    identity="1",
                    site_id="site-a",
                    extra_state=True,
                ),
                "W2": payloads(identity="2", site_id="site-a"),
            }
        )
        result = compare_windowpilot_contract_baseline(
            baseline=baseline,
            current_report=current,
        )
        self.assertEqual(result["status"], "DRIFT")
        self.assertGreater(result["contract_drift_count"], 0)
        self.assertTrue(
            any(
                row["category"] == "CONTRACT_DRIFT"
                and "endpoint_shapes.state" in row["path"]
                for row in result["drifts"]
            )
        )

    def test_transport_change_is_contract_drift(self):
        baseline = self.baseline()
        current = report(
            {
                "W1": payloads(
                    identity="1",
                    site_id="site-a",
                    transport="mqtt",
                ),
                "W2": payloads(identity="2", site_id="site-a"),
            }
        )
        result = compare_windowpilot_contract_baseline(
            baseline=baseline,
            current_report=current,
        )
        self.assertTrue(
            any(
                row["category"] == "CONTRACT_DRIFT"
                and row["path"] == "contract.execution.transport"
                for row in result["drifts"]
            )
        )

    def test_hardware_identity_and_site_change_are_instance_drift(self):
        baseline = self.baseline()
        current = report(
            {
                "W1": payloads(identity="9", site_id="site-b"),
                "W2": payloads(identity="2", site_id="site-a"),
            }
        )
        result = compare_windowpilot_contract_baseline(
            baseline=baseline,
            current_report=current,
        )
        self.assertEqual(result["status"], "DRIFT")
        paths = {
            row["path"]
            for row in result["drifts"]
            if row["category"] == "INSTANCE_DRIFT"
        }
        self.assertIn("instance.hardware_identity_sha256", paths)
        self.assertIn("instance.co2_site_id", paths)

    def test_endpoint_addition_is_instance_drift(self):
        baseline = self.baseline()
        current = report(
            {
                "W1": payloads(identity="1", site_id="site-a"),
                "W2": payloads(identity="2", site_id="site-a"),
                "W3": payloads(identity="3", site_id="site-a"),
            }
        )
        result = compare_windowpilot_contract_baseline(
            baseline=baseline,
            current_report=current,
        )
        self.assertTrue(
            any(
                row["endpoint_id"] == "W3"
                and row["category"] == "INSTANCE_DRIFT"
                for row in result["drifts"]
            )
        )

    def test_only_compatible_probe_can_be_frozen(self):
        partial = report(
            {
                "W1": payloads(
                    identity="1",
                    site_id="site-a",
                    transport="",
                )
            }
        )
        self.assertEqual(partial["status"], "PARTIAL")
        with self.assertRaisesRegex(ValueError, "fully COMPATIBLE"):
            freeze_windowpilot_contract_baseline(
                partial,
                baseline_id="bad",
            )

    def test_tampered_baseline_is_rejected(self):
        baseline = self.baseline()
        baseline["endpoints"]["W1"]["instance"][
            "hardware_identity_sha256"
        ] = "f" * 64
        current = report(
            {
                "W1": payloads(identity="1", site_id="site-a"),
                "W2": payloads(identity="2", site_id="site-a"),
            }
        )
        with self.assertRaisesRegex(ValueError, "baseline SHA-256"):
            compare_windowpilot_contract_baseline(
                baseline=baseline,
                current_report=current,
            )

    def test_tampered_probe_is_rejected(self):
        baseline = self.baseline()
        current = report(
            {
                "W1": payloads(identity="1", site_id="site-a"),
                "W2": payloads(identity="2", site_id="site-a"),
            }
        )
        current["endpoints"]["W1"]["observed"]["co2_site_id"] = "site-z"
        with self.assertRaisesRegex(ValueError, "config probe receipt"):
            compare_windowpilot_contract_baseline(
                baseline=baseline,
                current_report=current,
            )


if __name__ == "__main__":
    unittest.main()
