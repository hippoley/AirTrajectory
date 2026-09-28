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


if __name__ == "__main__":
    unittest.main()
