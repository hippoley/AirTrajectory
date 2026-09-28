import json
import tempfile
import unittest
from pathlib import Path

from airtrajectory.topology_source import (
    DEFAULT_FIXED_TOPOLOGY_PATH,
    TopologyManifest,
    load_fixed_topology,
)


class TopologySourceTests(unittest.TestCase):
    def test_fixed_manifest_builds_runtime_topology(self):
        manifest=load_fixed_topology()
        topology=manifest.to_building_topology()

        self.assertEqual(manifest.topology_id,"demo.fixed-three-room.v1")
        self.assertEqual(set(topology.zones),{"living","bedroom","study"})
        self.assertEqual(
            set(topology.openings),
            {"W1","W2","W3","D1","D2"},
        )
        self.assertFalse(manifest.edit_policy["layout_mutable"])
        self.assertTrue(
            manifest.edit_policy["opening_position_mutable"]
        )

    def test_opening_positions_can_change_without_changing_connectivity(self):
        manifest=load_fixed_topology()
        changed=manifest.with_opening_positions({
            "W1":0.72,
            "D1":0.25,
        })

        before=manifest.to_building_topology()
        after=changed.to_building_topology()

        self.assertEqual(
            {
                k:(v.source,v.target,v.kind,v.max_area_m2)
                for k,v in before.openings.items()
            },
            {
                k:(v.source,v.target,v.kind,v.max_area_m2)
                for k,v in after.openings.items()
            },
        )
        self.assertEqual(changed.opening_positions()["W1"],0.72)
        self.assertEqual(changed.opening_positions()["D1"],0.25)
        self.assertNotEqual(manifest.sha256,changed.sha256)

    def test_opening_position_outside_wall_is_rejected(self):
        manifest=load_fixed_topology()
        with self.assertRaisesRegex(ValueError,"within"):
            manifest.with_opening_positions({"W1":1.2})

    def test_unknown_opening_position_is_rejected(self):
        manifest=load_fixed_topology()
        with self.assertRaisesRegex(ValueError,"unknown opening"):
            manifest.with_opening_positions({"W404":0.5})

    def test_contam_compile_contract_is_reserved_not_fake_prj(self):
        manifest=load_fixed_topology()
        contract=manifest.contam_compile_contract()

        self.assertEqual(contract["status"],"RESERVED")
        self.assertEqual(contract["compiler"],"topology-to-contam")
        self.assertEqual(
            contract["topology_manifest_sha256"],
            manifest.sha256,
        )
        self.assertEqual(
            {o["id"] for o in contract["openings"]},
            {"W1","W2","W3","D1","D2"},
        )
        self.assertIsNone(contract["reserved_outputs"]["prj_path"])
        self.assertIsNone(
            contract["reserved_outputs"]["opening_controls"]
        )
        self.assertIn(
            "not claimed complete",
            contract["note"],
        )

    def test_contam_compile_contract_reflects_moved_opening(self):
        manifest=load_fixed_topology().with_opening_positions({"W2":0.8})
        contract=manifest.contam_compile_contract()
        w2=next(o for o in contract["openings"] if o["id"]=="W2")
        self.assertEqual(w2["position_on_wall"],0.8)

    def test_trajectory_context_carries_topology_identity_and_positions(self):
        manifest=load_fixed_topology().with_opening_positions({
            "W1":0.41,
            "D2":0.61,
        })
        context=manifest.trajectory_context()

        self.assertEqual(
            context["topology_manifest_sha256"],
            manifest.sha256,
        )
        self.assertEqual(context["topology_provider"],"fixed-json")
        self.assertFalse(context["edit_policy"]["layout_mutable"])
        self.assertEqual(context["opening_positions"]["W1"],0.41)
        self.assertEqual(context["opening_positions"]["D2"],0.61)

    def test_fixed_provider_rejects_layout_mutation_policy(self):
        payload=json.loads(
            Path(DEFAULT_FIXED_TOPOLOGY_PATH).read_text(
                encoding="utf-8"
            )
        )
        payload["edit_policy"]["layout_mutable"]=True
        model=TopologyManifest(payload)
        with self.assertRaisesRegex(ValueError,"layout_mutable=False"):
            model.validate()


if __name__=="__main__":
    unittest.main()
