import json
from pathlib import Path
import unittest

from airtrajectory.contam_ir import compile_contam_ir
from airtrajectory.layout import LayoutContract


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"


def metric_layout() -> LayoutContract:
    payload = json.loads(LAYOUT.read_text(encoding="utf-8"))
    wall_lengths = {
        "living-west": 5.0,
        "bedroom-east": 5.0,
        "study-south": 8.0,
        "living-bedroom": 5.0,
        "living-study": 4.0,
    }
    wall_azimuths = {
        "living-west": 270.0,
        "bedroom-east": 90.0,
        "study-south": 180.0,
        "living-bedroom": 90.0,
        "living-study": 180.0,
    }
    for wall in payload["walls"]:
        wall["length_m"] = wall_lengths[wall["id"]]
        wall["azimuth_deg"] = wall_azimuths[wall["id"]]
    for opening in payload["openings"]:
        opening["width_m"] = 1.2
        opening["height_m"] = 2.0
        opening["sill_height_m"] = 0.2 if opening["kind"] == "door" else 0.9
        opening["max_area_m2"] = min(opening["max_area_m2"], 2.4)
    return LayoutContract.from_dict(payload)


class ContamIRTests(unittest.TestCase):
    def test_incomplete_metric_layout_is_rejected(self):
        payload = json.loads(LAYOUT.read_text(encoding="utf-8"))
        layout = LayoutContract.from_dict(payload)
        with self.assertRaisesRegex(ValueError, "not CONTAM metric-input ready"):
            compile_contam_ir(layout)

    def test_metric_layout_compiles_to_symbolic_contam_ir(self):
        ir = compile_contam_ir(metric_layout())

        self.assertEqual(ir["status"], "READY_FOR_PRJ_WRITER")
        self.assertFalse(ir["writer_contract"]["ready"])
        self.assertEqual(len(ir["zones"]), 3)
        self.assertEqual(len(ir["flow_paths"]), 5)
        self.assertEqual(len(ir["controls"]), 5)
        self.assertEqual(len(ir["contam_semantics_sha256"]), 64)

    def test_exterior_window_targets_ambient_boundary(self):
        ir = compile_contam_ir(metric_layout())
        w1 = next(x for x in ir["flow_paths"] if x["layout_opening_id"] == "W1")

        self.assertEqual(w1["boundary_kind"], "exterior")
        self.assertEqual(w1["from"], "zone:living")
        self.assertEqual(w1["to"], "ambient:OUTSIDE")
        self.assertEqual(w1["wall_azimuth_deg"], 270.0)

    def test_internal_door_connects_two_zones(self):
        ir = compile_contam_ir(metric_layout())
        d1 = next(x for x in ir["flow_paths"] if x["layout_opening_id"] == "D1")

        self.assertEqual(d1["boundary_kind"], "internal")
        self.assertEqual(d1["from"], "zone:living")
        self.assertEqual(d1["to"], "zone:bedroom")

    def test_moving_window_changes_metric_position_not_symbolic_identity(self):
        base = compile_contam_ir(metric_layout())
        moved = compile_contam_ir(
            metric_layout(),
            opening_positions={"W1": 0.8},
        )
        a = next(x for x in base["flow_paths"] if x["layout_opening_id"] == "W1")
        b = next(x for x in moved["flow_paths"] if x["layout_opening_id"] == "W1")

        self.assertEqual(a["key"], b["key"])
        self.assertEqual(a["from"], b["from"])
        self.assertEqual(a["to"], b["to"])
        self.assertNotEqual(
            a["distance_along_wall_m"],
            b["distance_along_wall_m"],
        )
        self.assertEqual(b["distance_along_wall_m"], 4.0)

    def test_contam_numeric_ids_remain_unassigned(self):
        ir = compile_contam_ir(metric_layout())
        self.assertTrue(all(z["contam_zone_number"] is None for z in ir["zones"]))
        self.assertTrue(
            all(p["contam_path_number"] is None for p in ir["flow_paths"])
        )
        self.assertTrue(
            all(c["contam_control_number"] is None for c in ir["controls"])
        )


if __name__ == "__main__":
    unittest.main()
