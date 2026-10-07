import copy
import hashlib
import json
import unittest

from airtrajectory.windowpilot_contract_mapping import (
    validate_windowpilot_contract_mapping,
)
from airtrajectory.windowpilot_deployment_config_draft import (
    build_windowpilot_deployment_config_draft,
)


def sha(payload):
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def mapping_profile(profile_id="vendor-v1"):
    return {
        "schema_version": "0.1",
        "profile_id": profile_id,
        "endpoints": {
            "/api/capabilities": {
                "execution.simulated": "runtime.simulated",
                "execution.measured_position": "runtime.measuredPosition",
                "execution.transport": "runtime.transport",
            },
            "/api/physical-readiness": {
                "hardware_identity.identity_sha256": "device.identity",
                "latest_position_feedback.measured": "position.measured",
                "latest_position_feedback.position_pct": "position.percent",
                "latest_position_feedback.timestamp": "position.timestamp",
                "latest_position_feedback.quality": "position.quality",
                "latest_position_feedback.source": "position.source",
            },
            "/api/state": {
                "thing_model.sensors.co2_ppm": "telemetry.co2.value",
                "thing_model.sensor_timestamps.co2_ppm": "telemetry.co2.timestamp",
                "thing_model.sensor_evidence.co2_ppm.measured": "telemetry.co2.measured",
                "thing_model.sensor_evidence.co2_ppm.timestamp": "telemetry.co2.timestamp",
                "thing_model.sensor_evidence.co2_ppm.source": "telemetry.co2.source",
                "thing_model.sensor_evidence.co2_ppm.thingmodel_binding.site_id": "telemetry.co2.siteId",
            },
        },
    }


def source_config(*, placeholders=False):
    source = {
        "kind": "site-sensor-system",
        "id": "site-recorder-a",
        "model": "CWDS-CA01-windowpilot-stack",
        "serial": "SITE-A",
        "calibration_ref": "CAL-A",
        "unexpected_secret": "must-not-copy",
    }
    if placeholders:
        source["serial"] = "replace-with-system-serial"

    return {
        "schema_version": "0.1",
        "topology_id": "demo.fixed-three-room.v1",
        "windowpilot_endpoints": {
            "W1": {
                "base_url": "https://w1.example",
                "timeout_s": 2,
                "feedback_timeout_s": 5,
                "position_tolerance_pct": 1,
                "headers_env": {
                    "Authorization": "WINDOWPILOT_AUTH",
                },
                "inline_token": "must-not-copy",
            },
            "W2": {
                "base_url": "https://w2.example",
                "headers_env": {
                    "X-API-Key": "WINDOWPILOT_API_KEY",
                },
            },
        },
        "fixed_openings": {
            "D1": 100.0,
            "D2": 100.0,
        },
        "field_capture": {
            "source": source,
            "co2_zone_sources": {
                "living": "W1",
                "bedroom": "W2",
            },
            "max_sample_age_s": 10,
            "max_future_skew_s": 2,
            "private_token": "must-not-copy",
        },
        "contract_mapping_profiles": {},
        "root_password": "must-not-copy",
    }


def workspace(
    *,
    status="CAPTURED_AND_COMPATIBLE",
    eval_status="COMPATIBLE",
    profile_sha=None,
    capture_errors=None,
):
    payload = {
        "schema_version": "0.1",
        "workspace": "windowpilot-first-contact-workspace-v1",
        "status": status,
        "first_contact_capture_sha256": "c" * 64,
        "endpoint_ids": ["W1", "W2"],
        "endpoint_count": 2,
        "capture_errors": capture_errors or [],
        "mapping_profile_supplied": True,
        "mapping_profile_file_sha256": "f" * 64,
        "mapping_evaluations": {
            endpoint: {
                "status": eval_status,
                "evaluation_sha256": endpoint.lower().ljust(64, "0"),
                "mapping_profile_id": "vendor-v1",
                "mapping_profile_sha256": profile_sha,
                "compatibility_probe_receipt_sha256": (
                    endpoint.lower() * 32
                )[:64],
            }
            for endpoint in ("W1", "W2")
        },
        "successful_network_requests": 6,
        "network_requests_exact": True,
        "network_requests": 6,
        "actuator_writes": 0,
    }
    return {
        **payload,
        "workspace_sha256": sha(payload),
    }


