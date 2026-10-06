import copy
import unittest

from airtrajectory.demo_physical_config import build_windowpilot_drivers
from airtrajectory.windowpilot_contract_baseline import (
    compare_windowpilot_contract_baseline,
    freeze_windowpilot_contract_baseline,
)
from airtrajectory.windowpilot_contract_mapping import (
    apply_windowpilot_contract_mapping,
    build_windowpilot_response_adapter,
    validate_windowpilot_contract_mapping,
)
from airtrajectory.windowpilot_contract_probe import probe_windowpilot_config


H = "a" * 64


def profile(profile_id="vendor-v1"):
    return {
        "schema_version": "0.1",
        "profile_id": profile_id,
        "endpoints": {
            "/api/capabilities": {
                "execution.simulated": {
                    "path": "runtime.isSimulated",
                    "coerce": "bool",
                },
                "execution.measured_position": {
                    "path": "runtime.position.measured",
                    "coerce": "bool",
                },
                "execution.transport": {
                    "path": "runtime.transport",
                    "coerce": "string",
                },
            },
            "/api/physical-readiness": {
                "hardware_identity.identity_sha256": "device.identity.sha256",
                "latest_position_feedback.measured": {
                    "path": "position.measured",
                    "coerce": "bool",
                },
                "latest_position_feedback.position_pct": {
                    "path": "position.positionPercent",
                    "coerce": "float",
                },
                "latest_position_feedback.timestamp": {
                    "path": "position.ts",
                    "coerce": "float",
                },
                "latest_position_feedback.quality": {
                    "path": "position.quality",
                    "coerce": "string",
                },
                "latest_position_feedback.source": {
                    "path": "position.source",
                    "coerce": "string",
                },
            },
            "/api/state": {
                "thing_model.sensors.co2_ppm": {
                    "path": "telemetry.co2.value",
                    "coerce": "float",
                },
                "thing_model.sensor_timestamps.co2_ppm": {
                    "path": "telemetry.co2.ts",
                    "coerce": "float",
                },
                "thing_model.sensor_evidence.co2_ppm.measured": {
                    "path": "telemetry.co2.measured",
                    "coerce": "bool",
                },
                "thing_model.sensor_evidence.co2_ppm.timestamp": {
                    "path": "telemetry.co2.ts",
                    "coerce": "float",
                },
                "thing_model.sensor_evidence.co2_ppm.source": {
                    "path": "telemetry.co2.source",
                    "coerce": "string",
                },
                "thing_model.sensor_evidence.co2_ppm.quality": {
                    "path": "telemetry.co2.quality",
                    "coerce": "string",
                },
                "thing_model.sensor_evidence.co2_ppm.thingmodel_binding.product_model": "telemetry.co2.binding.productModel",
                "thing_model.sensor_evidence.co2_ppm.thingmodel_binding.product_key": "telemetry.co2.binding.productKey",
                "thing_model.sensor_evidence.co2_ppm.thingmodel_binding.device_id": "telemetry.co2.binding.deviceId",
                "thing_model.sensor_evidence.co2_ppm.thingmodel_binding.property": "telemetry.co2.binding.property",
                "thing_model.sensor_evidence.co2_ppm.thingmodel_binding.source_sha256": "telemetry.co2.binding.sourceSha256",
                "thing_model.sensor_evidence.co2_ppm.thingmodel_binding.source_bundle_sha256": "telemetry.co2.binding.sourceBundleSha256",
                "thing_model.sensor_evidence.co2_ppm.thingmodel_binding.registry_sha256": "telemetry.co2.binding.registrySha256",
                "thing_model.sensor_evidence.co2_ppm.thingmodel_binding.contract_sha256": "telemetry.co2.binding.contractSha256",
                "thing_model.sensor_evidence.co2_ppm.thingmodel_binding.site_id": "telemetry.co2.binding.siteId",
                "thing_model.sensor_evidence.co2_ppm.thingmodel_binding.site_instance_id": "telemetry.co2.binding.siteInstanceId",
                "thing_model.sensor_evidence.co2_ppm.thingmodel_binding.site_manifest_sha256": "telemetry.co2.binding.siteManifestSha256",
                "thing_model.sensor_evidence.co2_ppm.thingmodel_binding.site_contract_sha256": "telemetry.co2.binding.siteContractSha256",
            },
        },
    }


def payloads():
    return {
        "/api/capabilities": {
            "runtime": {
                "isSimulated": "false",
                "position": {"measured": "true"},
                "transport": "rs485-vendor",
            },
            "private": {"tokenHint": "must-not-pass-through"},
        },
        "/api/physical-readiness": {
            "device": {"identity": {"sha256": "1" * 64}},
            "position": {
                "measured": True,
                "positionPercent": "42.5",
                "ts": "1800000000",
                "quality": "encoder",
                "source": "enc-1",
            },
        },
        "/api/state": {
            "telemetry": {
                "co2": {
                    "value": "850",
                    "ts": "1800000000",
                    "measured": True,
                    "source": "co2-device-1",
                    "quality": "measured",
                    "binding": {
                        "productModel": "CWDS-CA01",
                        "productKey": "cwds-ca01",
                        "deviceId": "sensor-1",
                        "property": "airSensor.co2",
                        "sourceSha256": H,
                        "sourceBundleSha256": H,
                        "registrySha256": H,
                        "contractSha256": H,
                        "siteId": "site-a",
                        "siteInstanceId": "site-instance-a",
                        "siteManifestSha256": H,
                        "siteContractSha256": H,
                    },
                }
            }
        },
    }


