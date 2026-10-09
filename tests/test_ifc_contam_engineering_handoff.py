"""Independent falsification of an IFC engineering handoff."""
import copy
import unittest

from examples.audit_ifc_contam_engineering_handoff import audit_duplex_engineering_inputs


class IFCContamHandoffTests(unittest.TestCase):
    def setUp(self):
        self.readiness = {
            "source": {"sha256": "a"*64},
            "control_scope": {"mode": "ALL_OPENINGS"},
            "semantics": {"spaces": [
                {"id": "S1", "volume_m3": 37.5, "volume_source": "IfcQuantityVolume"},
                {"id": "S2", "volume_m3": 21.0, "volume_source": "IfcQuantityVolume"},
            ]},
        }
        self.scope = {
            "source_ifc_sha256": "a"*64,
            "candidate_count": 1, "excluded_count": 1,
            "prj_compilation_authorized": False,
            "candidate_openings": [{
                "opening_id": "W1", "kind": "window",
                "adjacent_spaces": ["S1"], "width_m": 1.0, "height_m": 1.0,
            }],
            "excluded_openings": [{"opening_id": "W2"}],
        }

    def test_missing_calibration_and_excluded_openings_are_explicit_blockers(self):
        r = audit_duplex_engineering_inputs(self.readiness, self.scope)
        self.assertEqual(r["verified_source_volumes"]["S1"]["volume_m3"], 37.5)
        self.assertFalse(r["prj_compilation_authorized"])
        reasons = {x["reason"] for x in r["issues"]}
        self.assertIn("EXCLUDED_OPENING_REQUIRES_AIRFLOW_TREATMENT", reasons)
        self.assertIn("MISSING_APPROVED_CLOSED_LEAKAGE_CALIBRATION", reasons)
        self.assertIn("EXTERIOR_BOUNDARY_NOT_ENGINEERING_REVIEWED", reasons)

    def test_wrong_source_and_fake_prior_approval_fail_closed(self):
        bad = copy.deepcopy(self.scope)
        bad["source_ifc_sha256"] = "b"*64
        with self.assertRaisesRegex(ValueError, "identical upstream"):
            audit_duplex_engineering_inputs(self.readiness, bad)
        bad = copy.deepcopy(self.scope)
        bad["prj_compilation_authorized"] = True
        with self.assertRaisesRegex(ValueError, "pre-authorized"):
            audit_duplex_engineering_inputs(self.readiness, bad)

    def test_invalid_volume_cannot_be_promoted_by_fake_other_evidence(self):
        bad = copy.deepcopy(self.readiness)
        bad["semantics"]["spaces"][0]["volume_m3"] = float("nan")
        r = audit_duplex_engineering_inputs(bad, self.scope)
        self.assertIn("MISSING_MEASURED_SPACE_VOLUME", {x["reason"] for x in r["issues"]})


if __name__ == "__main__":
    unittest.main()
