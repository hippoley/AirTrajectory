"""Review candidate signals are never automatic engineering approval."""
import unittest
from examples.build_ifc_adjacency_review_queue import build_adjacency_review_queue

class IFCAdjacencyReviewTests(unittest.TestCase):
    def test_cross_evidence_and_no_auto_adoption(self):
        report={"source":{"sha256":"a"*64},"control_scope":{"mode":"ALL_OPENINGS"},
                "blockers":[{"entity_id":"W1","reason":"AMBIGUOUS_SPACE_ADJACENCY"}],
                "semantics":{"spaces":[{"id":"R1"},{"id":"R2"}],
                             "openings":[{"id":"W1","kind":"window","adjacent_spaces":[],
                                          "ifc_host_element_ids":["H1"],
                                          "host_boundary_space_candidates":["R1","R2"],
                                          "bbox_intersection_space_candidates":["R1"]}]}}
        result=build_adjacency_review_queue(report)
        self.assertEqual(result["items"][0]["corroborated_candidates"],["R1"])
        self.assertIsNone(result["items"][0]["adopted_adjacency"])
        self.assertFalse(result["contam_prj_authorized"])
    def test_unknown_space_and_filtered_source_are_rejected(self):
        base={"source":{"sha256":"a"*64},"control_scope":{"mode":"ALL_OPENINGS"},
              "blockers":[{"entity_id":"W1","reason":"AMBIGUOUS_SPACE_ADJACENCY"}],
              "semantics":{"spaces":[{"id":"R1"}],
                           "openings":[{"id":"W1","adjacent_spaces":[],
                                        "host_boundary_space_candidates":["UNKNOWN"]}]}}
        with self.assertRaisesRegex(ValueError,"not present"):
            build_adjacency_review_queue(base)
        base["control_scope"]["mode"]="SELECTED"
        with self.assertRaisesRegex(ValueError,"full IFC"):
            build_adjacency_review_queue(base)

if __name__=="__main__":
    unittest.main()