class WindowPilotDeploymentConfigDraftTests(unittest.TestCase):
    def test_compatible_workspace_builds_ready_sanitized_config(self):
        normalized = validate_windowpilot_contract_mapping(
            mapping_profile()
        )
        draft, receipt = build_windowpilot_deployment_config_draft(
            source_config=source_config(),
            workspace=workspace(
                profile_sha=normalized["profile_sha256"]
            ),
            mapping_profile=mapping_profile(),
            mapping_profile_name="vendor",
        )

        self.assertEqual(receipt["status"], "READY_FOR_LIVE_PROBE")
        self.assertEqual(receipt["blockers"], [])
        self.assertFalse(receipt["http_secret_values_embedded"])
        self.assertEqual(
            draft["windowpilot_endpoints"]["W1"]["headers_env"],
            {"Authorization": "WINDOWPILOT_AUTH"},
        )
        self.assertNotIn(
            "inline_token",
            draft["windowpilot_endpoints"]["W1"],
        )
        self.assertNotIn("root_password", draft)
        self.assertNotIn(
            "unexpected_secret",
            draft["field_capture"]["source"],
        )
        self.assertNotIn(
            "private_token",
            draft["field_capture"],
        )
        self.assertEqual(
            draft["windowpilot_endpoints"]["W1"][
                "contract_mapping_profile"
            ],
            "vendor",
        )
        self.assertEqual(
            draft["contract_mapping_profiles"]["vendor"][
                "profile_sha256"
            ],
            normalized["profile_sha256"],
        )

    def test_placeholder_deployment_metadata_blocks_ready_status(self):
        normalized = validate_windowpilot_contract_mapping(
            mapping_profile()
        )
        _, receipt = build_windowpilot_deployment_config_draft(
            source_config=source_config(placeholders=True),
            workspace=workspace(
                profile_sha=normalized["profile_sha256"]
            ),
            mapping_profile=mapping_profile(),
        )
        self.assertEqual(receipt["status"], "DRAFT_WITH_BLOCKERS")
        self.assertTrue(
            any(
                "field_capture.source.serial" in blocker
                for blocker in receipt["blockers"]
            )
        )

    def test_partial_capture_blocks_ready_status(self):
        normalized = validate_windowpilot_contract_mapping(
            mapping_profile()
        )
        ws = workspace(
            status="PARTIAL_CAPTURE_WITH_MAPPING",
            profile_sha=normalized["profile_sha256"],
            capture_errors=[
                {
                    "endpoint_id": "W2",
                    "error_type": "RuntimeError",
                    "error": "offline",
                }
            ],
        )
        _, receipt = build_windowpilot_deployment_config_draft(
            source_config=source_config(),
            workspace=ws,
            mapping_profile=mapping_profile(),
        )
        self.assertEqual(receipt["status"], "DRAFT_WITH_BLOCKERS")
        self.assertTrue(
            any(
                "first-contact capture incomplete" in blocker
                for blocker in receipt["blockers"]
            )
        )

    def test_incompatible_mapping_blocks_ready_status(self):
        normalized = validate_windowpilot_contract_mapping(
            mapping_profile()
        )
        _, receipt = build_windowpilot_deployment_config_draft(
            source_config=source_config(),
            workspace=workspace(
                eval_status="INCOMPATIBLE",
                profile_sha=normalized["profile_sha256"],
            ),
            mapping_profile=mapping_profile(),
        )
        self.assertEqual(receipt["status"], "DRAFT_WITH_BLOCKERS")
        self.assertTrue(
            all(
                value == "INCOMPATIBLE"
                for value in receipt["endpoint_readiness"].values()
            )
        )

    def test_mapping_profile_sha_must_match_workspace_evaluation(self):
        with self.assertRaisesRegex(
            ValueError,
            "mapping profile SHA-256 does not match",
        ):
            build_windowpilot_deployment_config_draft(
                source_config=source_config(),
                workspace=workspace(profile_sha="9" * 64),
                mapping_profile=mapping_profile(),
            )

    def test_tampered_workspace_is_rejected(self):
        normalized = validate_windowpilot_contract_mapping(
            mapping_profile()
        )
        ws = workspace(profile_sha=normalized["profile_sha256"])
        ws["endpoint_ids"] = ["W1"]
        with self.assertRaisesRegex(
            ValueError,
            "workspace SHA-256 integrity",
        ):
            build_windowpilot_deployment_config_draft(
                source_config=source_config(),
                workspace=ws,
                mapping_profile=mapping_profile(),
            )

    def test_zone_mapping_to_uncaptured_endpoint_is_blocked(self):
        normalized = validate_windowpilot_contract_mapping(
            mapping_profile()
        )
        cfg = source_config()
        cfg["field_capture"]["co2_zone_sources"]["study"] = "W3"
        _, receipt = build_windowpilot_deployment_config_draft(
            source_config=cfg,
            workspace=workspace(
                profile_sha=normalized["profile_sha256"]
            ),
            mapping_profile=mapping_profile(),
        )
        self.assertEqual(receipt["status"], "DRAFT_WITH_BLOCKERS")
        self.assertTrue(
            any(
                "uncaptured endpoints: W3" in blocker
                for blocker in receipt["blockers"]
            )
        )


if __name__ == "__main__":
    unittest.main()
