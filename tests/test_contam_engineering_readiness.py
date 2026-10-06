import copy
import unittest

from airtrajectory.contam_engineering_readiness import (
    audit_engineering_readiness,
)


def provenance():
    return {
        "topology_id": "demo.fixed-three-room.v1",
        "layout_contract_sha256": "a" * 64,
        "demo_runtime_snapshot_sha256": "b" * 64,
        "status": "GENERATED_TOPOLOGY_LOAD_SMOKE",
        "metric_geometry_provenance": {
            "metric_geometry_profile_id": "metric",
            "metric_geometry_profile_sha256": "c" * 64,
            "evidence_level": "illustrative-schema",
            "engineering_validated": False,
        },
        "airflow_profile": {
            "profile_id": "airflow",
            "profile_sha256": "d" * 64,
            "evidence_level": "illustrative",
            "engineering_validated": False,
            "closed_leakage_multiplier_by_kind": {
                "window": 0.01,
                "door": 0.01,
            },
        },
        "boundary_profile": {
            "profile_id": "boundary",
            "profile_sha256": "e" * 64,
            "evidence_level": "illustrative-schema",
            "engineering_validated": False,
        },
        "prj_serialization_profile": {
            "profile_id": "prj",
            "profile_sha256": "f" * 64,
            "evidence_level": "illustrative-schema",
            "engineering_validated": False,
        },
    }


class ContamEngineeringReadinessTests(unittest.TestCase):
    def test_demo_provenance_is_software_only_not_engineering_truth(self):
        result = audit_engineering_readiness(provenance())
        self.assertEqual(result["status"], "SOFTWARE_VERIFIED_ONLY")
        self.assertTrue(result["software_verified"])
        self.assertFalse(result["engineering_ready"])
        self.assertFalse(result["engineering_truth"])
        self.assertEqual(
            result["closed_leakage_multiplier_by_kind"]["window"],
            0.01,
        )
        self.assertIn("metric_geometry", result["blockers"])
        self.assertEqual(len(result["evidence_sha256"]), 64)

    def test_all_engineering_validated_profiles_can_pass(self):
        payload = provenance()
        for key in (
            "metric_geometry_provenance",
            "airflow_profile",
            "boundary_profile",
            "prj_serialization_profile",
        ):
            payload[key]["engineering_validated"] = True
            payload[key]["evidence_level"] = "approved"

        result = audit_engineering_readiness(payload)
        self.assertEqual(result["status"], "ENGINEERING_READY")
        self.assertTrue(result["engineering_ready"])
        self.assertTrue(result["engineering_truth"])
        self.assertEqual(result["blockers"], {})

    def test_missing_leakage_calibration_blocks_airflow_component(self):
        payload = provenance()
        for key in (
            "metric_geometry_provenance",
            "airflow_profile",
            "boundary_profile",
            "prj_serialization_profile",
        ):
            payload[key]["engineering_validated"] = True
            payload[key]["evidence_level"] = "approved"
        del payload["airflow_profile"]["closed_leakage_multiplier_by_kind"]

        result = audit_engineering_readiness(payload)
        self.assertFalse(result["engineering_ready"])
        self.assertIn(
            "missing_closed_leakage_calibration",
            result["blockers"]["airflow_calibration"],
        )

    def test_unknown_evidence_level_does_not_pass_even_with_boolean_true(self):
        payload = provenance()
        for key in (
            "metric_geometry_provenance",
            "airflow_profile",
            "boundary_profile",
            "prj_serialization_profile",
        ):
            payload[key]["engineering_validated"] = True
            payload[key]["evidence_level"] = "self-asserted"

        result = audit_engineering_readiness(payload)
        self.assertFalse(result["engineering_ready"])
        self.assertTrue(
            all(
                "evidence_level_not_engineering" in blockers
                for blockers in result["blockers"].values()
            )
        )


if __name__ == "__main__":
    unittest.main()
