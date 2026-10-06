import json
from pathlib import Path
import unittest

from airtrajectory.contam_allocator import allocate_contam_ids
from airtrajectory.contam_boundary import bind_boundary_profile
from airtrajectory.contam_ir import compile_contam_ir
from airtrajectory.contam_profile import bind_airflow_elements, illustrative_opening_profile
from airtrajectory.contam_prj_profile import (
    bind_prj_serialization_profile,
    ppmv_to_mass_fraction,
)
from airtrajectory.layout import LayoutContract


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"


def forced_manifest():
    payload = json.loads(LAYOUT.read_text(encoding="utf-8"))
    for wall in payload["walls"]:
        wall["length_m"] = 5.0
        wall["azimuth_deg"] = 90.0
    for opening in payload["openings"]:
        opening["width_m"] = 1.0
        opening["height_m"] = 2.0
        opening["sill_height_m"] = 0.5
        opening["max_area_m2"] = min(opening["max_area_m2"], 2.0)
    layout = LayoutContract.from_dict(payload)
    manifest = allocate_contam_ids(compile_contam_ir(layout))
    manifest = bind_airflow_elements(manifest, illustrative_opening_profile())
    boundary = {
        "schema_version": "0.1",
        "profile_id": "boundary",
        "engineering_validated": False,
        "weather": {
            "wind_speed_m_s": 1.5,
            "wind_direction_deg": 180.0,
            "outdoor_temperature_c": 25.0,
            "barometric_pressure_pa": 101325.0,
        },
        "contaminants": [{
            "key": "co2",
            "name": "CO2",
            "unit": "ppm",
            "outdoor_concentration": 430.0,
            "initial_zone_concentration": {
                "zone:living": 1400.0,
                "zone:bedroom": 900.0,
                "zone:study": 800.0,
            },
        }],
    }
    return bind_boundary_profile(manifest, boundary)


def profile():
    return {
        "schema_version": "0.1",
        "profile_id": "test-prj-profile",
        "engineering_validated": False,
        "zone_defaults": {
            "level_number": 1,
            "relative_height_m": 0.0,
            "initial_temperature_k": 298.15,
            "initial_pressure_pa": 0.0,
        },
        "airflow_element_storage": {
            "window": {
                "hydraulic_diameter_m": 1.0,
                "laminar_flow_coefficient": 0.0,
                "turbulent_flow_coefficient": 0.0,
                "transition_reynolds_number": 30.0,
            },
            "door": {
                "hydraulic_diameter_m": 1.0,
                "laminar_flow_coefficient": 0.0,
                "turbulent_flow_coefficient": 0.0,
                "transition_reynolds_number": 30.0,
            },
        },
        "species": {
            "co2": {
                "molecular_weight_g_mol": 44.0095,
                "conversion": "ppmv-to-mass-fraction-mw-ratio",
            }
        },
        "project_controls": {
            "mode": "steady",
            "start": "00:00:00",
            "stop": "01:00:00",
            "time_step_s": 60
        },
        "path_records": {
            "path:W1": {"prj_flags":0,"filter_number":0,"wind_profile_number":0,"ahs_number":0,"schedule_number":0,"level_number":1,"x_m":0.0,"y_m":1.8,"relative_height_m":0.9,"element_multiplier":1.0,"constant_wind_pressure_pa":0.0,"wind_speed_modifier":1.0},
            "path:W2": {"prj_flags":0,"filter_number":0,"wind_profile_number":0,"ahs_number":0,"schedule_number":0,"level_number":1,"x_m":5.0,"y_m":1.7,"relative_height_m":0.9,"element_multiplier":1.0,"constant_wind_pressure_pa":0.0,"wind_speed_modifier":1.0},
            "path:W3": {"prj_flags":0,"filter_number":0,"wind_profile_number":0,"ahs_number":0,"schedule_number":0,"level_number":1,"x_m":3.8,"y_m":5.0,"relative_height_m":0.9,"element_multiplier":1.0,"constant_wind_pressure_pa":0.0,"wind_speed_modifier":1.0},
            "path:D1": {"prj_flags":0,"filter_number":0,"wind_profile_number":0,"ahs_number":0,"schedule_number":0,"level_number":1,"x_m":5.0,"y_m":2.8,"relative_height_m":0.0,"element_multiplier":1.0,"constant_wind_pressure_pa":0.0,"wind_speed_modifier":1.0},
            "path:D2": {"prj_flags":0,"filter_number":0,"wind_profile_number":0,"ahs_number":0,"schedule_number":0,"level_number":1,"x_m":2.5,"y_m":5.0,"relative_height_m":0.0,"element_multiplier":1.0,"constant_wind_pressure_pa":0.0,"wind_speed_modifier":1.0}
        },
        "levels": {
            "1": {
                "name": "Ground",
                "reference_height_m": 0.0,
            }
        },
    }


class ContamPrjProfileTests(unittest.TestCase):
    def test_profile_fills_zone_section_14_fields(self):
        bound = bind_prj_serialization_profile(forced_manifest(), profile())
        living = next(z for z in bound["zones"] if z["key"] == "zone:living")
        self.assertEqual(living["level_number"], 1)
        self.assertEqual(living["initial_temperature_k"], 298.15)
        self.assertEqual(living["initial_pressure_pa"], 0.0)

    def test_profile_fills_airflow_section_10_storage_fields(self):
        bound = bind_prj_serialization_profile(forced_manifest(), profile())
        w1 = next(
            x for x in bound["airflow_elements"]
            if x["layout_opening_id"] == "W1"
        )
        self.assertEqual(w1["hydraulic_diameter_m"], 1.0)
        self.assertEqual(w1["transition_reynolds_number"], 30.0)
        self.assertEqual(w1["laminar_flow_coefficient"], 0.0)

    def test_co2_ppmv_conversion_matches_existing_mass_ratio_convention(self):
        fraction = ppmv_to_mass_fraction(1000.0, 44.0095)
        self.assertAlmostEqual(
            fraction * (28.96546 / 44.0095) * 1_000_000.0,
            1000.0,
            places=8,
        )

    def test_profile_fills_species_and_initial_mass_fractions(self):
        bound = bind_prj_serialization_profile(forced_manifest(), profile())
        co2 = bound["contaminants"][0]
        self.assertEqual(co2["molecular_weight_g_mol"], 44.0095)
        self.assertEqual(
            co2["mass_fraction_conversion"],
            "ppmv-to-mass-fraction-mw-ratio",
        )
        self.assertGreater(
            co2["initial_zone_mass_fraction"]["zone:living"],
            0.0,
        )
        self.assertEqual(bound["species_definitions"][0]["key"], "co2")

    def test_profile_fills_path_and_project_control_fields(self):
        bound = bind_prj_serialization_profile(forced_manifest(), profile())
        w1 = next(x for x in bound["flow_paths"] if x["key"] == "path:W1")
        self.assertEqual(w1["x_m"], 0.0)
        self.assertEqual(w1["relative_height_m"], 0.9)
        self.assertEqual(bound["project_controls"]["time_step_s"], 60)

    def test_unknown_zone_override_fails_closed(self):
        p = profile()
        p["zone_overrides"] = {"zone:garage": {"relative_height_m": 1.0}}
        with self.assertRaisesRegex(ValueError, "unknown zones"):
            bind_prj_serialization_profile(forced_manifest(), p)

    def test_production_gate_rejects_unvalidated_profile(self):
        with self.assertRaisesRegex(ValueError, "engineering-validated"):
            bind_prj_serialization_profile(
                forced_manifest(),
                profile(),
                require_engineering_validated=True,
            )


if __name__ == "__main__":
    unittest.main()
