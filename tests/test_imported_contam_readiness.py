import unittest
from dataclasses import asdict
from airtrajectory.layout import LayoutContract
from airtrajectory.imported_contam_readiness import verify_imported_contam_readiness
from tests.test_layout_correction import fixture


class ImportedContamReadinessTests(unittest.TestCase):
    def test_missing_metric_geometry_is_not_solver_ready(self):
        receipt=verify_imported_contam_readiness(fixture())
        self.assertEqual(receipt["topology_status"],"PASS")
        self.assertEqual(receipt["contam_ir_status"],"BLOCKED")
        self.assertEqual(receipt["status"],"BLOCKED")
        self.assertIn("metric-input ready",receipt["blockers"][0])
        self.assertEqual(receipt["evidence_level"],"COMPILE_READINESS_ONLY_NOT_SOLVED")

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
