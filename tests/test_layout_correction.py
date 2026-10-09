import unittest
from airtrajectory.layout import LayoutContract
from airtrajectory.layout_correction import correct_layout


def fixture():
    return LayoutContract.from_dict({
        "schema_version":"0.1","topology_id":"import:test","source_kind":"imported-floorplan",
        "outside_id":"OUTSIDE",
        "capabilities":{"floorplan_geometry_editable":True,"opening_position_editable":True,
                        "opening_state_editable":True,"arbitrary_topology_import":"supported",
                        "contam_compiler":"reserved"},
        "source_provenance":{"format":"JSON","source_sha256":"a"*64,
                             "importer":{"id":"test","version":"1"}},
        "rooms":[{"id":"r1","name":"R1","x":0,"y":0,"w":4,"h":4,"volume_m3":40},
                 {"id":"r2","name":"R2","x":4,"y":0,"w":4,"h":4,"volume_m3":40}],
        "walls":[{"id":"w1","kind":"exterior","source":"r1","target":"OUTSIDE",
                  "x1":0,"y1":0,"x2":0,"y2":4}],
        "openings":[{"id":"o1","kind":"window","wall_id":"w1","source":"r1",
                     "target":"OUTSIDE","position_t":0.5,"initial_open_pct":0,
                     "max_area_m2":1,"render_side":"left","position_editable":True,
                     "state_editable":True}],
        "compiler_contract":{},
    })


class LayoutCorrectionTests(unittest.TestCase):
    def test_rename_and_move_preserve_source(self):
        original=fixture()
        edited=correct_layout(original,[
            {"op":"rename_room","id":"r1","name":"Kitchen"},
            {"op":"move_opening","id":"o1","position_t":0.8},
        ])
        self.assertEqual(edited.rooms[0].name,"Kitchen")
        self.assertEqual(edited.openings[0].position_t,0.8)
        self.assertEqual(original.rooms[0].name,"R1")
        self.assertEqual(edited.source_provenance["correction"]["count"],2)

    def test_rewire_updates_openings(self):
        edited=correct_layout(fixture(),[
            {"op":"rewire_wall","id":"w1","kind":"internal","source":"r1","target":"r2"}
        ])
        self.assertEqual(edited.openings[0].target,"r2")
        self.assertEqual(edited.walls[0].kind,"internal")

    def test_add_room_and_wall_to_new_topology(self):
        edited=correct_layout(fixture(),[
            {"op":"add_room","id":"r3","x":8,"y":0,"w":3,"h":4,"volume_m3":30},
            {"op":"add_wall","id":"w2","kind":"internal",
             "source":"r2","target":"r3","x1":8,"y1":0,"x2":8,"y2":4},
        ])
        self.assertEqual(len(edited.rooms),3)
        self.assertEqual(len(edited.walls),2)

    def test_remove_referenced_room_and_wall_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"referenced by a wall"):
            correct_layout(fixture(),[{"op":"remove_room","id":"r1"}])
        with self.assertRaisesRegex(ValueError,"referenced by an opening"):
            correct_layout(fixture(),[{"op":"remove_wall","id":"w1"}])

    def test_remove_unreferenced_room(self):
        edited=correct_layout(fixture(),[{"op":"remove_room","id":"r2"}])
        self.assertEqual([x.id for x in edited.rooms],["r1"])

    def test_unknown_room_endpoint_rejected(self):
        with self.assertRaises(ValueError):
            correct_layout(fixture(),[{
                "op":"add_wall","id":"bad","kind":"internal",
                "source":"r1","target":"missing",
                "x1":1,"y1":0,"x2":1,"y2":4,
            }])

    def test_rejects_invalid_opening_geometry(self):
        with self.assertRaises(ValueError):
            correct_layout(fixture(),[
                {"op":"move_opening","id":"o1","position_t":1.5}
            ])

    def test_remove_and_add(self):
        edited=correct_layout(fixture(),[
            {"op":"remove_opening","id":"o1"},
            {"op":"add_opening","id":"o2","kind":"window","wall_id":"w1","max_area_m2":1},
        ])
        self.assertEqual([o.id for o in edited.openings],["o2"])


if __name__=="__main__":
    unittest.main()
