import copy
import hashlib
import json
import unittest

from airtrajectory.windowpilot_contract_baseline import (
    compare_windowpilot_contract_baseline,
    freeze_windowpilot_contract_baseline,
)
from airtrajectory.windowpilot_contract_probe import (
    probe_windowpilot_config,
)
from airtrajectory.windowpilot_startup_bundle import (
    build_windowpilot_startup_bundle,
    verify_windowpilot_startup_bundle,
)


def sha(payload):
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def payloads(endpoint_id):
    identity = {"W1": "1", "W2": "2", "W3": "3"}[endpoint_id]
    room = {"W1": "living", "W2": "bedroom", "W3": "study"}[endpoint_id]
    co2 = {"W1": 1290.0, "W2": 905.0, "W3": 805.0}[endpoint_id]
    return {
        "/api/capabilities": {
            "execution": {
                "simulated": False,
                "measured_position": True,
                "transport": "rs485-verified",
            }
        },
        "/api/physical-readiness": {
            "hardware_identity": {
                "identity_sha256": identity * 64,
            },
            "latest_position_feedback": {
                "measured": True,
                "position_pct": {
                    "W1": 75.0,
                    "W2": 35.0,
                    "W3": 0.0,
                }[endpoint_id],
                "timestamp": 1800000000.0,
                "quality": "encoder-measured",
                "source": f"encoder-{endpoint_id}",
            },
        },
        "/api/state": {
            "thing_model": {
                "sensors": {"co2_ppm": co2},
                "sensor_timestamps": {
                    "co2_ppm": 1800000000.0,
                },
                "sensor_evidence": {
                    "co2_ppm": {
                        "measured": True,
                        "timestamp": 1800000000.0,
                        "source": f"co2-{endpoint_id}",
                        "thingmodel_binding": {
                            "site_id": "site-a",
                            "room_id": room,
                        },
                    }
                },
            }
        },
    }


def probe_report():
    config = {
        "windowpilot_endpoints": {
            "W1": {"base_url": "http://w1"},
            "W2": {"base_url": "http://w2"},
            "W3": {"base_url": "http://w3"},
        }
    }

    def factory(endpoint_id, spec):
        fixture = payloads(endpoint_id)

        def request(method, path, body):
            return fixture[path]

        return request

    return probe_windowpilot_config(
        config=config,
        request_json_factory=factory,
        clock_fn=lambda: 1800000001.0,
    )


def artifacts():
    probe = probe_report()
    baseline = freeze_windowpilot_contract_baseline(
        probe,
        baseline_id="site-a-windowpilot-v1",
    )
    comparison = compare_windowpilot_contract_baseline(
        baseline=baseline,
        current_report=probe,
    )
    preflight_payload = {
        "schema_version": "0.1",
        "preflight": "windowpilot-field-validation-preflight-v1",
        "status": "PASS",
        "topology_id": "demo.fixed-three-room.v1",
        "runtime_receipt_sha256": "r" * 64,
        "protocol_sha256": "p" * 64,
        "physical_site_id": "site-a",
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
        "measured_openings": ["W1", "W2", "W3"],
        "fixed_opening_assumptions": {
            "D1": 100.0,
            "D2": 100.0,
        },
        "max_sample_age_s": 10.0,
        "max_future_skew_s": 2.0,
        "checked_at": 1800000001.0,
        "endpoints": {
            endpoint_id: {
                "capabilities": {
                    "transport": "rs485-verified",
                    "simulated": False,
                    "measured_position": True,
                    "sensor_types": ["co2", "rain"],
                },
                "hardware_identity_sha256": identity * 64,
                "position_feedback": {
                    "position_pct": {
                        "W1": 75.0,
                        "W2": 35.0,
                        "W3": 0.0,
                    }[endpoint_id],
                    "timestamp": 1800000000.0,
                    "age_s": 1.0,
                    "quality": "encoder-measured",
                    "source": f"encoder-{endpoint_id}",
                },
            }
            for endpoint_id, identity in (
                ("W1", "1"),
                ("W2", "2"),
                ("W3", "3"),
            )
        },
        "co2_by_endpoint": {
            endpoint_id: {
                "sensor_id": f"co2-{endpoint_id}",
                "value_ppm": value,
                "timestamp": 1800000000.0,
                "age_s": 1.0,
                "quality": "sensor-measured",
                "site_id": "site-a",
                "provenance_sha256": endpoint_id.lower().ljust(64, "0"),
            }
            for endpoint_id, value in (
                ("W1", 1290.0),
                ("W2", 905.0),
                ("W3", 805.0),
            )
        },
        "actuator_writes": 0,
    }
    preflight = {
        **preflight_payload,
        "preflight_receipt_sha256": sha(preflight_payload),
    }
    return baseline, probe, comparison, preflight


