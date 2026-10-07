from pathlib import Path
import unittest

from airtrajectory.layout import LayoutContract
from airtrajectory.ventilation_path_candidates import (
    build_ventilation_path_joint_candidates,
    inject_ventilation_path_candidates,
)


ROOT = Path(__file__).resolve().parents[1]
PRIMARY = ROOT / "web" / "data" / "home_topology.fixed.json"
ALTERNATE = ROOT / "tests" / "data" / "topology.alt-two-room.json"


class VentilationPathCandidateTests(unittest.TestCase):
    def test_primary_topology_compiles_three_paths_at_each_intensity(self):
        topology = LayoutContract.from_file(PRIMARY).to_building_topology()
        rows = build_ventilation_path_joint_candidates(
            topology,
            intensities=(50, 75),
        )

        self.assertEqual(len(rows), 6)
        labels = {row["label"] for row in rows}
        self.assertIn("ventpath:W1->W2@50", labels)
        self.assertIn("ventpath:W1->W3@75", labels)
        self.assertIn("ventpath:W2->W3@50", labels)

        living_bedroom = next(
            row for row in rows
            if row["label"] == "ventpath:W1->W2@75"
        )
        self.assertEqual(
            living_bedroom["opening_pct"],
            {"W1": 75.0, "W2": 75.0, "W3": 0.0},
        )
        self.assertEqual(
            living_bedroom["ventilation_path"]["opening_ids"],
            ["W1", "D1", "W2"],
        )

    def test_alternate_topology_uses_only_discovered_ids(self):
        topology = LayoutContract.from_file(ALTERNATE).to_building_topology()
        rows = build_ventilation_path_joint_candidates(
            topology,
            intensities=(60,),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["label"], "ventpath:AX->BZ@60")
        self.assertEqual(
            rows[0]["opening_pct"],
            {"AX": 60.0, "BZ": 60.0},
        )
        self.assertEqual(
            rows[0]["ventilation_path"]["opening_ids"],
            ["AX", "LINK9", "BZ"],
        )

    def test_injection_replaces_manual_candidates_without_mutating_input(self):
        topology = LayoutContract.from_file(PRIMARY).to_building_topology()
        original = {
            "schema_version": "0.1",
            "joint_candidates": [{"label": "manual", "opening_pct": {}}],
        }
        result = inject_ventilation_path_candidates(
            original,
            topology,
            intensities=(55,),
        )

        self.assertEqual(original["joint_candidates"][0]["label"], "manual")
        self.assertEqual(
            result["candidate_source"],
            "topology-derived-ventilation-paths",
        )
        self.assertEqual(len(result["joint_candidates"]), 3)
        self.assertEqual(len(result["ventilation_path_candidates"]), 3)

    def test_invalid_intensity_fails_closed(self):
        topology = LayoutContract.from_file(PRIMARY).to_building_topology()
        with self.assertRaisesRegex(ValueError, "intensities"):
            build_ventilation_path_joint_candidates(
                topology,
                intensities=(120,),
            )


if __name__ == "__main__":
    unittest.main()
