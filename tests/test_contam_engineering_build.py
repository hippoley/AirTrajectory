import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from airtrajectory.contam_engineering_build import (
    build_engineering_contam_project,
)
from airtrajectory.layout import LayoutContract


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"
PRJ_PROFILE = ROOT / "examples" / "contam_prj_profile.example.json"


def approval():
    return {
        "approved": True,
        "approved_by": "Engineer A",
        "approved_role": "HVAC engineer",
        "approved_at": "2026-10-06T14:30:00+08:00",
    }


def common(evidence_type, evidence_id, data, *, approved=True):
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
        payload["approval"] = approval()
    return payload


class ContamEngineeringBuildTests(unittest.TestCase):
    def setUp(self):
        self.layout = LayoutContract.from_file(LAYOUT)

    def metric(self, approved=True):
        return common(
            "metric_geometry_measurement",
            "geometry-1",
            {
                "rooms": {
                    room.id: {"volume_m3": room.volume_m3}
                    for room in self.layout.rooms
                },
                "walls": {
                    wall.id: {
                        "length_m": {
                            "living-west": 5.0,
                            "bedroom-east": 5.0,
                            "study-south": 8.0,
                            "living-bedroom": 5.0,
                            "living-study": 4.0,
                        }[wall.id],
                        "azimuth_deg": {
                            "living-west": 270.0,
                            "bedroom-east": 90.0,
                            "study-south": 180.0,
                            "living-bedroom": 90.0,
                            "living-study": 180.0,
                        }[wall.id],
                    }
                    for wall in self.layout.walls
                },
                "openings": {
                    opening.id: {
                        "width_m": 1.0,
                        "height_m": 2.2 if opening.kind == "door" else 2.0,
                        "sill_height_m": 0.0 if opening.kind == "door" else 0.9,
                        "max_area_m2": opening.max_area_m2,
                    }
                    for opening in self.layout.openings
                },
            },
            approved=approved,
        )

    def airflow(self):
        return common(
            "airflow_calibration",
            "airflow-1",
            {
                "opening_fits": {
                    opening.id: {
                        "flow_exponent": 0.5,
                        "discharge_coefficient": 0.61,
                        "closed_leakage_multiplier": (
                            0.012 if opening.kind == "window" else 0.02
                        ),
                        "sample_count": 8,
                        "rmse": 0.004,
                    }
                    for opening in self.layout.openings
                }
            },
        )

    def boundary(self):
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

    def reviewed_prj(self):
        profile = json.loads(PRJ_PROFILE.read_text(encoding="utf-8"))
        base = dict(profile)
        base.pop("engineering_validated", None)
        base.pop("evidence_level", None)
        base.pop("evidence_receipts", None)
        approved_sha = hashlib.sha256(
            json.dumps(
                base,
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
                "approved_profile_sha256": approved_sha,
            },
            approved=False,
        )
        return profile, review

    def test_approved_evidence_builds_engineering_input_ready_project(self):
        profile, review = self.reviewed_prj()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "engineering.prj"
            result = build_engineering_contam_project(
                layout=self.layout,
                metric_evidence=self.metric(),
                airflow_evidence=self.airflow(),
                boundary_evidence=self.boundary(),
                prj_profile=profile,
                prj_review_evidence=review,
                out_path=out,
            )
            self.assertTrue(out.exists())
            self.assertEqual(result["status"], "ENGINEERING_INPUTS_READY")
            self.assertTrue(result["engineering_inputs_ready"])
            self.assertFalse(result["runtime_verified"])
            self.assertFalse(result["engineering_truth"])
            self.assertTrue(
                result["engineering_readiness"]["engineering_ready"]
            )

    def test_unapproved_measurement_fails_before_engineering_build(self):
        profile, review = self.reviewed_prj()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(
                ValueError,
                "metric engineering profile is not explicitly approved",
            ):
                build_engineering_contam_project(
                    layout=self.layout,
                    metric_evidence=self.metric(approved=False),
                    airflow_evidence=self.airflow(),
                    boundary_evidence=self.boundary(),
                    prj_profile=profile,
                    prj_review_evidence=review,
                    out_path=Path(tmp) / "blocked.prj",
                )


if __name__ == "__main__":
    unittest.main()
