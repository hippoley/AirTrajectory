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

    def test_split_room_rewires_wall_and_opening_without_guessing(self):
        edited=correct_layout(fixture(),[{
            "op":"split_room","id":"r1",
            "children":[
                {"id":"r1a","x":0,"y":0,"w":2,"h":4,"volume_m3":20},
                {"id":"r1b","x":2,"y":0,"w":2,"h":4,"volume_m3":20},
            ],
            "wall_assignment":{"w1":"r1a"},
        }])
        self.assertEqual({r.id for r in edited.rooms},{"r1a","r1b","r2"})
        self.assertEqual(edited.walls[0].source,"r1a")
        self.assertEqual(edited.openings[0].source,"r1a")

    def test_split_requires_complete_explicit_wall_ownership(self):
        with self.assertRaisesRegex(ValueError,"explicit assignment"):
            correct_layout(fixture(),[{
                "op":"split_room","id":"r1",
                "children":[
                    {"id":"r1a","x":0,"y":0,"w":2,"h":4,"volume_m3":20},
                    {"id":"r1b","x":2,"y":0,"w":2,"h":4,"volume_m3":20},
                ],
                "wall_assignment":{},
            }])

    def test_split_rejects_unknown_child_target(self):
        with self.assertRaisesRegex(ValueError,"unknown child"):
            correct_layout(fixture(),[{
                "op":"split_room","id":"r1",
                "children":[
                    {"id":"r1a","x":0,"y":0,"w":2,"h":4,"volume_m3":20},
                    {"id":"r1b","x":2,"y":0,"w":2,"h":4,"volume_m3":20},
                ],
                "wall_assignment":{"w1":"r3"},
            }])

    def test_merge_roundtrip_through_shared_topology_runtime(self):
        from airtrajectory.topology_acceptance import verify_topology_runtime
        edited=correct_layout(fixture(),[{
            "op":"merge_rooms","source_ids":["r1","r2"],
            "merged_room":{"id":"combined","name":"Combined",
                           "x":0,"y":0,"w":8,"h":4,"volume_m3":80},
        }])
        receipt=verify_topology_runtime(edited)
        self.assertEqual(receipt["status"],"PASS")
        self.assertEqual(receipt["expected"]["zone_ids"],["combined"])
        self.assertEqual(receipt["expected"]["opening_ids"],["o1"])
        self.assertTrue(all(receipt["checks"].values()))

    def test_corrected_layout_roundtrip_preserves_identity(self):
        import json
        from dataclasses import asdict
        edited=correct_layout(fixture(),[
            {"op":"rename_room","id":"r1","name":"Kitchen"},
            {"op":"move_opening","id":"o1","position_t":0.65},
        ])
        payload={
            "schema_version":edited.schema_version,
            "topology_id":edited.topology_id,
            "source_kind":edited.source_kind,
            "outside_id":edited.outside_id,
            "capabilities":edited.capabilities,
            "source_provenance":edited.source_provenance,
            "rooms":[asdict(v) for v in edited.rooms],
            "walls":[asdict(v) for v in edited.walls],
            "openings":[asdict(v) for v in edited.openings],
            "compiler_contract":edited.compiler_contract,
        }
        restored=LayoutContract.from_dict(json.loads(json.dumps(payload)))
        self.assertEqual(restored.sha256(),edited.sha256())
        from airtrajectory.topology_acceptance import verify_topology_runtime
        receipt=verify_topology_runtime(restored)
        self.assertEqual(receipt["status"],"PASS")

    def test_nonfinite_geometry_never_enters_runtime(self):
        for patch in (
            {"op":"move_opening","id":"o1","position_t":float("nan")},
            {"op":"set_room_volume","id":"r1","volume_m3":float("inf")},
            {"op":"move_wall","id":"w1","x1":float("-inf")},
        ):
            with self.subTest(patch=patch["op"]):
                with self.assertRaisesRegex(ValueError,"must be finite"):
                    correct_layout(fixture(),[patch])

    def test_merge_rooms_preserves_external_opening(self):
        edited=correct_layout(fixture(),[{
            "op":"merge_rooms","source_ids":["r1","r2"],
            "merged_room":{"id":"combined","name":"Combined","x":0,"y":0,
                           "w":8,"h":4,"volume_m3":80},
        }])
        self.assertEqual([r.id for r in edited.rooms],["combined"])
        self.assertEqual(edited.walls[0].source,"combined")
        self.assertEqual(edited.openings[0].source,"combined")

    def test_merge_rejects_unresolved_shared_wall(self):
        with self.assertRaisesRegex(ValueError,"shared internal walls"):
            correct_layout(fixture(),[
                {"op":"add_wall","id":"shared","kind":"internal",
                 "source":"r1","target":"r2","x1":4,"y1":0,"x2":4,"y2":4},
                {"op":"merge_rooms","source_ids":["r1","r2"],
                 "merged_room":{"id":"combined","x":0,"y":0,"w":8,"h":4,"volume_m3":80}},
            ])

    def test_merge_rejects_unknown_room(self):
        with self.assertRaisesRegex(ValueError,"unknown source room"):
            correct_layout(fixture(),[{
                "op":"merge_rooms","source_ids":["r1","missing"],
                "merged_room":{"id":"combined","x":0,"y":0,"w":8,"h":4,"volume_m3":80},
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
