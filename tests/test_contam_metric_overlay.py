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

    def test_imported_overlay_requires_exact_layout_revision_hash(self):
        base_payload = json.loads(LAYOUT.read_text(encoding="utf-8"))
        base_payload["source_kind"] = "imported-floorplan"
        base_payload["capabilities"]["arbitrary_topology_import"] = "supported"
        base_payload["capabilities"]["floorplan_geometry_editable"] = True
        base_payload["source_provenance"] = {
            "format": "JSON", "source_sha256": "a" * 64,
            "importer": {"id": "test", "version": "1"},
        }
        base = LayoutContract.from_dict(base_payload)
        overlay = json.loads(PROFILE.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "requires layout_contract_sha256"):
            apply_metric_geometry_overlay(base, overlay)
        overlay["layout_contract_sha256"] = base.sha256()
        resolved, meta = apply_metric_geometry_overlay(base, overlay)
        self.assertEqual(resolved.topology_id, base.topology_id)
        self.assertEqual(len(meta["metric_geometry_profile_sha256"]), 64)
        # Same topology and entity IDs, but revised geometry invalidates profile.
        base_payload["rooms"][0]["volume_m3"] += 1.0
        changed = LayoutContract.from_dict(base_payload)
        with self.assertRaisesRegex(ValueError, "does not match layout"):
            apply_metric_geometry_overlay(changed, overlay)

    def test_incomplete_overlay_fails_closed(self):
        base = LayoutContract.from_file(LAYOUT)
        overlay = json.loads(PROFILE.read_text(encoding="utf-8"))
        del overlay["openings"]["W3"]
        with self.assertRaisesRegex(ValueError, "missing openings=W3"):
            apply_metric_geometry_overlay(base, overlay)


if __name__ == "__main__":
    unittest.main()
