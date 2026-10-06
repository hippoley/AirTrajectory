import json
import unittest

from airtrajectory.windowpilot_first_contact_workspace import (
    build_windowpilot_first_contact_workspace,
)


def config():
    return {
        "schema_version": "0.1",
        "windowpilot_endpoints": {
            "W1": {
                "base_url": "https://w1.example",
                "headers_env": {
                    "Authorization": "WINDOWPILOT_AUTH",
                },
            }
        },
        "fixed_openings": {},
        "contract_mapping_profiles": {},
    }


def profile():
    return {
        "schema_version": "0.1",
        "profile_id": "workspace-vendor-v1",
        "endpoints": {
            "/api/capabilities": {
                "execution.simulated": {
                    "path": "runtime.simulated",
                    "coerce": "bool",
                },
                "execution.measured_position": {
                    "path": "runtime.measuredPosition",
                    "coerce": "bool",
                },
                "execution.transport": "runtime.transport",
            },
            "/api/physical-readiness": {
                "hardware_identity.identity_sha256": "device.identity",
                "latest_position_feedback.measured": {
                    "path": "position.measured",
                    "coerce": "bool",
                },
                "latest_position_feedback.position_pct": {
                    "path": "position.percent",
                    "coerce": "float",
                },
                "latest_position_feedback.timestamp": {
                    "path": "position.timestamp",
                    "coerce": "float",
                },
                "latest_position_feedback.quality": "position.quality",
                "latest_position_feedback.source": "position.source",
            },
            "/api/state": {
                "thing_model.sensors.co2_ppm": {
                    "path": "telemetry.co2.value",
                    "coerce": "float",
                },
                "thing_model.sensor_timestamps.co2_ppm": {
                    "path": "telemetry.co2.timestamp",
                    "coerce": "float",
                },
                "thing_model.sensor_evidence.co2_ppm.measured": {
                    "path": "telemetry.co2.measured",
                    "coerce": "bool",
                },
                "thing_model.sensor_evidence.co2_ppm.timestamp": {
                    "path": "telemetry.co2.timestamp",
                    "coerce": "float",
                },
                "thing_model.sensor_evidence.co2_ppm.source": "telemetry.co2.source",
                "thing_model.sensor_evidence.co2_ppm.thingmodel_binding.site_id": "telemetry.co2.siteId",
            },
        },
    }


def payloads(*, simulated=False, measured=True):
    return {
        "/api/capabilities": {
            "runtime": {
                "simulated": simulated,
                "measuredPosition": measured,
                "transport": "rs485-vendor",
            }
        },
        "/api/physical-readiness": {
            "device": {"identity": "1" * 64},
            "position": {
                "measured": measured,
                "percent": 42.0,
                "timestamp": 1800000000.0,
                "quality": "encoder",
                "source": "enc-1",
            },
        },
        "/api/state": {
            "telemetry": {
                "co2": {
                    "value": 850.0,
                    "timestamp": 1800000000.0,
                    "measured": measured,
                    "source": "co2-1",
                    "siteId": "site-a",
                }
            }
        },
    }


def fetcher(data, calls):
    def fetch(*, url, headers, timeout_s):
        calls.append((url, dict(headers), timeout_s))
        path = url.replace("https://w1.example", "")
        return (
            200,
            {"Content-Type": "application/json"},
            json.dumps(data[path], separators=(",", ":")).encode("utf-8"),
        )
    return fetch


