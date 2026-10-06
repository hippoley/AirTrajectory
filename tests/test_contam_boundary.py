import json
from pathlib import Path
import unittest

from airtrajectory.contam_allocator import allocate_contam_ids
from airtrajectory.contam_boundary import bind_boundary_profile
from airtrajectory.contam_ir import compile_contam_ir
from airtrajectory.contam_profile import (
    bind_airflow_elements,
    illustrative_opening_profile,
)
from airtrajectory.layout import LayoutContract


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"


def bound_manifest():
    payload = json.loads(LAYOUT.read_text(encoding="utf-8"))
    for wall in payload["walls"]:
        wall["length_m"] = 5.0
        wall["azimuth_deg"] = 90.0
    for opening in payload["openings"]:
        opening["width_m"] = 1.0
        opening["height_m"] = 2.0
        opening["sill_height_m"] = 0.2 if opening["kind"] == "door" else 0.9
        opening["max_area_m2"] = min(opening["max_area_m2"], 2.0)
    layout = LayoutContract.from_dict(payload)
    manifest = allocate_contam_ids(compile_contam_ir(layout))
    return bind_airflow_elements(
        manifest,
        illustrative_opening_profile(),
    )


def profile():
    return {
        "schema_version": "0.1",
        "profile_id": "demo-boundary-v1",
        "evidence_level": "illustrative",
        "engineering_validated": False,
        "source": {"title": "demo"},
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


class ContamBoundaryTests(unittest.TestCase):
    def test_weather_and_co2_bind_to_manifest(self):
        forced = bind_boundary_profile(bound_manifest(), profile())

        self.assertEqual(forced["compiler"], "contam-forced-manifest")
        self.assertEqual(forced["weather"]["wind_speed_m_s"], 1.5)
        self.assertEqual(forced["contaminant_numbers"]["co2"], 1)
        self.assertEqual(
            forced["writer_contract"]["weather/wind_profile"],
            "implemented",
        )
        self.assertEqual(
            forced["writer_contract"]["contaminant_definition"],
            "implemented",
        )
        self.assertFalse(forced["writer_contract"]["ready"])

    def test_missing_zone_initial_concentration_fails_closed(self):
        p = profile()
        del p["contaminants"][0]["initial_zone_concentration"]["zone:study"]
        with self.assertRaisesRegex(ValueError, "missing zones"):
            bind_boundary_profile(bound_manifest(), p)

    def test_unknown_zone_initial_concentration_fails_closed(self):
        p = profile()
        p["contaminants"][0]["initial_zone_concentration"]["zone:garage"] = 700
        with self.assertRaisesRegex(ValueError, "unknown zones"):
            bind_boundary_profile(bound_manifest(), p)

    def test_invalid_wind_direction_fails_closed(self):
        p = profile()
        p["weather"]["wind_direction_deg"] = 360
        with self.assertRaisesRegex(ValueError, "wind_direction_deg"):
            bind_boundary_profile(bound_manifest(), p)

    def test_production_gate_rejects_illustrative_boundary(self):
        with self.assertRaisesRegex(ValueError, "engineering-validated"):
            bind_boundary_profile(
                bound_manifest(),
                profile(),
                require_engineering_validated=True,
            )


if __name__ == "__main__":
    unittest.main()
