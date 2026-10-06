import unittest

from airtrajectory.windowpilot_contract_probe import (
    probe_windowpilot_config,
    probe_windowpilot_http_contract,
)


def compatible_payloads():
    return {
        "/api/capabilities": {
            "execution": {
                "simulated": False,
                "measured_position": True,
                "transport": "rs485",
            }
        },
        "/api/physical-readiness": {
            "hardware_identity": {
                "identity_sha256": "a" * 64,
            },
            "latest_position_feedback": {
                "measured": True,
                "position_pct": 42.0,
                "timestamp": 1800000000.0,
                "quality": "encoder-measured",
                "source": "encoder-1",
            },
        },
        "/api/state": {
            "thing_model": {
                "sensors": {
                    "co2_ppm": 850.0,
                },
                "sensor_timestamps": {
                    "co2_ppm": 1800000000.0,
                },
                "sensor_evidence": {
                    "co2_ppm": {
                        "measured": True,
                        "timestamp": 1800000000.0,
                        "source": "sensor-1",
                        "thingmodel_binding": {
                            "site_id": "site-a",
                            "room_id": "living",
                        },
                    }
                },
            }
        },
    }


def request_from(payloads, calls):
    def request(method, path, payload):
        calls.append((method, path, payload))
        if path not in payloads:
            raise RuntimeError("missing fixture endpoint")
        value = payloads[path]
        if isinstance(value, Exception):
            raise value
        return value

    return request


class WindowPilotContractProbeTests(unittest.TestCase):
    def test_complete_contract_is_compatible_and_read_only(self):
        calls = []
        report = probe_windowpilot_http_contract(
            base_url="http://windowpilot",
            request_json=request_from(compatible_payloads(), calls),
            clock_fn=lambda: 1800000001.0,
        )
        self.assertEqual(report["status"], "COMPATIBLE")
        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["warning_count"], 0)
        self.assertEqual(report["actuator_writes"], 0)
        self.assertEqual(
            [call[:2] for call in calls],
            [
                ("GET", "/api/capabilities"),
                ("GET", "/api/physical-readiness"),
                ("GET", "/api/state"),
            ],
        )
        self.assertTrue(
            all(call[0] == "GET" for call in calls)
        )
        self.assertEqual(len(report["probe_receipt_sha256"]), 64)
        self.assertNotIn(
            "payload",
            report["endpoints"]["state"],
        )
        self.assertEqual(
            len(report["endpoints"]["state"]["payload_sha256"]),
            64,
        )

    def test_missing_identity_and_site_binding_is_incompatible(self):
        payloads = compatible_payloads()
        payloads["/api/physical-readiness"] = {
            "latest_position_feedback": {
                "measured": True,
                "position_pct": 42.0,
                "timestamp": 1800000000.0,
            }
        }
        payloads["/api/state"]["thing_model"]["sensor_evidence"]["co2_ppm"][
            "thingmodel_binding"
        ] = {}
        report = probe_windowpilot_http_contract(
            base_url="http://windowpilot",
            request_json=request_from(payloads, []),
        )
        self.assertEqual(report["status"], "INCOMPATIBLE")
        codes = {row["code"] for row in report["findings"]}
        self.assertIn("HARDWARE_IDENTITY_MISSING", codes)
        self.assertIn("CO2_SITE_BINDING_MISSING", codes)

    def test_missing_transport_is_partial_not_hard_failure(self):
        payloads = compatible_payloads()
        del payloads["/api/capabilities"]["execution"]["transport"]
        report = probe_windowpilot_http_contract(
            base_url="http://windowpilot",
            request_json=request_from(payloads, []),
        )
        self.assertEqual(report["status"], "PARTIAL")
        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["warning_count"], 1)
        self.assertEqual(
            report["findings"][0]["code"],
            "TRANSPORT_MISSING",
        )

    def test_unreachable_state_still_reports_other_endpoint_findings(self):
        payloads = compatible_payloads()
        payloads["/api/state"] = RuntimeError("state endpoint down")
        payloads["/api/capabilities"]["execution"]["simulated"] = True
        report = probe_windowpilot_http_contract(
            base_url="http://windowpilot",
            request_json=request_from(payloads, []),
        )
        self.assertEqual(report["status"], "INCOMPATIBLE")
        codes = {row["code"] for row in report["findings"]}
        self.assertIn("STATE_UNREACHABLE", codes)
        self.assertIn("EXECUTION_NOT_CONFIRMED_PHYSICAL", codes)

    def test_config_probe_collects_all_endpoints(self):
        config = {
            "windowpilot_endpoints": {
                "W1": {"base_url": "http://w1"},
                "W2": {"base_url": "http://w2"},
            }
        }

        def factory(endpoint_id, spec):
            payloads = compatible_payloads()
            if endpoint_id == "W2":
                payloads["/api/physical-readiness"] = {}
            return request_from(payloads, [])

        report = probe_windowpilot_config(
            config=config,
            request_json_factory=factory,
        )
        self.assertEqual(report["status"], "INCOMPATIBLE")
        self.assertEqual(report["endpoint_count"], 2)
        self.assertEqual(
            report["endpoints"]["W1"]["status"],
            "COMPATIBLE",
        )
        self.assertEqual(
            report["endpoints"]["W2"]["status"],
            "INCOMPATIBLE",
        )
        self.assertEqual(report["actuator_writes"], 0)
        self.assertEqual(
            len(report["config_probe_receipt_sha256"]),
            64,
        )


if __name__ == "__main__":
    unittest.main()
