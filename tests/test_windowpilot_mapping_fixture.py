import json
import unittest

from airtrajectory.windowpilot_mapping_fixture import (
    evaluate_windowpilot_mapping_files,
    evaluate_windowpilot_mapping_fixture,
)


def profile():
    return {
        "schema_version": "0.1",
        "profile_id": "vendor-offline-v1",
        "endpoints": {
            "/api/capabilities": {
                "execution.simulated": {
                    "path": "runtime.sim",
                    "coerce": "bool",
                },
                "execution.measured_position": {
                    "path": "runtime.measuredPosition",
                    "coerce": "bool",
                },
                "execution.transport": "runtime.transport",
            },
            "/api/physical-readiness": {
                "hardware_identity.identity_sha256": "device.sha256",
                "latest_position_feedback.measured": {
                    "path": "position.measured",
                    "coerce": "bool",
                },
                "latest_position_feedback.position_pct": {
                    "path": "position.percent",
                    "coerce": "float",
                },
                "latest_position_feedback.timestamp": {
                    "path": "position.ts",
                    "coerce": "float",
                },
                "latest_position_feedback.quality": "position.quality",
                "latest_position_feedback.source": "position.source",
            },
            "/api/state": {
                "thing_model.sensors.co2_ppm": {
                    "path": "co2.value",
                    "coerce": "float",
                },
                "thing_model.sensor_timestamps.co2_ppm": {
                    "path": "co2.ts",
                    "coerce": "float",
                },
                "thing_model.sensor_evidence.co2_ppm.measured": {
                    "path": "co2.measured",
                    "coerce": "bool",
                },
                "thing_model.sensor_evidence.co2_ppm.timestamp": {
                    "path": "co2.ts",
                    "coerce": "float",
                },
                "thing_model.sensor_evidence.co2_ppm.source": "co2.source",
                "thing_model.sensor_evidence.co2_ppm.thingmodel_binding.site_id": "co2.siteId",
            },
        },
    }


def raw_payloads(*, simulated=False, measured=True):
    return {
        "capabilities": {
            "runtime": {
                "sim": simulated,
                "measuredPosition": measured,
                "transport": "rs485-vendor",
            }
        },
        "physical_readiness": {
            "device": {"sha256": "1" * 64},
            "position": {
                "measured": measured,
                "percent": 42.0,
                "ts": 1800000000.0,
                "quality": "encoder-measured",
                "source": "encoder-1",
            },
        },
        "state": {
            "co2": {
                "value": 850.0,
                "ts": 1800000000.0,
                "measured": measured,
                "source": "co2-1",
                "siteId": "site-a",
            }
        },
    }


class WindowPilotMappingFixtureTests(unittest.TestCase):
    def test_valid_saved_payloads_map_and_probe_compatible(self):
        report, canonical = evaluate_windowpilot_mapping_fixture(
            profile=profile(),
            raw_payloads=raw_payloads(),
            fixture_id="fixture-001",
            clock_fn=lambda: 1800000001.0,
        )
        self.assertEqual(report["status"], "COMPATIBLE")
        self.assertEqual(report["mapping_errors"], [])
        self.assertEqual(report["actuator_writes"], 0)
        self.assertEqual(report["network_requests"], 0)
        self.assertEqual(
            canonical["physical_readiness"][
                "latest_position_feedback"
            ]["position_pct"],
            42.0,
        )
        self.assertEqual(
            canonical["state"]["thing_model"]["sensors"]["co2_ppm"],
            850.0,
        )
        self.assertEqual(
            report["mapping_profile_id"],
            "vendor-offline-v1",
        )
        self.assertEqual(len(report["mapping_profile_sha256"]), 64)
        self.assertEqual(len(report["evaluation_sha256"]), 64)

    def test_missing_required_source_field_is_mapping_error(self):
        raw = raw_payloads()
        del raw["physical_readiness"]["position"]["percent"]
        report, canonical = evaluate_windowpilot_mapping_fixture(
            profile=profile(),
            raw_payloads=raw,
        )
        self.assertEqual(report["status"], "MAPPING_ERROR")
        self.assertIsNone(report["compatibility"])
        self.assertEqual(
            report["endpoint_receipts"]["physical_readiness"]["status"],
            "MAPPING_ERROR",
        )
        self.assertTrue(
            any(
                row["endpoint"] == "/api/physical-readiness"
                for row in report["mapping_errors"]
            )
        )
        self.assertNotIn("physical_readiness", canonical)

    def test_mapping_can_succeed_while_semantics_remain_incompatible(self):
        report, canonical = evaluate_windowpilot_mapping_fixture(
            profile=profile(),
            raw_payloads=raw_payloads(simulated=True, measured=False),
        )
        self.assertEqual(report["status"], "INCOMPATIBLE")
        self.assertIsNotNone(report["compatibility"])
        codes = {
            row["code"]
            for row in report["compatibility"]["findings"]
        }
        self.assertIn(
            "EXECUTION_NOT_CONFIRMED_PHYSICAL",
            codes,
        )
        self.assertIn(
            "MEASURED_POSITION_CAPABILITY_MISSING",
            codes,
        )
        self.assertIn("POSITION_NOT_MEASURED", codes)
        self.assertIn("CO2_NOT_MEASURED", codes)
        self.assertEqual(
            canonical["capabilities"]["execution"]["simulated"],
            True,
        )

    def test_raw_file_hash_uses_exact_bytes_not_json_semantics(self):
        p = json.dumps(profile()).encode("utf-8")
        cap_a = json.dumps(
            raw_payloads()["capabilities"],
            separators=(",", ":"),
        ).encode("utf-8")
        cap_b = json.dumps(
            raw_payloads()["capabilities"],
            indent=2,
        ).encode("utf-8")
        ready = json.dumps(
            raw_payloads()["physical_readiness"]
        ).encode("utf-8")
        state = json.dumps(raw_payloads()["state"]).encode("utf-8")

        report_a, _ = evaluate_windowpilot_mapping_files(
            profile_bytes=p,
            capabilities_bytes=cap_a,
            physical_readiness_bytes=ready,
            state_bytes=state,
        )
        report_b, _ = evaluate_windowpilot_mapping_files(
            profile_bytes=p,
            capabilities_bytes=cap_b,
            physical_readiness_bytes=ready,
            state_bytes=state,
        )
        self.assertEqual(report_a["status"], "COMPATIBLE")
        self.assertEqual(report_b["status"], "COMPATIBLE")
        self.assertNotEqual(
            report_a["endpoint_receipts"]["capabilities"]["raw_sha256"],
            report_b["endpoint_receipts"]["capabilities"]["raw_sha256"],
        )
        self.assertEqual(
            report_a["endpoint_receipts"]["capabilities"][
                "canonical_sha256"
            ],
            report_b["endpoint_receipts"]["capabilities"][
                "canonical_sha256"
            ],
        )

    def test_raw_payload_key_set_must_be_exact(self):
        raw = raw_payloads()
        del raw["state"]
        with self.assertRaisesRegex(
            ValueError,
            "must contain exactly",
        ):
            evaluate_windowpilot_mapping_fixture(
                profile=profile(),
                raw_payloads=raw,
            )


if __name__ == "__main__":
    unittest.main()
