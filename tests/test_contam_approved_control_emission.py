"""Approval scope must affect actual CONTAM control-node generation."""
import unittest
from airtrajectory.contam_prj_serializer import _dynamic_window_controls


class ApprovedControlEmissionTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "flow_paths": [
                {"layout_opening_id": "W1", "kind": "window", "boundary_kind": "exterior",
                 "contam_path_number": 10, "airflow_element": {"closed_leakage_multiplier": 0.02}},
                {"layout_opening_id": "W2", "kind": "window", "boundary_kind": "exterior",
                 "contam_path_number": 11, "airflow_element": {"closed_leakage_multiplier": 0.02}},
                {"layout_opening_id": "D1", "kind": "door", "boundary_kind": "interior",
                 "contam_path_number": 12, "airflow_element": {"closed_leakage_multiplier": 0.02}},
            ]
        }

    def test_only_approved_windows_get_input_nodes(self):
        self.manifest["approved_control_opening_ids"] = ["W2"]
        controls = _dynamic_window_controls(self.manifest)
        self.assertEqual([x["opening_id"] for x in controls], ["W2"])
        self.assertEqual(controls[0]["path_number"], 11)

    def test_explicit_empty_scope_is_not_legacy_all_windows(self):
        self.manifest["approved_control_opening_ids"] = []
        self.assertEqual(_dynamic_window_controls(self.manifest), [])

    def test_unapproved_internal_door_or_missing_window_rejected(self):
        for selected in (["D1"], ["W3"], ["W1", "W1"]):
            with self.subTest(selected=selected):
                self.manifest["approved_control_opening_ids"] = selected
                with self.assertRaises(ValueError):
                    _dynamic_window_controls(self.manifest)


if __name__ == "__main__":
    unittest.main()
