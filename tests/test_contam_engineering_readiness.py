import unittest

from airtrajectory.contam_engineering_readiness import (
    audit_engineering_readiness,
)


TOPOLOGY = "demo.fixed-three-room.v1"


def receipt(evidence_type, marker, *, approved=False):
    payload = {
        "schema_version": "0.1",
        "evidence_id": marker,
        "evidence_type": evidence_type,
        "topology_id": TOPOLOGY,
        "captured_at": "2026-10-06T04:30:00Z",
        "method": "field-measurement",
        "source": {"kind": "instrument", "id": marker},
        "summary": {"data_sha256": marker[0] * 64},
        "receipt_sha256": marker[-1] * 64,
    }
    if approved:
        payload["approval"] = {
            "approved": True,
            "approved_by": "Engineer A",
            "approved_role": "HVAC engineer",
            "approved_at": "2026-10-06T06:30:00Z",
        }
    else:
        payload["approval"] = None
    return payload


def provenance():
    return {
        "topology_id": TOPOLOGY,
        "layout_contract_sha256": "a" * 64,
        "demo_runtime_snapshot_sha256": "b" * 64,
        "status": "GENERATED_TOPOLOGY_LOAD_SMOKE",
        "metric_geometry_provenance": {
            "metric_geometry_profile_id": "metric",
            "metric_geometry_profile_sha256": "c" * 64,
            "evidence_level": "illustrative-schema",
            "engineering_validated": False,
            "evidence_receipts": [],
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
            "evidence_receipts": [],
        },
        "boundary_profile": {
            "profile_id": "boundary",
            "profile_sha256": "e" * 64,
            "evidence_level": "illustrative-schema",
            "engineering_validated": False,
            "evidence_receipts": [],
        },
        "prj_serialization_profile": {
            "profile_id": "prj",
            "profile_sha256": "f" * 64,
            "evidence_level": "illustrative-schema",
            "engineering_validated": False,
            "evidence_receipts": [],
        },
    }


def approve_with_receipts(payload):
    mapping = {
        "metric_geometry_provenance": "metric_geometry_measurement",
        "airflow_profile": "airflow_calibration",
        "boundary_profile": "boundary_measurement",
        "prj_serialization_profile": "prj_engineering_review",
    }
    for index, (key, evidence_type) in enumerate(mapping.items(), start=1):
        payload[key]["engineering_validated"] = True
        payload[key]["evidence_level"] = "approved"
        payload[key]["evidence_receipts"] = [
            receipt(
                evidence_type,
                f"e{index}",
                approved=evidence_type != "prj_engineering_review",
            )
        ]
    return payload


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
        self.assertIn(
            "missing_required_evidence_receipt",
            result["blockers"]["metric_geometry"],
        )
        self.assertEqual(len(result["evidence_sha256"]), 64)

    def test_boolean_approval_without_receipts_still_fails(self):
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
        self.assertFalse(result["engineering_ready"])
        self.assertTrue(
            all(
                "missing_required_evidence_receipt" in blockers
                for blockers in result["blockers"].values()
            )
        )

    def test_unapproved_measurement_receipt_still_fails(self):
        payload = approve_with_receipts(provenance())
        payload["airflow_profile"]["evidence_receipts"][0]["approval"] = None
        result = audit_engineering_readiness(payload)
        self.assertFalse(result["engineering_ready"])
        self.assertIn(
            "evidence_receipt_not_approved",
            result["blockers"]["airflow_calibration"],
        )

    def test_all_engineering_validated_profiles_with_typed_receipts_can_pass(self):
        payload = approve_with_receipts(provenance())
        result = audit_engineering_readiness(payload)
        self.assertEqual(result["status"], "ENGINEERING_READY")
        self.assertTrue(result["engineering_ready"])
        self.assertTrue(result["engineering_truth"])
        self.assertEqual(result["blockers"], {})

    def test_missing_leakage_calibration_blocks_airflow_component(self):
        payload = approve_with_receipts(provenance())
        del payload["airflow_profile"]["closed_leakage_multiplier_by_kind"]

        result = audit_engineering_readiness(payload)
        self.assertFalse(result["engineering_ready"])
        self.assertIn(
            "missing_closed_leakage_calibration",
            result["blockers"]["airflow_calibration"],
        )

    def test_wrong_topology_evidence_fails_closed(self):
        payload = approve_with_receipts(provenance())
        payload["boundary_profile"]["evidence_receipts"][0][
            "topology_id"
        ] = "other-topology"

        result = audit_engineering_readiness(payload)
        self.assertFalse(result["engineering_ready"])
        self.assertIn(
            "evidence_topology_mismatch",
            result["blockers"]["boundary_weather_co2"],
        )

    def test_unknown_evidence_level_does_not_pass_even_with_receipts(self):
        payload = approve_with_receipts(provenance())
        for key in (
            "metric_geometry_provenance",
            "airflow_profile",
            "boundary_profile",
            "prj_serialization_profile",
        ):
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