class WindowPilotStartupBundleTests(unittest.TestCase):
    def test_build_and_offline_replay_verify(self):
        baseline, probe, comparison, preflight = artifacts()
        bundle = build_windowpilot_startup_bundle(
            baseline=baseline,
            probe_report=probe,
            comparison=comparison,
            preflight=preflight,
            bundle_id="site-a-startup-001",
        )
        self.assertEqual(
            bundle["status"],
            "VERIFIED_READ_ONLY_STARTUP",
        )
        self.assertEqual(bundle["physical_site_id"], "site-a")
        self.assertEqual(
            bundle["endpoint_ids"],
            ["W1", "W2", "W3"],
        )
        self.assertEqual(bundle["actuator_writes"], 0)
        self.assertEqual(len(bundle["startup_bundle_sha256"]), 64)

        replay = verify_windowpilot_startup_bundle(
            bundle=bundle,
            baseline=baseline,
            probe_report=probe,
            comparison=comparison,
            preflight=preflight,
        )
        self.assertEqual(replay["status"], "VERIFIED")
        self.assertEqual(replay["actuator_writes"], 0)
        self.assertEqual(len(replay["verification_sha256"]), 64)

    def test_resigned_fake_comparison_is_rejected_by_exact_replay(self):
        baseline, probe, comparison, preflight = artifacts()
        fake = copy.deepcopy(comparison)
        fake["contract_drift_count"] = 1
        fake["drifts"] = [{
            "endpoint_id": "W1",
            "category": "CONTRACT_DRIFT",
            "path": "contract.fake",
            "expected": "x",
            "actual": "y",
        }]
        payload = dict(fake)
        payload.pop("comparison_sha256", None)
        fake["comparison_sha256"] = sha(payload)

        with self.assertRaisesRegex(
            ValueError,
            "does not replay exactly",
        ):
            build_windowpilot_startup_bundle(
                baseline=baseline,
                probe_report=probe,
                comparison=fake,
                preflight=preflight,
                bundle_id="site-a-startup-fake-comparison",
            )

    def test_resigned_preflight_identity_drift_is_rejected(self):
        baseline, probe, comparison, preflight = artifacts()
        bad = copy.deepcopy(preflight)
        bad["endpoints"]["W1"]["hardware_identity_sha256"] = "9" * 64
        payload = dict(bad)
        payload.pop("preflight_receipt_sha256", None)
        bad["preflight_receipt_sha256"] = sha(payload)

        with self.assertRaisesRegex(
            ValueError,
            "preflight hardware identity drift",
        ):
            build_windowpilot_startup_bundle(
                baseline=baseline,
                probe_report=probe,
                comparison=comparison,
                preflight=bad,
                bundle_id="site-a-startup-identity-drift",
            )

    def test_preflight_actuator_write_is_rejected(self):
        baseline, probe, comparison, preflight = artifacts()
        bad = copy.deepcopy(preflight)
        bad["actuator_writes"] = 1
        payload = dict(bad)
        payload.pop("preflight_receipt_sha256", None)
        bad["preflight_receipt_sha256"] = sha(payload)

        with self.assertRaisesRegex(
            ValueError,
            "zero actuator writes",
        ):
            build_windowpilot_startup_bundle(
                baseline=baseline,
                probe_report=probe,
                comparison=comparison,
                preflight=bad,
                bundle_id="site-a-startup-actuation",
            )

    def test_preflight_site_drift_is_rejected(self):
        baseline, probe, comparison, preflight = artifacts()
        bad = copy.deepcopy(preflight)
        bad["physical_site_id"] = "site-b"
        payload = dict(bad)
        payload.pop("preflight_receipt_sha256", None)
        bad["preflight_receipt_sha256"] = sha(payload)

        with self.assertRaisesRegex(
            ValueError,
            "physical_site_id does not match baseline",
        ):
            build_windowpilot_startup_bundle(
                baseline=baseline,
                probe_report=probe,
                comparison=comparison,
                preflight=bad,
                bundle_id="site-a-startup-site-drift",
            )

    def test_tampered_bundle_is_rejected_by_offline_verifier(self):
        baseline, probe, comparison, preflight = artifacts()
        bundle = build_windowpilot_startup_bundle(
            baseline=baseline,
            probe_report=probe,
            comparison=comparison,
            preflight=preflight,
            bundle_id="site-a-startup-002",
        )
        bundle["physical_site_id"] = "site-z"

        with self.assertRaisesRegex(
            ValueError,
            "startup bundle SHA-256 integrity",
        ):
            verify_windowpilot_startup_bundle(
                bundle=bundle,
                baseline=baseline,
                probe_report=probe,
                comparison=comparison,
                preflight=preflight,
            )

    def test_endpoint_set_mismatch_is_rejected(self):
        baseline, probe, comparison, preflight = artifacts()
        bad = copy.deepcopy(preflight)
        del bad["endpoints"]["W3"]
        payload = dict(bad)
        payload.pop("preflight_receipt_sha256", None)
        bad["preflight_receipt_sha256"] = sha(payload)

        with self.assertRaisesRegex(
            ValueError,
            "endpoint sets do not match",
        ):
            build_windowpilot_startup_bundle(
                baseline=baseline,
                probe_report=probe,
                comparison=comparison,
                preflight=bad,
                bundle_id="site-a-startup-endpoint-drift",
            )


if __name__ == "__main__":
    unittest.main()
