import json
from pathlib import Path
import tempfile
import unittest

from airtrajectory.demo_physical_config import (
    build_windowpilot_drivers,
    load_windowpilot_driver_config,
)


class DemoPhysicalConfigTests(unittest.TestCase):
    def test_config_builds_per_opening_windowpilot_drivers(self):
        payload = {
            "schema_version": "0.1",
            "topology_id": "demo.fixed-three-room.v1",
            "windowpilot_endpoints": {
                "W1": {"base_url": "http://w1"},
                "W2": {"base_url": "http://w2"},
                "W3": {"base_url": "http://w3"},
            },
            "fixed_openings": {"D1": 100, "D2": 100},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "physical.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            config = load_windowpilot_driver_config(path)
        drivers = build_windowpilot_drivers(config)
        self.assertEqual(set(drivers), {"W1", "W2", "W3"})
        self.assertEqual(drivers["W1"].base_url, "http://w1")

    def test_endpoint_fixed_overlap_fails_closed(self):
        payload = {
            "schema_version": "0.1",
            "windowpilot_endpoints": {"W1": {"base_url": "http://w1"}},
            "fixed_openings": {"W1": 0},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "physical.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "both endpoint-driven and fixed"):
                load_windowpilot_driver_config(path)


if __name__ == "__main__":
    unittest.main()
