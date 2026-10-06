import copy
import json
from pathlib import Path
import unittest

from airtrajectory.contam_allocator import allocate_contam_ids
from airtrajectory.contam_ir import compile_contam_ir
from airtrajectory.contam_profile import (
    bind_airflow_elements,
    illustrative_opening_profile,
)
from airtrajectory.layout import LayoutContract


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"


def metric_manifest():
    payload = json.loads(LAYOUT.read_text(encoding="utf-8"))
    for wall in payload["walls"]:
        wall["length_m"] = 5.0
        wall["azimuth_deg"] = 90.0
    for opening in payload["openings"]:
        opening["width_m"] = 1.2
        opening["height_m"] = 2.0
        opening["sill_height_m"] = 0.2 if opening["kind"] == "door" else 0.9
        opening["max_area_m2"] = min(opening["max_area_m2"], 2.4)
    layout = LayoutContract.from_dict(payload)
    return allocate_contam_ids(compile_contam_ir(layout))


class ContamProfileTests(unittest.TestCase):
    def test_demo_profile_binds_all_current_openings(self):
        bound = bind_airflow_elements(
            metric_manifest(),
            illustrative_opening_profile(),
        )

        self.assertEqual(bound["compiler"], "contam-bound-manifest")
        self.assertEqual(len(bound["airflow_elements"]), 5)
        self.assertEqual(len(bound["element_numbers"]), 5)
        self.assertEqual(
            bound["writer_contract"]["airflow_element_binding"],
            "implemented",
        )
        self.assertFalse(bound["writer_contract"]["ready"])
        self.assertFalse(bound["airflow_profile"]["engineering_validated"])
        window_path = next(p for p in bound["flow_paths"] if p["layout_opening_id"] == "W1")
        self.assertEqual(window_path["airflow_element"]["closed_leakage_multiplier"], 0.01)

    def test_each_path_references_deterministic_element_number(self):
        bound = bind_airflow_elements(
            metric_manifest(),
            illustrative_opening_profile(),
        )
        for path in bound["flow_paths"]:
            ref = path["airflow_element"]
            self.assertEqual(
                ref["contam_element_number"],
                bound["element_numbers"][ref["key"]],
            )

    def test_source_order_does_not_change_element_mapping(self):
        manifest = metric_manifest()
        reversed_manifest = copy.deepcopy(manifest)
        reversed_manifest["flow_paths"] = list(
            reversed(reversed_manifest["flow_paths"])
        )
        profile = illustrative_opening_profile()

        a = bind_airflow_elements(manifest, profile)
        b = bind_airflow_elements(reversed_manifest, profile)

        self.assertEqual(a["element_numbers"], b["element_numbers"])
        self.assertEqual(
            a["airflow_binding_sha256"],
            b["airflow_binding_sha256"],
        )

    def test_production_gate_rejects_illustrative_profile(self):
        with self.assertRaisesRegex(ValueError, "engineering-validated"):
            bind_airflow_elements(
                metric_manifest(),
                illustrative_opening_profile(),
                require_engineering_validated=True,
            )

    def test_missing_opening_kind_rule_fails_closed(self):
        profile = illustrative_opening_profile()
        del profile["rules"]["door"]
        with self.assertRaisesRegex(ValueError, "no rule"):
            bind_airflow_elements(metric_manifest(), profile)

    def test_invalid_closed_leakage_multiplier_fails_closed(self):
        profile = illustrative_opening_profile()
        profile["rules"]["window"]["closed_leakage_multiplier"] = 1.0
        with self.assertRaisesRegex(ValueError, "closed_leakage_multiplier"):
            bind_airflow_elements(metric_manifest(), profile)

    def test_invalid_engineering_parameter_fails_closed(self):
        profile = illustrative_opening_profile()
        profile["rules"]["window"]["discharge_coefficient"] = 1.2
        with self.assertRaisesRegex(ValueError, "discharge_coefficient"):
            bind_airflow_elements(metric_manifest(), profile)


if __name__ == "__main__":
    unittest.main()
