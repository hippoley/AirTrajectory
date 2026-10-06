import copy
from pathlib import Path
import unittest

from airtrajectory.contam_profile_compiler import (
    attach_prj_review_evidence,
    compile_airflow_profile_from_evidence,
    compile_boundary_profile_from_evidence,
    compile_metric_overlay_from_evidence,
)
from airtrajectory.layout import LayoutContract


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"


def common(evidence_type, evidence_id, data, *, approved=False):
    payload = {
        "schema_version": "0.1",
        "evidence_id": evidence_id,
        "evidence_type": evidence_type,
        "topology_id": "demo.fixed-three-room.v1",
        "captured_at": "2026-10-06T12:30:00+08:00",
        "method": "field-method",
        "source": {"kind": "instrument", "id": evidence_id},
        "data": data,
    }
    if approved:
        payload["approval"] = {
            "approved": True,
            "approved_by": "Engineer A",
            "approved_role": "HVAC engineer",
            "approved_at": "2026-10-06T14:30:00+08:00",
        }
    return payload


class ContamProfileCompilerTests(unittest.TestCase):
    def setUp(self):
        self.layout = LayoutContract.from_file(LAYOUT)

    def geometry_bundle(self):
        return common(
            "metric_geometry_measurement",
            "geometry-1",
            {
                "rooms": {
                    r.id: {"volume_m3": r.volume_m3}
                    for r in self.layout.rooms
                },
                "walls": {
                    w.id: {
                        "length_m": 5.0 if w.id != "study-south" else 8.0,
                        "azimuth_deg": {
                            "living-west": 270.0,
                            "bedroom-east": 90.0,
                            "study-south": 180.0,
                            "living-bedroom": 90.0,
                            "living-study": 180.0,
                        }[w.id],
                    }
                    for w in self.layout.walls
                },
                "openings": {
                    o.id: {
                        "width_m": 1.0,
                        "height_m": 2.2 if o.kind == "door" else 2.0,
                        "sill_height_m": 0.0 if o.kind == "door" else 0.9,
                        "max_area_m2": o.max_area_m2,
                    }
                    for o in self.layout.openings
                },
            },
        )

    def airflow_bundle(self):
        return common(
            "airflow_calibration",
            "airflow-1",
            {
                "opening_fits": {
                    o.id: {
                        "flow_exponent": 0.5,
                        "discharge_coefficient": 0.61,
                        "closed_leakage_multiplier": (
                            0.012 if o.kind == "window" else 0.02
                        ),
                        "sample_count": 8,
                        "rmse": 0.004,
                    }
                    for o in self.layout.openings
                }
            },
        )

    def boundary_bundle(self):
        return common(
            "boundary_measurement",
            "boundary-1",
            {
                "weather": {
                    "wind_speed_m_s": 1.8,
                    "wind_direction_deg": 190.0,
                    "outdoor_temperature_c": 25.2,
                    "barometric_pressure_pa": 100800.0,
                    "wind_pressure_model": "site-measured-facade-v1",
                },
                "contaminants": {
                    "co2": {
                        "name": "CO2",
                        "unit": "ppm",
                        "outdoor_concentration": 428.0,
                        "initial_zone_concentration": {
                            "zone:living": 1370.0,
                            "zone:bedroom": 910.0,
                            "zone:study": 805.0,
                        },
                    }
                },
            },
        )

    def test_metric_profile_is_compiled_from_full_measurement_bundle(self):
        profile = compile_metric_overlay_from_evidence(
            self.layout,
            self.geometry_bundle(),
        )
        self.assertFalse(profile["engineering_validated"])
        self.assertEqual(profile["evidence_level"], "measured")
        self.assertEqual(profile["rooms"]["living"]["volume_m3"], 75.0)
        self.assertEqual(
            profile["evidence_receipts"][0]["evidence_type"],
            "metric_geometry_measurement",
        )

    def test_metric_profile_becomes_engineering_validated_only_with_approval(self):
        bundle = self.geometry_bundle()
        bundle["approval"] = {
            "approved": True,
            "approved_by": "Engineer A",
            "approved_role": "HVAC engineer",
            "approved_at": "2026-10-06T14:30:00+08:00",
        }
        profile = compile_metric_overlay_from_evidence(self.layout, bundle)
        self.assertTrue(profile["engineering_validated"])
        self.assertTrue(profile["evidence_receipts"][0]["approval"]["approved"])

    def test_metric_profile_rejects_partial_geometry(self):
        bundle = self.geometry_bundle()
        del bundle["data"]["walls"]["living-west"]
        with self.assertRaisesRegex(ValueError, "exactly cover layout walls"):
            compile_metric_overlay_from_evidence(self.layout, bundle)

    def test_airflow_profile_compiles_kind_rules_without_averaging(self):
        profile = compile_airflow_profile_from_evidence(
            self.layout,
            self.airflow_bundle(),
        )
        self.assertEqual(
            profile["rules"]["window"]["closed_leakage_multiplier"],
            0.012,
        )
        self.assertEqual(
            profile["rules"]["door"]["closed_leakage_multiplier"],
            0.02,
        )

    def test_airflow_profile_rejects_disagreement_within_kind(self):
        bundle = self.airflow_bundle()
        bundle["data"]["opening_fits"]["W2"][
            "closed_leakage_multiplier"
        ] = 0.02
        with self.assertRaisesRegex(ValueError, "disagree"):
            compile_airflow_profile_from_evidence(self.layout, bundle)

    def test_boundary_profile_compiles_site_observation(self):
        profile = compile_boundary_profile_from_evidence(
            self.layout,
            self.boundary_bundle(),
        )
        self.assertEqual(profile["weather"]["wind_speed_m_s"], 1.8)
        self.assertEqual(
            profile["contaminants"][0]["initial_zone_concentration"][
                "zone:living"
            ],
            1370.0,
        )

    def test_prj_review_is_bound_to_exact_profile_sha(self):
        prj = {
            "schema_version": "0.1",
            "profile_id": "prj-1",
            "project_controls": {"mode": "steady"},
        }
        import hashlib, json
        approved = hashlib.sha256(
            json.dumps(
                prj,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        review = common(
            "prj_engineering_review",
            "review-1",
            {
                "reviewer": "Engineer A",
                "reviewer_role": "HVAC engineer",
                "approved_profile_sha256": approved,
            },
        )
        reviewed = attach_prj_review_evidence(
            topology_id=self.layout.topology_id,
            prj_profile=prj,
            review_bundle=review,
        )
        self.assertTrue(reviewed["engineering_validated"])
        self.assertEqual(reviewed["evidence_level"], "engineering-reviewed")

        changed = {**prj, "project_controls": {"mode": "transient"}}
        with self.assertRaisesRegex(ValueError, "does not match"):
            attach_prj_review_evidence(
                topology_id=self.layout.topology_id,
                prj_profile=changed,
                review_bundle=review,
            )


if __name__ == "__main__":
    unittest.main()
