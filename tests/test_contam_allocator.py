import copy
import json
from pathlib import Path
import unittest

from airtrajectory.contam_allocator import allocate_contam_ids
from airtrajectory.contam_ir import compile_contam_ir
from airtrajectory.layout import LayoutContract


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"


def metric_layout() -> LayoutContract:
    payload = json.loads(LAYOUT.read_text(encoding="utf-8"))
    for wall in payload["walls"]:
        wall["length_m"] = 5.0
        wall["azimuth_deg"] = 90.0
    for opening in payload["openings"]:
        opening["width_m"] = 1.0
        opening["height_m"] = 2.0
        opening["sill_height_m"] = 0.2 if opening["kind"] == "door" else 0.9
        opening["max_area_m2"] = min(opening["max_area_m2"], 2.0)
    return LayoutContract.from_dict(payload)


class ContamAllocatorTests(unittest.TestCase):
    def test_allocator_assigns_one_based_deterministic_ids(self):
        manifest = allocate_contam_ids(compile_contam_ir(metric_layout()))

        self.assertEqual(manifest["status"], "READY_FOR_PRJ_SERIALIZATION")
        self.assertEqual(manifest["zone_numbers"]["zone:bedroom"], 1)
        self.assertEqual(manifest["zone_numbers"]["zone:living"], 2)
        self.assertEqual(manifest["zone_numbers"]["zone:study"], 3)
        self.assertEqual(len(manifest["mapping_sha256"]), 64)

    def test_source_order_does_not_change_mapping(self):
        ir = compile_contam_ir(metric_layout())
        shuffled = copy.deepcopy(ir)
        shuffled["zones"] = list(reversed(shuffled["zones"]))
        shuffled["flow_paths"] = list(reversed(shuffled["flow_paths"]))
        shuffled["controls"] = list(reversed(shuffled["controls"]))

        a = allocate_contam_ids(ir)
        b = allocate_contam_ids(shuffled)

        self.assertEqual(a["zone_numbers"], b["zone_numbers"])
        self.assertEqual(a["path_numbers"], b["path_numbers"])
        self.assertEqual(a["control_numbers"], b["control_numbers"])
        self.assertEqual(a["mapping_sha256"], b["mapping_sha256"])

    def test_moving_window_preserves_numeric_identity(self):
        base = allocate_contam_ids(compile_contam_ir(metric_layout()))
        moved = allocate_contam_ids(
            compile_contam_ir(
                metric_layout(),
                opening_positions={"W1": 0.8},
            )
        )

        self.assertEqual(base["path_numbers"], moved["path_numbers"])
        self.assertEqual(base["control_numbers"], moved["control_numbers"])
        self.assertEqual(base["mapping_sha256"], moved["mapping_sha256"])

        a = next(x for x in base["flow_paths"] if x["layout_opening_id"] == "W1")
        b = next(x for x in moved["flow_paths"] if x["layout_opening_id"] == "W1")
        self.assertEqual(a["contam_path_number"], b["contam_path_number"])
        self.assertNotEqual(
            a["distance_along_wall_m"],
            b["distance_along_wall_m"],
        )

    def test_duplicate_keys_fail_closed(self):
        ir = compile_contam_ir(metric_layout())
        ir["zones"].append(copy.deepcopy(ir["zones"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate symbolic keys"):
            allocate_contam_ids(ir)

    def test_non_contam_ir_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not CONTAM IR"):
            allocate_contam_ids({"compiler": "other"})


if __name__ == "__main__":
    unittest.main()
