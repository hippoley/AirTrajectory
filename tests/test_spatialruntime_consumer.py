import os
import unittest
from unittest.mock import patch

from airtrajectory.spatialruntime_consumer import (
    SpatialRuntimeConsumerError,
    _spatialruntime_commit_sha,
    native_branch_result_from_stable,
    stable_mappings_from_provenance,
)


class SpatialRuntimeConsumerMappingTests(unittest.TestCase):
    def setUp(self):
        self.provenance = {
            "zone_numbers": {
                "zone:living": 1,
                "zone:bedroom": 2,
                "zone:study": 3,
            },
            "path_numbers": {
                "path:D1": 1,
                "path:D2": 2,
                "path:W1": 3,
                "path:W2": 4,
                "path:W3": 5,
            },
        }
        self.inventory = {
            "flow_paths": [
                {"number": 1, "flow_element_number": 11},
                {"number": 2, "flow_element_number": 12},
                {"number": 3, "flow_element_number": 21},
                {"number": 4, "flow_element_number": 22},
                {"number": 5, "flow_element_number": 23},
            ]
        }

    def test_stable_ids_are_bound_to_actual_native_path_elements(self):
        mappings = stable_mappings_from_provenance(
            self.provenance,
            self.inventory,
        )
        self.assertEqual(
            mappings["zones"],
            {
                "bedroom": {"contam_zone_number": 2},
                "living": {"contam_zone_number": 1},
                "study": {"contam_zone_number": 3},
            },
        )
        self.assertEqual(
            mappings["flow_paths"]["W1"],
            {
                "contam_path_number": 3,
                "contam_flow_element_number": 21,
            },
        )
        self.assertEqual(set(mappings["flow_paths"]), {"D1", "D2", "W1", "W2", "W3"})

    def test_missing_native_path_fails_closed(self):
        broken = {
            "flow_paths": [
                row for row in self.inventory["flow_paths"] if row["number"] != 5
            ]
        }
        with self.assertRaisesRegex(
            SpatialRuntimeConsumerError,
            "missing CONTAM path 5",
        ):
            stable_mappings_from_provenance(self.provenance, broken)

    def test_missing_flow_element_number_fails_closed(self):
        broken = {
            "flow_paths": [
                {"number": 1, "flow_element_number": 11},
                {"number": 2, "flow_element_number": 12},
                {"number": 3, "flow_element_number": 21},
                {"number": 4, "flow_element_number": 22},
                {"number": 5},
            ]
        }
        with self.assertRaisesRegex(
            SpatialRuntimeConsumerError,
            "has no flow_element_number",
        ):
            stable_mappings_from_provenance(self.provenance, broken)


    def test_real_branch_results_are_converted_back_to_native_ids(self):
        branch = {
            "label": "Joint",
            "end_co2_ppm_by_zone": {
                "living": 1001.25,
                "bedroom": 812.5,
                "study": 903.75,
            },
            "path_flow_kg_s": {
                "D1": -0.11,
                "D2": 0.07,
                "W1": -0.31,
                "W2": 0.22,
                "W3": -0.04,
            },
            "evidence_level": "real-contam-test",
            "trusted_for_promotion": False,
        }
        native = native_branch_result_from_stable(branch, self.provenance)
        self.assertEqual(native["source_format"], "airtrajectory_real_contam_branch")
        self.assertEqual(
            {row["native_zone_number"]: row["co2_ppm"] for row in native["zones"]},
            {1: 1001.25, 2: 812.5, 3: 903.75},
        )
        self.assertEqual(
            {row["native_path_number"]: row["mass_flow_kg_s"] for row in native["paths"]},
            {1: -0.11, 2: 0.07, 3: -0.31, 4: 0.22, 5: -0.04},
        )
        self.assertEqual(
            native["execution"]["schema"],
            "airtrajectory_real_contam_branch_execution_v1",
        )

    def test_real_branch_result_requires_complete_path_coverage(self):
        branch = {
            "label": "broken",
            "end_co2_ppm_by_zone": {
                "living": 1000.0,
                "bedroom": 800.0,
                "study": 900.0,
            },
            "path_flow_kg_s": {
                "D1": 0.1,
                "D2": 0.1,
                "W1": 0.1,
                "W2": 0.1,
            },
        }
        with self.assertRaisesRegex(
            SpatialRuntimeConsumerError,
            "path results do not exactly cover",
        ):
            native_branch_result_from_stable(branch, self.provenance)


    def test_spatialruntime_commit_sha_is_validated(self):
        with patch.dict(os.environ, {"SPATIALRUNTIME_COMMIT_SHA": "a" * 40}, clear=False):
            self.assertEqual(_spatialruntime_commit_sha(), "a" * 40)
        with patch.dict(os.environ, {"SPATIALRUNTIME_COMMIT_SHA": "not-a-git-sha"}, clear=False):
            with self.assertRaisesRegex(
                SpatialRuntimeConsumerError,
                "40-char git SHA",
            ):
                _spatialruntime_commit_sha()


if __name__ == "__main__":
    unittest.main()