class WindowPilotFirstContactWorkspaceTests(unittest.TestCase):
    def test_capture_only_preserves_raw_workspace(self):
        calls = []
        workspace, captures, evaluations = (
            build_windowpilot_first_contact_workspace(
                config=config(),
                environ={"WINDOWPILOT_AUTH": "Bearer secret"},
                fetch_fn=fetcher(payloads(), calls),
            )
        )
        self.assertEqual(workspace["status"], "CAPTURED_ONLY")
        self.assertEqual(workspace["network_requests"], 3)
        self.assertEqual(workspace["actuator_writes"], 0)
        self.assertEqual(evaluations, {})
        self.assertEqual(
            set(captures["W1"]),
            {
                "capabilities.json",
                "physical_readiness.json",
                "state.json",
            },
        )
        self.assertEqual(len(workspace["workspace_sha256"]), 64)

    def test_capture_and_mapping_can_finish_compatible_in_one_workspace(self):
        calls = []
        workspace, captures, evaluations = (
            build_windowpilot_first_contact_workspace(
                config=config(),
                mapping_profile_bytes=json.dumps(profile()).encode("utf-8"),
                environ={"WINDOWPILOT_AUTH": "Bearer secret"},
                fetch_fn=fetcher(payloads(), calls),
            )
        )
        self.assertEqual(
            workspace["status"],
            "CAPTURED_AND_COMPATIBLE",
        )
        self.assertEqual(
            workspace["mapping_evaluations"]["W1"]["status"],
            "COMPATIBLE",
        )
        self.assertEqual(
            evaluations["W1"]["report"]["status"],
            "COMPATIBLE",
        )
        self.assertEqual(
            evaluations["W1"]["canonical"]["physical_readiness"][
                "hardware_identity"
            ]["identity_sha256"],
            "1" * 64,
        )
        self.assertEqual(len(calls), 3)

    def test_semantic_incompatibility_keeps_raw_capture(self):
        workspace, captures, evaluations = (
            build_windowpilot_first_contact_workspace(
                config=config(),
                mapping_profile_bytes=json.dumps(profile()).encode("utf-8"),
                environ={"WINDOWPILOT_AUTH": "Bearer secret"},
                fetch_fn=fetcher(
                    payloads(simulated=True, measured=False),
                    [],
                ),
            )
        )
        self.assertEqual(
            workspace["status"],
            "CAPTURED_WITH_INCOMPATIBLE_MAPPING",
        )
        self.assertEqual(
            evaluations["W1"]["report"]["status"],
            "INCOMPATIBLE",
        )
        self.assertTrue(captures["W1"]["state.json"])

    def test_mapping_error_keeps_raw_capture(self):
        broken = profile()
        broken["endpoints"]["/api/physical-readiness"][
            "latest_position_feedback.position_pct"
        ]["path"] = "position.DOES_NOT_EXIST"
        workspace, captures, evaluations = (
            build_windowpilot_first_contact_workspace(
                config=config(),
                mapping_profile_bytes=json.dumps(broken).encode("utf-8"),
                environ={"WINDOWPILOT_AUTH": "Bearer secret"},
                fetch_fn=fetcher(payloads(), []),
            )
        )
        self.assertEqual(
            workspace["status"],
            "CAPTURED_WITH_MAPPING_ERROR",
        )
        self.assertEqual(
            evaluations["W1"]["report"]["status"],
            "MAPPING_ERROR",
        )
        self.assertTrue(captures["W1"]["physical_readiness.json"])

    def test_invalid_profile_still_returns_captured_raw_files(self):
        workspace, captures, evaluations = (
            build_windowpilot_first_contact_workspace(
                config=config(),
                mapping_profile_bytes=b'{"schema_version":"9"}',
                environ={"WINDOWPILOT_AUTH": "Bearer secret"},
                fetch_fn=fetcher(payloads(), []),
            )
        )
        self.assertEqual(
            workspace["status"],
            "CAPTURED_WITH_MAPPING_ERROR",
        )
        self.assertIsNone(
            workspace["mapping_evaluations"]["W1"][
                "mapping_profile_sha256"
            ]
        )
        self.assertEqual(
            evaluations["W1"]["report"]["status"],
            "MAPPING_ERROR",
        )
        self.assertTrue(captures["W1"]["capabilities.json"])


if __name__ == "__main__":
    unittest.main()
