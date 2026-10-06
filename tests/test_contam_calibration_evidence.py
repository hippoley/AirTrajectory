import unittest

from airtrajectory.contam_calibration_evidence import issue_evidence_receipt


class ContamCalibrationEvidenceTests(unittest.TestCase):
    def common(self, evidence_type, data):
        return {
            "schema_version": "0.1",
            "evidence_id": "e-1",
            "evidence_type": evidence_type,
            "topology_id": "demo.fixed-three-room.v1",
            "captured_at": "2026-10-06T12:30:00+08:00",
            "method": "field-measurement",
            "source": {"kind": "instrument", "id": "tool-1"},
            "data": data,
        }

    def test_geometry_receipt_is_hashed_and_summarized(self):
        receipt = issue_evidence_receipt(
            self.common(
                "metric_geometry_measurement",
                {
                    "walls": {
                        "living-west": {
                            "length_m": 5.0,
                            "azimuth_deg": 270.0,
                        }
                    },
                    "openings": {
                        "W1": {
                            "width_m": 1.0,
                            "height_m": 2.0,
                            "sill_height_m": 0.9,
                        }
                    },
                },
            )
        )
        self.assertEqual(receipt["summary"]["wall_count"], 1)
        self.assertEqual(receipt["summary"]["opening_count"], 1)
        self.assertEqual(len(receipt["receipt_sha256"]), 64)
        self.assertTrue(receipt["captured_at"].endswith("Z"))
        self.assertIsNone(receipt["approval"])

    def test_airflow_receipt_requires_real_fit_shape(self):
        receipt = issue_evidence_receipt(
            self.common(
                "airflow_calibration",
                {
                    "opening_fits": {
                        "W1": {
                            "closed_leakage_multiplier": 0.012,
                            "sample_count": 8,
                            "rmse": 0.004,
                        }
                    }
                },
            )
        )
        self.assertEqual(receipt["summary"]["opening_fit_count"], 1)

    def test_boundary_receipt_validates_weather_and_contaminants(self):
        receipt = issue_evidence_receipt(
            self.common(
                "boundary_measurement",
                {
                    "weather": {
                        "wind_speed_m_s": 1.8,
                        "wind_direction_deg": 190.0,
                        "barometric_pressure_pa": 100800.0,
                    },
                    "contaminants": {"co2_ppm": 428.0},
                },
            )
        )
        self.assertEqual(receipt["summary"]["contaminant_count"], 1)

    def test_explicit_approval_is_normalized_and_hashed(self):
        payload = self.common(
            "boundary_measurement",
            {
                "weather": {
                    "wind_speed_m_s": 1.8,
                    "wind_direction_deg": 190.0,
                    "barometric_pressure_pa": 100800.0,
                },
                "contaminants": {"co2_ppm": 428.0},
            },
        )
        payload["approval"] = {
            "approved": True,
            "approved_by": "Engineer A",
            "approved_role": "HVAC engineer",
            "approved_at": "2026-10-06T14:30:00+08:00",
        }
        receipt = issue_evidence_receipt(payload)
        self.assertTrue(receipt["approval"]["approved"])
        self.assertEqual(receipt["approval"]["approved_by"], "Engineer A")
        self.assertTrue(receipt["approval"]["approved_at"].endswith("Z"))

    def test_incomplete_approval_fails_closed(self):
        payload = self.common(
            "airflow_calibration",
            {
                "opening_fits": {
                    "W1": {
                        "closed_leakage_multiplier": 0.01,
                        "sample_count": 2,
                        "rmse": 0.0,
                    }
                }
            },
        )
        payload["approval"] = {"approved": True}
        with self.assertRaisesRegex(ValueError, "approved_by and approved_role"):
            issue_evidence_receipt(payload)

    def test_naive_self_assertion_without_source_fails(self):
        payload = self.common(
            "airflow_calibration",
            {
                "opening_fits": {
                    "W1": {
                        "closed_leakage_multiplier": 0.01,
                        "sample_count": 2,
                        "rmse": 0.0,
                    }
                }
            },
        )
        payload["source"] = {}
        with self.assertRaisesRegex(ValueError, "source kind and id"):
            issue_evidence_receipt(payload)


if __name__ == "__main__":
    unittest.main()
