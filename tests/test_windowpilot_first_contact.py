import hashlib
import json
import unittest

from airtrajectory.windowpilot_first_contact import (
    capture_windowpilot_first_contact,
)


class WindowPilotFirstContactTests(unittest.TestCase):
    def config(self):
        return {
            "schema_version": "0.1",
            "windowpilot_endpoints": {
                "W1": {
                    "base_url": "https://windowpilot.example",
                    "timeout_s": 3.0,
                    "headers_env": {
                        "Authorization": "WINDOWPILOT_AUTH",
                        "X-API-Key": "WINDOWPILOT_API_KEY",
                    },
                }
            },
            "fixed_openings": {},
            "contract_mapping_profiles": {},
        }

    def test_exact_raw_bytes_are_captured_with_secret_headers_not_persisted(self):
        bodies = {
            "/api/capabilities": b'{ "runtime" : {"ok": true} }\n',
            "/api/physical-readiness": b'{"device":{"id":"abc"}}\n',
            "/api/state": b'{"telemetry":{"co2":850}}\n',
        }
        calls = []

        def fetch(*, url, headers, timeout_s):
            calls.append((url, dict(headers), timeout_s))
            path = url.replace("https://windowpilot.example", "")
            return (
                200,
                {"Content-Type": "application/json; charset=utf-8"},
                bodies[path],
            )

        manifest, captures = capture_windowpilot_first_contact(
            config=self.config(),
            environ={
                "WINDOWPILOT_AUTH": "Bearer super-secret",
                "WINDOWPILOT_API_KEY": "key-secret",
            },
            fetch_fn=fetch,
        )

        self.assertEqual(manifest["status"], "CAPTURED")
        self.assertEqual(manifest["network_requests"], 3)
        self.assertEqual(manifest["actuator_writes"], 0)
        self.assertEqual(
            [call[0] for call in calls],
            [
                "https://windowpilot.example/api/capabilities",
                "https://windowpilot.example/api/physical-readiness",
                "https://windowpilot.example/api/state",
            ],
        )
        self.assertTrue(
            all(
                call[1]["Authorization"] == "Bearer super-secret"
                and call[1]["X-API-Key"] == "key-secret"
                for call in calls
            )
        )
        endpoint = manifest["endpoints"]["W1"]
        self.assertEqual(
            endpoint["request_header_names"],
            ["Authorization", "X-API-Key"],
        )
        serialized = json.dumps(manifest)
        self.assertNotIn("super-secret", serialized)
        self.assertNotIn("key-secret", serialized)

        self.assertEqual(
            captures["W1"]["capabilities.json"],
            bodies["/api/capabilities"],
        )
        self.assertEqual(
            endpoint["responses"]["capabilities"]["body_sha256"],
            hashlib.sha256(bodies["/api/capabilities"]).hexdigest(),
        )
        self.assertEqual(len(manifest["first_contact_capture_sha256"]), 64)

    def test_missing_secret_environment_variable_fails_before_fetch(self):
        calls = []

        def fetch(**kwargs):
            calls.append(kwargs)
            raise AssertionError("network should not be contacted")

        with self.assertRaisesRegex(
            ValueError,
            "missing WindowPilot header environment variable WINDOWPILOT_API_KEY",
        ):
            capture_windowpilot_first_contact(
                config=self.config(),
                environ={"WINDOWPILOT_AUTH": "Bearer token"},
                fetch_fn=fetch,
            )
        self.assertEqual(calls, [])

    def test_non_json_response_fails_closed(self):
        def fetch(*, url, headers, timeout_s):
            return 200, {"Content-Type": "text/plain"}, b"not-json"

        with self.assertRaisesRegex(ValueError, "is not valid JSON"):
            capture_windowpilot_first_contact(
                config={
                    "windowpilot_endpoints": {
                        "W1": {"base_url": "http://w1"}
                    }
                },
                fetch_fn=fetch,
            )

    def test_non_success_http_status_fails_closed(self):
        def fetch(*, url, headers, timeout_s):
            return 401, {"Content-Type": "application/json"}, b'{"error":"unauthorized"}'

        with self.assertRaisesRegex(ValueError, "HTTP status 401"):
            capture_windowpilot_first_contact(
                config={
                    "windowpilot_endpoints": {
                        "W1": {"base_url": "http://w1"}
                    }
                },
                fetch_fn=fetch,
            )

    def test_unsafe_endpoint_id_is_rejected_for_artifact_path(self):
        with self.assertRaisesRegex(ValueError, "unsafe WindowPilot endpoint id"):
            capture_windowpilot_first_contact(
                config={
                    "windowpilot_endpoints": {
                        "../escape": {"base_url": "http://w1"}
                    }
                },
                fetch_fn=lambda **kwargs: (
                    200,
                    {"Content-Type": "application/json"},
                    b"{}",
                ),
            )


if __name__ == "__main__":
    unittest.main()
