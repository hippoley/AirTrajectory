from pathlib import Path
import unittest

from airtrajectory.layout import LayoutContract
from airtrajectory.ventilation_path_contract import (
    build_ventilation_path_contract,
)


ROOT = Path(__file__).resolve().parents[1]
PRIMARY = ROOT / "web" / "data" / "home_topology.fixed.json"
ALTERNATE = ROOT / "tests" / "data" / "topology.alt-two-room.json"


class VentilationPathContractTests(unittest.TestCase):
    def test_primary_contract_is_deterministic_and_topology_bound(self):
        layout = LayoutContract.from_file(PRIMARY)
        a = build_ventilation_path_contract(layout)
        b = build_ventilation_path_contract(layout)

        self.assertEqual(a, b)
        self.assertEqual(
            a["contract"],
            "airtrajectory-ventilation-path-v0.1",
        )
        self.assertEqual(a["topology_id"], layout.topology_id)
        self.assertEqual(a["topology_sha256"], layout.sha256())
        self.assertEqual(len(a["contract_sha256"]), 64)
        self.assertEqual(len(a["paths"]), 3)
        self.assertTrue(
            all(
                row["semantics"]["effectiveness"] == "unverified"
                for row in a["paths"]
            )
        )

    def test_alternate_topology_emits_non_demo_path_identity(self):
        layout = LayoutContract.from_file(ALTERNATE)
        receipt = build_ventilation_path_contract(layout)

        self.assertEqual(len(receipt["paths"]), 1)
        path = receipt["paths"][0]
        self.assertEqual(
            path["opening_ids"],
            ["AX", "LINK9", "BZ"],
        )
        self.assertEqual(
            path["zones"],
            ["zone_alpha", "zone_beta"],
        )
        self.assertEqual(
            path["semantics"]["directionality"],
            "undirected-candidate",
        )


if __name__ == "__main__":
    unittest.main()
