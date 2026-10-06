import json
from pathlib import Path
import unittest

from airtrajectory.contam_metric_overlay import apply_metric_geometry_overlay
from airtrajectory.layout import LayoutContract


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"
PROFILE = ROOT / "examples" / "contam_metric_geometry.example.json"


class ContamMetricOverlayTests(unittest.TestCase):
    def test_overlay_keeps_topology_identity_and_adds_metric_fields(self):
        base = LayoutContract.from_file(LAYOUT)
        overlay = json.loads(PROFILE.read_text(encoding="utf-8"))
        resolved, meta = apply_metric_geometry_overlay(base, overlay)

        self.assertEqual(resolved.topology_id, base.topology_id)
        self.assertEqual(
            {o.id for o in resolved.openings},
            {o.id for o in base.openings},
        )
        w1 = next(o for o in resolved.openings if o.id == "W1")
        self.assertEqual(w1.width_m, 1.0)
        self.assertEqual(w1.sill_height_m, 0.9)
        self.assertEqual(len(meta["metric_geometry_profile_sha256"]), 64)
        self.assertFalse(meta["engineering_validated"])

    def test_incomplete_overlay_fails_closed(self):
        base = LayoutContract.from_file(LAYOUT)
        overlay = json.loads(PROFILE.read_text(encoding="utf-8"))
        del overlay["openings"]["W3"]
        with self.assertRaisesRegex(ValueError, "missing openings=W3"):
            apply_metric_geometry_overlay(base, overlay)


if __name__ == "__main__":
    unittest.main()
