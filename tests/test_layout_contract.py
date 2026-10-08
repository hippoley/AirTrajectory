import copy
import json
from pathlib import Path
import unittest

from airtrajectory.layout import LayoutContract


ROOT=Path(__file__).resolve().parents[1]
LAYOUT=ROOT/"web"/"data"/"home_topology.fixed.json"


class LayoutContractTests(unittest.TestCase):
    def _payload(self):
        return json.loads(LAYOUT.read_text(encoding="utf-8"))

    def test_fixed_layout_contract_projects_to_building_topology(self):
        contract=LayoutContract.from_dict(self._payload())
        building=contract.to_building_topology()

        self.assertEqual(contract.source_kind,"fixed-floorplan")
        self.assertFalse(
            contract.capabilities["floorplan_geometry_editable"]
        )
        self.assertTrue(
            contract.capabilities["opening_position_editable"]
        )
        self.assertEqual(
            contract.capabilities["arbitrary_topology_import"],
            "reserved",
        )
        self.assertEqual(
            contract.capabilities["contam_compiler"],
            "reserved",
        )
        self.assertEqual(
            set(building.zones),
            {"living","bedroom","study"},
        )
        self.assertEqual(
            set(building.openings),
            {"W1","W2","W3","D1","D2"},
        )
        self.assertEqual(building.openings["W1"].source,"living")
        self.assertEqual(building.openings["W1"].target,"OUTSIDE")
        self.assertEqual(building.openings["D1"].target,"bedroom")

    def test_all_current_windows_and_doors_are_position_editable(self):
        contract=LayoutContract.from_dict(self._payload())
        self.assertTrue(contract.openings)
        self.assertTrue(all(o.position_editable for o in contract.openings))
        self.assertEqual(
            {o.kind for o in contract.openings},
            {"window","door"},
        )

    def test_moving_opening_position_does_not_change_connectivity(self):
        original=self._payload()
        moved=copy.deepcopy(original)
        target=next(o for o in moved["openings"] if o["id"]=="D1")
        target["position_t"]=0.72

        a=LayoutContract.from_dict(original).to_building_topology()
        b=LayoutContract.from_dict(moved).to_building_topology()

        self.assertEqual(a.zones,b.zones)
        self.assertEqual(a.openings,b.openings)

    def test_trajectory_context_binds_opening_positions_without_mutating_layout(self):
        contract=LayoutContract.from_dict(self._payload())
        context=contract.trajectory_context(
            topology_revision=3,
            opening_positions={"W1":0.72,"D1":0.25},
        )

        self.assertEqual(context["topology_id"],contract.topology_id)
        self.assertEqual(context["topology_revision"],3)
        self.assertEqual(context["opening_positions"]["W1"],0.72)
        self.assertEqual(context["opening_positions"]["D1"],0.25)
        self.assertFalse(
            context["capabilities"]["floorplan_geometry_editable"]
        )
        self.assertEqual(
            len(context["layout_contract_sha256"]),
            64,
        )

    def test_reserved_contam_contract_reflects_current_opening_positions(self):
        contract=LayoutContract.from_dict(self._payload())
        compiled=contract.contam_compile_contract(
            opening_positions={"W2":0.81,"D2":0.18},
        )

        self.assertEqual(compiled["status"],"RESERVED")
        self.assertEqual(compiled["compiler"],"topology-to-contam")
        self.assertIsNone(compiled["reserved_outputs"]["prj_path"])
        self.assertIsNone(
            compiled["reserved_outputs"]["opening_controls"]
        )
        positions={
            opening["id"]:opening["position_t"]
            for opening in compiled["openings"]
        }
        self.assertEqual(positions["W2"],0.81)
        self.assertEqual(positions["D2"],0.18)
        self.assertIn("not claimed complete",compiled["note"])

    def test_contam_contract_keeps_connectivity_when_window_moves(self):
        contract=LayoutContract.from_dict(self._payload())
        base=contract.contam_compile_contract()
        moved=contract.contam_compile_contract(
            opening_positions={"W1":0.9},
        )

        base_w1=next(x for x in base["openings"] if x["id"]=="W1")
        moved_w1=next(x for x in moved["openings"] if x["id"]=="W1")
        self.assertEqual(base_w1["source"],moved_w1["source"])
        self.assertEqual(base_w1["target"],moved_w1["target"])
        self.assertEqual(base_w1["wall_id"],moved_w1["wall_id"])
        self.assertNotEqual(
            base_w1["position_t"],
            moved_w1["position_t"],
        )

    def test_trajectory_and_contam_reject_unknown_opening_override(self):
        contract=LayoutContract.from_dict(self._payload())
        with self.assertRaisesRegex(ValueError,"unknown opening"):
            contract.trajectory_context(
                opening_positions={"W404":0.5},
            )
        with self.assertRaisesRegex(ValueError,"unknown opening"):
            contract.contam_compile_contract(
                opening_positions={"W404":0.5},
            )

    def test_current_contract_rejects_floorplan_geometry_editing(self):
        payload=self._payload()
        payload["capabilities"]["floorplan_geometry_editable"]=True
        with self.assertRaisesRegex(ValueError,"floorplan geometry fixed"):
            LayoutContract.from_dict(payload)

    def test_structured_topology_is_accepted_as_external_import_boundary(self):
        payload=self._payload()
        payload["topology_id"]="external.structured.v1"
        payload["source_kind"]="structured-topology"
        payload["capabilities"]["arbitrary_topology_import"]=True
        contract=LayoutContract.from_dict(payload)
        self.assertEqual(contract.source_kind,"structured-topology")
        self.assertTrue(contract.capabilities["arbitrary_topology_import"])
        self.assertEqual(
            set(contract.to_building_topology().openings),
            {"W1","W2","W3","D1","D2"},
        )

    def test_unknown_source_kind_remains_rejected(self):
        payload=self._payload()
        payload["source_kind"]="magic-floorplan-parser"
        with self.assertRaisesRegex(ValueError,"unsupported layout source_kind"):
            LayoutContract.from_dict(payload)

    def test_structured_topology_must_declare_import_capability(self):
        payload=self._payload()
        payload["source_kind"]="structured-topology"
        with self.assertRaisesRegex(ValueError,"arbitrary_topology_import=true"):
            LayoutContract.from_dict(payload)

    def test_opening_must_stay_on_declared_wall(self):
        payload=self._payload()
        payload["openings"][0]["wall_id"]="missing-wall"
        with self.assertRaisesRegex(ValueError,"unknown wall"):
            LayoutContract.from_dict(payload)

    def test_opening_endpoints_must_match_wall_connectivity(self):
        payload=self._payload()
        payload["openings"][0]["target"]="bedroom"
        with self.assertRaisesRegex(ValueError,"endpoints do not match"):
            LayoutContract.from_dict(payload)


if __name__=="__main__":
    unittest.main()
