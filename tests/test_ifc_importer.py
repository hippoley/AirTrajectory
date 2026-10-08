import unittest

from airtrajectory.importers.ifc import _volume_from_property_sets, assess_ifc_semantics, layout_from_ifc_semantics
from airtrajectory.topology_acceptance import verify_topology_runtime

class IfcImporterTests(unittest.TestCase):
    def test_space_volume_falls_back_to_revit_style_volume_property(self):
        value,source=_volume_from_property_sets({
            "PSet_Revit_Dimensions":{"Volume":71.3906897089998}
        })
        self.assertAlmostEqual(value,71.3906897089998)
        self.assertEqual(source,"PSet_Revit_Dimensions.Volume")

    def test_conflicting_fallback_volumes_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"conflicting"):
            _volume_from_property_sets({
                "A":{"Volume":30.0},
                "B":{"Volume":31.0},
            })


    def test_normalized_ifc_semantics_enter_shared_runtime(self):
        semantics={
            "topology_id":"ifc:test-home",
            "spaces":[
                {"id":"S_A","name":"A","x":0,"y":0,"w":4,"h":3,"volume_m3":30},
                {"id":"S_B","name":"B","x":4,"y":0,"w":4,"h":3,"volume_m3":32},
            ],
            "openings":[
                {"id":"WIN_A","kind":"window","adjacent_spaces":["S_A"],"width_m":1.2,"height_m":1.4,"x1":0,"y1":1,"x2":0,"y2":2.2},
                {"id":"DOOR_AB","kind":"door","adjacent_spaces":["S_A","S_B"],"width_m":0.9,"height_m":2.0,"x1":4,"y1":1,"x2":4,"y2":1.9},
                {"id":"WIN_B","kind":"window","adjacent_spaces":["S_B"],"width_m":1.1,"height_m":1.4,"x1":8,"y1":1,"x2":8,"y2":2.1},
            ],
        }
        layout=layout_from_ifc_semantics(
            semantics,
            source_sha256="a"*64,
            importer_version="0.1",
        )
        self.assertEqual(layout.source_kind,"imported-floorplan")
        self.assertEqual(layout.source_provenance["format"],"IFC")
        receipt=verify_topology_runtime(layout)
        self.assertEqual(receipt["status"],"PASS")
        self.assertEqual(receipt["expected"]["zone_ids"],["S_A","S_B"])
        self.assertEqual(
            receipt["expected"]["opening_ids"],
            ["DOOR_AB","WIN_A","WIN_B"],
        )

    def test_readiness_explains_missing_physical_semantics(self):
        report=assess_ifc_semantics({
            "spaces":[{"id":"S_A","name":"A","x":0,"y":0,"w":4,"h":3,"volume_m3":30}],
            "openings":[{"id":"WIN_A","kind":"window","adjacent_spaces":[],"width_m":None,"height_m":1.4,"x1":0,"y1":1,"x2":0,"y2":2}],
        })
        self.assertEqual(report["status"],"BLOCKED")
        reasons={b["reason"] for b in report["blockers"]}
        self.assertIn("AMBIGUOUS_SPACE_ADJACENCY",reasons)
        self.assertIn("MISSING_WIDTH_M",reasons)

    def test_missing_ifc_adjacency_fails_closed(self):
        semantics={
            "spaces":[{"id":"S_A","name":"A","x":0,"y":0,"w":4,"h":3,"volume_m3":30}],
            "openings":[{"id":"WIN_A","kind":"window","adjacent_spaces":[],"width_m":1.2,"height_m":1.4,"x1":0,"y1":1,"x2":0,"y2":2}],
        }
        with self.assertRaisesRegex(ValueError,"requires one or two adjacent"):
            layout_from_ifc_semantics(semantics,source_sha256="b"*64)

if __name__=="__main__":
    unittest.main()
