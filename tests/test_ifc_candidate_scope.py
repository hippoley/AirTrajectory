"""Adversarial scope-selection checks using a minimal full-source IFC receipt."""
import copy
import unittest

from examples.select_ifc_control_scope import scope_candidate_receipt


class IFCScopeCandidateTests(unittest.TestCase):
    def setUp(self):
        self.original = {
            "source": {"sha256": "a" * 64},
            "control_scope": {"mode": "ALL_OPENINGS"},
            "opening_count": 3,
            "status": "BLOCKED",
            "blockers": [{"entity_id": "W2", "reason": "AMBIGUOUS_SPACE_ADJACENCY"}],
            "semantics": {"openings": [
                {"id": "W1", "kind": "window", "adjacent_spaces": ["S1"],
                 "width_m": 1.2, "height_m": 1.0},
                {"id": "W2", "kind": "window", "adjacent_spaces": [],
                 "width_m": 1.2, "height_m": 1.0},
                {"id": "D1", "kind": "door", "adjacent_spaces": ["S1", "S2"],
                 "width_m": 0.9, "height_m": 2.0},
            ]},
        }

    def test_scope_keeps_full_source_blocked_and_lists_exclusions(self):
        result = scope_candidate_receipt(self.original)
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["excluded_count"], 1)
        self.assertEqual(result["excluded_openings"][0]["opening_id"], "W2")
        self.assertEqual(result["original_full_scope_status"], "BLOCKED")
        self.assertFalse(result["prj_compilation_authorized"])

    def test_adversarial_duplicate_unknown_scope_and_accounting_rejected(self):
        for mutation in ("duplicate", "filtered", "lost"):
            case = copy.deepcopy(self.original)
            if mutation == "duplicate":
                case["semantics"]["openings"][1]["id"] = "W1"
            elif mutation == "filtered":
                case["control_scope"]["mode"] = "SELECTED_OPENINGS"
            else:
                case["opening_count"] = 4
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                scope_candidate_receipt(case)

    def test_original_blocker_never_promoted_to_candidate(self):
        case = copy.deepcopy(self.original)
        case["semantics"]["openings"][1]["adjacent_spaces"] = ["S2"]
        result = scope_candidate_receipt(case)
        self.assertEqual(result["excluded_count"], 1)
        self.assertFalse(result["prj_compilation_authorized"])


if __name__ == "__main__":
    unittest.main()
