from pathlib import Path
import unittest

from airtrajectory.layout import LayoutContract
from airtrajectory.topology_acceptance import (
    verify_topology_files,
    verify_topology_runtime,
)


ROOT = Path(__file__).resolve().parents[1]
PRIMARY = ROOT / "web" / "data" / "home_topology.fixed.json"
ALTERNATE = ROOT / "tests" / "data" / "topology.alt-two-room.json"
IMPORTED = ROOT / "tests" / "data" / "topology.imported-four-room.json"


class CrossTopologyAcceptanceTests(unittest.TestCase):
    def test_alternate_topology_reaches_all_runtime_consumers_without_fixed_ids(self):
        layout = LayoutContract.from_file(ALTERNATE)
        receipt = verify_topology_runtime(layout)

        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(
            receipt["expected"]["zone_ids"],
            ["zone_alpha", "zone_beta"],
        )
        self.assertEqual(
            receipt["expected"]["opening_ids"],
            ["AX", "BZ", "LINK9"],
        )
        self.assertEqual(
            receipt["observed"]["policy_action_ids"],
            ["AX", "BZ", "LINK9"],
        )
        self.assertNotIn("W1", receipt["observed"]["policy_action_ids"])
        self.assertTrue(all(receipt["checks"].values()))

    def test_imported_topology_reaches_same_runtime_without_demo_ids(self):
        layout = LayoutContract.from_file(IMPORTED)
        self.assertEqual(layout.source_kind, "imported-floorplan")
        self.assertEqual(
            layout.capabilities["arbitrary_topology_import"],
            "supported",
        )
        receipt = verify_topology_runtime(layout)

        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(
            receipt["expected"]["zone_ids"],
            ["center_room", "east_room", "north_room", "south_room"],
        )
        self.assertEqual(len(receipt["expected"]["opening_ids"]), 6)
        self.assertNotIn("W1", receipt["observed"]["policy_action_ids"])
        self.assertTrue(all(receipt["checks"].values()))

    def test_three_distinct_topologies_pass_same_runtime_contract(self):
        result = verify_topology_files([PRIMARY, ALTERNATE, IMPORTED])

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["topology_count"], 3)
        self.assertTrue(result["distinct_topology_ids"])
        self.assertTrue(result["distinct_opening_vocabularies"])
        self.assertEqual(
            [receipt["status"] for receipt in result["receipts"]],
            ["PASS", "PASS", "PASS"],
        )

    def test_duplicate_topology_is_rejected_as_fake_portability_evidence(self):
        with self.assertRaisesRegex(ValueError, "distinct topology_id"):
            verify_topology_files([PRIMARY, PRIMARY])


if __name__ == "__main__":
    unittest.main()
