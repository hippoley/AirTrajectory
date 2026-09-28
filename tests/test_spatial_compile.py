import json
from pathlib import Path
import unittest

from airtrajectory.layout import LayoutContract
from airtrajectory.spatial_compile import compile_spatial_plan


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"


class SpatialCompilePlanTests(unittest.TestCase):
    def _layout(self):
        payload = json.loads(LAYOUT.read_text(encoding="utf-8"))
        return LayoutContract.from_dict(payload)

    def test_fixed_layout_compiles_to_backend_neutral_spatial_plan(self):
        plan = compile_spatial_plan(self._layout())

        self.assertEqual(plan["status"], "READY_FOR_BACKEND_COMPILER")
        self.assertEqual(plan["coordinate_space"], "layout-canvas")
        self.assertFalse(plan["metric_geometry_ready"])
        self.assertFalse(
            plan["backend_requirements"]["contam"]["prj_generation_ready"]
        )
        self.assertEqual(
            {zone["id"] for zone in plan["zones"]},
            {"living", "bedroom", "study"},
        )

    def test_moving_window_changes_anchor_but_not_connectivity_identity(self):
        layout = self._layout()
        base = compile_spatial_plan(layout)
        moved = compile_spatial_plan(
            layout,
            opening_positions={"W1": 0.82},
        )

        base_w1 = next(x for x in base["openings"] if x["id"] == "W1")
        moved_w1 = next(x for x in moved["openings"] if x["id"] == "W1")

        self.assertNotEqual(base_w1["anchor"], moved_w1["anchor"])
        self.assertEqual(base_w1["source"], moved_w1["source"])
        self.assertEqual(base_w1["target"], moved_w1["target"])
        self.assertEqual(base_w1["wall_id"], moved_w1["wall_id"])
        self.assertEqual(base_w1["path_key"], moved_w1["path_key"])
        self.assertEqual(base_w1["control_key"], moved_w1["control_key"])
        self.assertEqual(
            base["connectivity_sha256"],
            moved["connectivity_sha256"],
        )

    def test_vertical_wall_anchor_is_deterministic_from_position_t(self):
        plan = compile_spatial_plan(
            self._layout(),
            opening_positions={"W1": 0.5},
        )
        w1 = next(x for x in plan["openings"] if x["id"] == "W1")

        self.assertEqual(w1["anchor"]["x"], 180.0)
        self.assertEqual(w1["anchor"]["y"], 245.0)
        self.assertEqual(w1["wall_vector"]["dx"], 0.0)
        self.assertEqual(w1["wall_vector"]["dy"], 250.0)

    def test_horizontal_wall_anchor_is_deterministic_from_position_t(self):
        plan = compile_spatial_plan(
            self._layout(),
            opening_positions={"W3": 0.25},
        )
        w3 = next(x for x in plan["openings"] if x["id"] == "W3")

        self.assertEqual(w3["anchor"]["x"], 470.0)
        self.assertEqual(w3["anchor"]["y"], 540.0)

    def test_unknown_opening_override_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unknown opening"):
            compile_spatial_plan(
                self._layout(),
                opening_positions={"W404": 0.5},
            )


    def test_metric_geometry_becomes_contam_input_ready_when_complete(self):
        payload = json.loads(LAYOUT.read_text(encoding="utf-8"))
        for wall in payload["walls"]:
            wall["length_m"] = 4.0
            wall["azimuth_deg"] = 90.0
        for opening in payload["openings"]:
            opening["width_m"] = 1.0
            opening["height_m"] = 2.0
            opening["sill_height_m"] = 0.5
            opening["max_area_m2"] = min(opening["max_area_m2"], 2.0)

        plan = compile_spatial_plan(LayoutContract.from_dict(payload))

        self.assertTrue(plan["metric_geometry_ready"])
        contam = plan["backend_requirements"]["contam"]
        self.assertTrue(contam["metric_inputs_ready"])
        self.assertEqual(contam["missing_metric_wall_fields"], {})
        self.assertEqual(contam["missing_metric_opening_fields"], {})
        self.assertFalse(contam["prj_generation_implemented"])
        self.assertFalse(contam["prj_generation_ready"])

        w1 = next(x for x in plan["openings"] if x["id"] == "W1")
        self.assertAlmostEqual(
            w1["metric"]["distance_along_wall_m"],
            4.0 * 0.36,
        )

    def test_partial_metric_geometry_reports_entity_level_missing_fields(self):
        payload = json.loads(LAYOUT.read_text(encoding="utf-8"))
        payload["walls"][0]["length_m"] = 2.5
        payload["walls"][0]["azimuth_deg"] = 270.0
        payload["openings"][0]["width_m"] = 1.2
        payload["openings"][0]["height_m"] = 1.5

        plan = compile_spatial_plan(LayoutContract.from_dict(payload))
        contam = plan["backend_requirements"]["contam"]

        self.assertFalse(plan["metric_geometry_ready"])
        self.assertIn("W1", contam["missing_metric_opening_fields"])
        self.assertEqual(
            contam["missing_metric_opening_fields"]["W1"],
            ["sill_height_m"],
        )
        self.assertNotIn(
            "living-west",
            contam["missing_metric_wall_fields"],
        )

    def test_invalid_metric_geometry_fails_closed(self):
        payload = json.loads(LAYOUT.read_text(encoding="utf-8"))
        payload["walls"][0]["length_m"] = 1.0
        payload["walls"][0]["azimuth_deg"] = 361.0
        with self.assertRaisesRegex(ValueError, "azimuth_deg"):
            LayoutContract.from_dict(payload)

        payload = json.loads(LAYOUT.read_text(encoding="utf-8"))
        payload["walls"][0]["length_m"] = 0.8
        payload["openings"][0]["width_m"] = 1.2
        with self.assertRaisesRegex(ValueError, "exceeds wall length_m"):
            LayoutContract.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