def config(mapping_profile=None):
    p = validate_windowpilot_contract_mapping(
        mapping_profile or profile()
    )
    return {
        "schema_version": "0.1",
        "windowpilot_endpoints": {
            "W1": {
                "base_url": "http://w1",
                "contract_mapping_profile": "vendor",
            }
        },
        "contract_mapping_profiles": {"vendor": p},
        "fixed_openings": {},
    }


def request_factory(endpoint_id, spec):
    data = payloads()

    def request(method, path, body):
        if method == "POST":
            return {"ok": True, "echo": body}
        return copy.deepcopy(data[path])

    return request


class WindowPilotContractMappingTests(unittest.TestCase):
    def test_profile_normalization_is_idempotent(self):
        first = validate_windowpilot_contract_mapping(profile())
        second = validate_windowpilot_contract_mapping(first)
        self.assertEqual(first, second)
        self.assertEqual(len(first["profile_sha256"]), 64)

    def test_vendor_payload_maps_to_canonical_without_private_pass_through(self):
        mapped = apply_windowpilot_contract_mapping(
            profile=profile(),
            endpoint="/api/capabilities",
            payload=payloads()["/api/capabilities"],
        )
        self.assertEqual(
            mapped,
            {
                "execution": {
                    "simulated": False,
                    "measured_position": True,
                    "transport": "rs485-vendor",
                }
            },
        )
        self.assertNotIn("private", mapped)

    def test_missing_required_vendor_field_fails_closed(self):
        raw = payloads()["/api/physical-readiness"]
        del raw["position"]["positionPercent"]
        with self.assertRaisesRegex(
            ValueError,
            "missing required source fields",
        ):
            apply_windowpilot_contract_mapping(
                profile=profile(),
                endpoint="/api/physical-readiness",
                payload=raw,
            )

    def test_driver_reads_real_co2_through_mapping_and_lineage_gate(self):
        drivers = build_windowpilot_drivers(
            config(),
            request_json_factory=request_factory,
        )
        driver = drivers["W1"]
        caps = driver.capabilities()
        self.assertFalse(caps.simulated)
        self.assertTrue(caps.measured_position)
        self.assertEqual(caps.transport, "rs485-vendor")

        readings = driver.read_sensors()
        self.assertEqual(len(readings), 1)
        self.assertEqual(readings[0].sensor_type, "co2")
        self.assertEqual(readings[0].value, 850.0)
        self.assertEqual(readings[0].provenance["site_id"], "site-a")
        mapping = driver.contract_mapping_identity()
        self.assertEqual(mapping["profile_id"], "vendor-v1")
        self.assertEqual(len(mapping["profile_sha256"]), 64)

    def test_post_payload_is_not_transformed_by_get_adapter(self):
        calls = []

        def raw(method, path, body):
            calls.append((method, path, body))
            return {"vendorAck": True}

        adapter = build_windowpilot_response_adapter(profile())
        from airtrajectory.drivers.windowpilot import WindowPilotHTTPDriver

        driver = WindowPilotHTTPDriver(
            base_url="http://w1",
            request_json=raw,
            response_adapter=adapter,
        )
        result = driver._request_json(
            "POST",
            "/api/window/open",
            {"target_pct": 10.0},
        )
        self.assertEqual(result, {"vendorAck": True})
        self.assertEqual(
            calls,
            [("POST", "/api/window/open", {"target_pct": 10.0})],
        )

    def test_probe_becomes_compatible_through_mapping_profile(self):
        report = probe_windowpilot_config(
            config=config(),
            request_json_factory=request_factory,
            clock_fn=lambda: 1800000001.0,
        )
        self.assertEqual(report["status"], "COMPATIBLE")
        endpoint = report["endpoints"]["W1"]
        self.assertEqual(
            endpoint["contract_mapping"]["profile_id"],
            "vendor-v1",
        )
        self.assertEqual(
            len(endpoint["contract_mapping"]["profile_sha256"]),
            64,
        )

    def test_mapping_profile_change_is_contract_drift(self):
        first = probe_windowpilot_config(
            config=config(profile("vendor-v1")),
            request_json_factory=request_factory,
            clock_fn=lambda: 1800000001.0,
        )
        baseline = freeze_windowpilot_contract_baseline(
            first,
            baseline_id="vendor-baseline-v1",
        )
        second = probe_windowpilot_config(
            config=config(profile("vendor-v2")),
            request_json_factory=request_factory,
            clock_fn=lambda: 1800000002.0,
        )
        result = compare_windowpilot_contract_baseline(
            baseline=baseline,
            current_report=second,
        )
        self.assertEqual(result["status"], "DRIFT")
        self.assertTrue(
            any(
                row["category"] == "CONTRACT_DRIFT"
                and "contract_mapping" in row["path"]
                for row in result["drifts"]
            )
        )


if __name__ == "__main__":
    unittest.main()
