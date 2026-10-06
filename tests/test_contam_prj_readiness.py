import json
from pathlib import Path
import unittest

from airtrajectory.contam_allocator import allocate_contam_ids
from airtrajectory.contam_boundary import bind_boundary_profile
from airtrajectory.contam_ir import compile_contam_ir
from airtrajectory.contam_prj_readiness import audit_prj_readiness
from airtrajectory.contam_profile import (
    bind_airflow_elements,
    illustrative_opening_profile,
)
from airtrajectory.contam_prj_profile import bind_prj_serialization_profile
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
    manifest = bind_airflow_elements(
        manifest,
        illustrative_opening_profile(),
    )
    boundary = {
        "schema_version": "0.1",
        "profile_id": "test-boundary",
        "evidence_level": "illustrative",
        "engineering_validated": False,
        "weather": {
            "wind_speed_m_s": 1.5,
            "wind_direction_deg": 180.0,
            "outdoor_temperature_c": 25.0,
            "barometric_pressure_pa": 101325.0,
        },
        "contaminants": [
            {
                "key": "co2",
                "name": "CO2",
                "unit": "ppm",
                "outdoor_concentration": 430.0,
                "initial_zone_concentration": {
                    "zone:living": 1400.0,
                    "zone:bedroom": 900.0,
                    "zone:study": 800.0,
                },
            }
        ],
    }
    return bind_boundary_profile(manifest, boundary)


class ContamPrjReadinessTests(unittest.TestCase):
    def test_current_forced_manifest_is_blocked_with_exact_sections(self):
        result = audit_prj_readiness(forced_manifest())

        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["prj_serialization_ready"])
        self.assertIn("section_10_airflow_elements", result["missing"])
        self.assertIn("section_14_zones", result["missing"])
        self.assertIn("section_15_initial_concentrations", result["missing"])
        self.assertIn("section_16_airflow_paths", result["missing"])
        self.assertIn("global", result["missing"])

    def test_airflow_blockers_are_entity_specific(self):
        result = audit_prj_readiness(forced_manifest())
        w1 = result["missing"]["section_10_airflow_elements"]["element:W1"]
        self.assertIn("lam", w1)
        self.assertIn("turb", w1)
        self.assertIn("Re", w1)

    def test_zone_blockers_name_prj_fields(self):
        result = audit_prj_readiness(forced_manifest())
        living = result["missing"]["section_14_zones"]["zone:living"]
        self.assertEqual(set(living), {"pl", "relHt", "T0", "P0"})

    def test_ppm_is_not_silently_written_as_mass_fraction(self):
        result = audit_prj_readiness(forced_manifest())
        co2 = result["missing"]["section_15_initial_concentrations"]["co2"]
        self.assertIn("molecular_weight_g_mol", co2)
        self.assertIn("mass_fraction_conversion", co2)

    def test_readiness_hash_is_deterministic(self):
        a = audit_prj_readiness(forced_manifest())
        b = audit_prj_readiness(forced_manifest())
        self.assertEqual(a["readiness_sha256"], b["readiness_sha256"])


    def test_profile_binding_clears_sections_10_14_15_and_global_species_levels(self):
        manifest = forced_manifest()
        prj_profile = {
            "schema_version": "0.1",
            "profile_id": "readiness-test",
            "engineering_validated": False,
            "zone_defaults": {
                "level_number": 1,
                "relative_height_m": 0.0,
                "initial_temperature_k": 298.15,
                "initial_pressure_pa": 101325.0,
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
            "levels": {
                "1": {
                    "name": "Ground",
                    "reference_height_m": 0.0,
                }
            },
        }
        profiled = bind_prj_serialization_profile(manifest, prj_profile)
        result = audit_prj_readiness(profiled)

        self.assertEqual(result["status"], "BLOCKED")
        self.assertNotIn("section_10_airflow_elements", result["missing"])
        self.assertNotIn("section_14_zones", result["missing"])
        self.assertNotIn("section_15_initial_concentrations", result["missing"])
        self.assertIn("section_16_airflow_paths", result["missing"])
        self.assertEqual(
            result["missing"]["global"]["manifest"],
            ["section_1_project_weather_simulation_controls"],
        )


if __name__ == "__main__":
    unittest.main()
