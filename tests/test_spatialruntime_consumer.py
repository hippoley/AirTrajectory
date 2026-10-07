import unittest

from airtrajectory.spatialruntime_consumer import (
    SpatialRuntimeConsumerError,
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


if __name__ == "__main__":
    unittest.main()
