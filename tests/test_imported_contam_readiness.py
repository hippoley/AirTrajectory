import unittest
from dataclasses import asdict
from airtrajectory.layout import LayoutContract
from airtrajectory.imported_contam_readiness import verify_imported_contam_readiness
def fixture():
    return LayoutContract.from_dict({
        "schema_version":"0.1","topology_id":"import:test","source_kind":"imported-floorplan",
        "outside_id":"OUTSIDE",
        "capabilities":{"floorplan_geometry_editable":True,"opening_position_editable":True,
                        "opening_state_editable":True,"arbitrary_topology_import":"supported",
                        "contam_compiler":"reserved"},
        "source_provenance":{"format":"JSON","source_sha256":"a"*64,
                             "importer":{"id":"test","version":"1"}},
        "rooms":[{"id":"r1","name":"R1","x":0,"y":0,"w":4,"h":4,"volume_m3":40}],
        "walls":[{"id":"w1","kind":"exterior","source":"r1","target":"OUTSIDE",
                  "x1":0,"y1":0,"x2":0,"y2":4}],
        "openings":[{"id":"o1","kind":"window","wall_id":"w1","source":"r1",
                     "target":"OUTSIDE","position_t":0.5,"initial_open_pct":0,
                     "max_area_m2":1,"render_side":"left","position_editable":True,
                     "state_editable":True}],
        "compiler_contract":{},
    })


class ImportedContamReadinessTests(unittest.TestCase):
    def test_missing_metric_geometry_is_not_solver_ready(self):
        receipt=verify_imported_contam_readiness(fixture())
        self.assertEqual(receipt["topology_status"],"PASS")
        self.assertEqual(receipt["contam_ir_status"],"BLOCKED")
        self.assertEqual(receipt["status"],"BLOCKED")
        self.assertIn("metric-input ready",receipt["blockers"][0])
        self.assertEqual(receipt["evidence_level"],"COMPILE_READINESS_ONLY_NOT_SOLVED")

    def test_metric_complete_layout_reaches_symbolic_contam_ir_only(self):
        source=fixture()
        payload={
            "schema_version":source.schema_version,"topology_id":source.topology_id,
            "source_kind":source.source_kind,"outside_id":source.outside_id,
            "capabilities":source.capabilities,"source_provenance":source.source_provenance,
            "rooms":[asdict(v) for v in source.rooms],
            "walls":[asdict(v) for v in source.walls],
            "openings":[asdict(v) for v in source.openings],
            "compiler_contract":source.compiler_contract,
        }
        payload["walls"][0].update(length_m=4.0,azimuth_deg=270.0)
        payload["openings"][0].update(width_m=1.0,height_m=1.0,sill_height_m=1.0)
        ready=verify_imported_contam_readiness(LayoutContract.from_dict(payload))
        self.assertEqual(ready["status"],"PASS")
        self.assertEqual(ready["contam_ir_status"],"PASS")
        self.assertEqual(len(ready["contam_ir_sha256"]),64)
        self.assertEqual(ready["evidence_level"],"COMPILE_READINESS_ONLY_NOT_SOLVED")

    def test_fixed_demo_is_not_mislabeled_imported_layout(self):
        source=fixture()
        payload={
            "schema_version":source.schema_version,"topology_id":source.topology_id,
            "source_kind":"fixed-floorplan","outside_id":source.outside_id,
            "capabilities":dict(source.capabilities),
            "source_provenance":source.source_provenance,
            "rooms":[asdict(v) for v in source.rooms],
            "walls":[asdict(v) for v in source.walls],
            "openings":[asdict(v) for v in source.openings],
            "compiler_contract":source.compiler_contract,
        }
        payload["capabilities"]["floorplan_geometry_editable"]=False
        payload["capabilities"]["arbitrary_topology_import"]="reserved"
        layout=LayoutContract.from_dict(payload)
        with self.assertRaisesRegex(ValueError,"imported-floorplan"):
            verify_imported_contam_readiness(layout)


if __name__=="__main__":
    unittest.main()
