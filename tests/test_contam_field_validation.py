import copy
import hashlib
import json
from pathlib import Path
import unittest

from airtrajectory.contam_field_validation import (
    validate_contam_against_field,
    validate_field_validation_protocol,
)
from airtrajectory.layout import LayoutContract


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"


def sha(payload):
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def protocol():
    return {
        "schema_version": "0.1",
        "protocol_id": "field-validation-v1",
        "topology_id": "demo.fixed-three-room.v1",
        "min_samples": 2,
        "co2": {
            "zones": ["living", "bedroom", "study"],
            "rmse_ppm_max": 50.0,
            "mae_ppm_max": 40.0,
        },
        "opening_position": {
            "openings": ["W1", "W2", "W3", "D1", "D2"],
            "mae_pct_max": 2.0,
        },
        "alignment": {
            "sampling_interval_s": 60.0,
            "max_skew_s": 10.0,
            "aggregation": "nearest",
            "accepted_qualities": ["measured"],
        },
        "approval": {
            "approved": True,
            "approved_by": "Engineer A",
            "approved_role": "HVAC validation lead",
            "approved_at": "2026-10-06T15:00:00+08:00",
        },
    }


def runtime_receipt(layout):
    series = [
        {
            "step": 0,
            "co2_ppm": {
                "living": 1300.0,
                "bedroom": 900.0,
                "study": 800.0,
            },
            "opening_pct": {
                "W1": 75.0,
                "W2": 35.0,
                "W3": 0.0,
                "D1": 100.0,
                "D2": 100.0,
            },
            "path_flow_kg_s": {
                "W1": 0.2,
                "W2": 0.1,
                "W3": 0.01,
                "D1": 0.05,
                "D2": 0.04,
            },
        },
        {
            "step": 1,
            "co2_ppm": {
                "living": 1100.0,
                "bedroom": 850.0,
                "study": 790.0,
            },
            "opening_pct": {
                "W1": 75.0,
                "W2": 35.0,
                "W3": 0.0,
                "D1": 100.0,
                "D2": 100.0,
            },
            "path_flow_kg_s": {
                "W1": 0.18,
                "W2": 0.09,
                "W3": 0.01,
                "D1": 0.04,
                "D2": 0.03,
            },
        },
    ]
    payload = {
        "schema_version": "0.1",
        "verifier": "contam-engineering-runtime-verifier",
        "status": "ENGINEERING_RUNTIME_VERIFIED",
        "topology_id": layout.topology_id,
        "layout_contract_sha256": layout.sha256(),
        "runtime_verified": True,
        "engineering_model_verified": True,
        "field_validation_verified": False,
        "engineering_truth": False,
        "steps": 2,
        "prediction_series": series,
        "prediction_series_sha256": sha(series),
    }
    return {
        **payload,
        "runtime_receipt_sha256": sha(payload),
    }


def field_bundle(*, protocol_sha, runtime_sha, offset=0.0):
    return {
        "schema_version": "0.1",
        "validation_id": "field-run-001",
        "protocol_id": "field-validation-v1",
        "protocol_sha256": protocol_sha,
        "topology_id": "demo.fixed-three-room.v1",
        "runtime_receipt_sha256": runtime_sha,
        "captured_at": "2026-10-06T15:30:00+08:00",
        "source": {
            "kind": "site-sensor-system",
            "id": "site-sensors-001",
            "model": "field-rig",
            "serial": "field-001",
            "calibration_ref": "cal-001",
        },
        "samples": [
            {
                "step": 0,
                "co2_ppm": {
                    "living": 1290.0 + offset,
                    "bedroom": 905.0 + offset,
                    "study": 805.0 + offset,
                },
                "opening_pct": {
                    "W1": 75.5,
                    "W2": 34.5,
                    "W3": 0.5,
                    "D1": 100.0,
                    "D2": 100.0,
                },
            },
            {
                "step": 1,
                "co2_ppm": {
                    "living": 1095.0 + offset,
                    "bedroom": 855.0 + offset,
                    "study": 795.0 + offset,
                },
                "opening_pct": {
                    "W1": 74.5,
                    "W2": 35.5,
                    "W3": 0.5,
                    "D1": 100.0,
                    "D2": 100.0,
                },
            },
        ],
    }


class FieldFiniteAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.layout = LayoutContract.from_file(LAYOUT)

    def test_reject_duplicate_runtime_prediction_steps(self):
        layout = self.layout
        runtime = runtime_receipt(layout)
        runtime["prediction_series"][1]["step"] = 0
        spec = validate_field_validation_protocol(layout, protocol())
        bundle = field_bundle(
            protocol_sha=spec["protocol_sha256"],
            runtime_sha=runtime["runtime_receipt_sha256"],
        )
        with self.assertRaisesRegex(ValueError, "duplicate prediction steps"):
            validate_contam_against_field(
                layout=layout, runtime_receipt=runtime,
                protocol=protocol(), field_bundle=bundle,
            )

    def test_reject_nonfinite_protocol_limits(self):
        for section, key in (
            ("co2", "rmse_ppm_max"),
            ("co2", "mae_ppm_max"),
            ("opening_position", "mae_pct_max"),
            ("alignment", "sampling_interval_s"),
            ("alignment", "max_skew_s"),
        ):
            for bad in (float("nan"), float("inf")):
                with self.subTest(section=section, key=key, bad=bad):
                    spec = protocol()
                    spec[section][key] = bad
                    with self.assertRaises(ValueError):
                        validate_field_validation_protocol(self.layout, spec)

    def test_reject_nonfinite_fixed_opening(self):
        spec = protocol()
        spec["opening_position"]["openings"] = ["W1", "W2", "W3"]
        spec["opening_position"]["fixed_openings"] = {"D1": float("nan"), "D2": 100.0}
        with self.assertRaises(ValueError):
            validate_field_validation_protocol(self.layout, spec)

    def test_reject_nonfinite_measured_co2_and_position(self):
        runtime = runtime_receipt(self.layout)
        normalized = validate_field_validation_protocol(self.layout, protocol())
        for category, ident in (("co2_ppm", "living"), ("opening_pct", "W1")):
            for bad in (float("nan"), float("inf")):
                with self.subTest(category=category, bad=bad):
                    bundle = field_bundle(
                        protocol_sha=normalized["protocol_sha256"],
                        runtime_sha=runtime["runtime_receipt_sha256"],
                    )
                    bundle["samples"][0][category][ident] = bad
                    with self.assertRaises(ValueError):
                        validate_contam_against_field(
                            layout=self.layout, runtime_receipt=runtime,
                            protocol=protocol(), field_bundle=bundle,
                        )


class ContamFieldValidationTests(unittest.TestCase):
    def setUp(self):
        self.layout = LayoutContract.from_file(LAYOUT)

    def bundle(self, *, offset=0.0):
        runtime = runtime_receipt(self.layout)
        normalized = validate_field_validation_protocol(
            self.layout,
            protocol(),
        )
        return runtime, field_bundle(
            protocol_sha=normalized["protocol_sha256"],
            runtime_sha=runtime["runtime_receipt_sha256"],
            offset=offset,
        )

    def test_protocol_can_separate_measured_windows_from_fixed_doors(self):
        spec = protocol()
        spec["opening_position"]["openings"] = ["W1", "W2", "W3"]
        spec["opening_position"]["fixed_openings"] = {
            "D1": 100.0,
            "D2": 100.0,
        }
        normalized = validate_field_validation_protocol(self.layout, spec)
        self.assertEqual(
            normalized["opening_position"]["openings"],
            ["W1", "W2", "W3"],
        )
        self.assertEqual(
            normalized["opening_position"]["fixed_openings"],
            {"D1": 100.0, "D2": 100.0},
        )

    def test_measured_and_fixed_openings_cannot_overlap(self):
        spec = protocol()
        spec["opening_position"]["fixed_openings"] = {"W1": 100.0}
        with self.assertRaisesRegex(ValueError, "must be disjoint"):
            validate_field_validation_protocol(self.layout, spec)

    def test_approved_protocol_and_matching_field_data_can_pass(self):
        runtime, bundle = self.bundle()
        result = validate_contam_against_field(
            layout=self.layout,
            runtime_receipt=runtime,
            protocol=protocol(),
            field_bundle=bundle,
        )
        self.assertEqual(result["status"], "FIELD_VALIDATION_PASSED")
        self.assertTrue(result["field_validation_verified"])
        self.assertTrue(result["engineering_truth"])
        self.assertIn("approved protocol", result["engineering_truth_scope"])
        self.assertEqual(result["sample_count"], 2)
        self.assertEqual(len(result["field_validation_receipt_sha256"]), 64)

    def test_alignment_provenance_is_bound_into_final_receipt(self):
        runtime, bundle = self.bundle()
        alignment_payload = {
            "aggregation": "nearest",
            "max_skew_s": 10.0,
            "accepted_qualities": ["measured"],
            "selected_record_count": 16,
            "input_record_count": 16,
            "alignments": [],
        }
        bundle["raw_capture_sha256"] = "c" * 64
        bundle["alignment_receipt"] = {
            **alignment_payload,
            "alignment_sha256": sha(alignment_payload),
        }
        import_payload = {
            "adapter": "field-capture-importer-v1",
            "records_format": "csv",
            "manifest_filename": "capture.manifest.json",
            "manifest_sha256": "d" * 64,
            "records_filename": "gateway.csv",
            "records_sha256": "e" * 64,
            "record_count": 16,
        }
        bundle["import_provenance"] = {
            **import_payload,
            "import_receipt_sha256": sha(import_payload),
        }
        result = validate_contam_against_field(
            layout=self.layout,
            runtime_receipt=runtime,
            protocol=protocol(),
            field_bundle=bundle,
        )
        self.assertEqual(result["raw_capture_sha256"], "c" * 64)
        self.assertEqual(
            result["alignment_sha256"],
            sha(alignment_payload),
        )
        self.assertEqual(
            result["import_receipt_sha256"],
            sha(import_payload),
        )
        self.assertEqual(result["source_records_sha256"], "e" * 64)

    def test_fixed_opening_assumptions_are_enforced_against_runtime(self):
        runtime, bundle = self.bundle()
        spec = protocol()
        spec["opening_position"]["openings"] = ["W1", "W2", "W3"]
        spec["opening_position"]["fixed_openings"] = {
            "D1": 100.0,
            "D2": 100.0,
        }
        normalized = validate_field_validation_protocol(self.layout, spec)
        bundle["protocol_sha256"] = normalized["protocol_sha256"]
        for sample in bundle["samples"]:
            sample["opening_pct"] = {
                key: value
                for key, value in sample["opening_pct"].items()
                if key in {"W1", "W2", "W3"}
            }
        runtime["prediction_series"][0]["opening_pct"]["D1"] = 0.0
        runtime["prediction_series_sha256"] = sha(
            runtime["prediction_series"]
        )
        payload = dict(runtime)
        payload.pop("runtime_receipt_sha256")
        runtime["runtime_receipt_sha256"] = sha(payload)
        bundle["runtime_receipt_sha256"] = runtime[
            "runtime_receipt_sha256"
        ]
        with self.assertRaisesRegex(
            ValueError,
            "violates fixed opening assumption for D1",
        ):
            validate_contam_against_field(
                layout=self.layout,
                runtime_receipt=runtime,
                protocol=spec,
                field_bundle=bundle,
            )

    def test_fixed_openings_do_not_require_fake_measurements(self):
        runtime, bundle = self.bundle()
        spec = protocol()
        spec["opening_position"]["openings"] = ["W1", "W2", "W3"]
        spec["opening_position"]["fixed_openings"] = {
            "D1": 100.0,
            "D2": 100.0,
        }
        normalized = validate_field_validation_protocol(self.layout, spec)
        bundle["protocol_sha256"] = normalized["protocol_sha256"]
        for sample in bundle["samples"]:
            sample["opening_pct"] = {
                key: value
                for key, value in sample["opening_pct"].items()
                if key in {"W1", "W2", "W3"}
            }
        result = validate_contam_against_field(
            layout=self.layout,
            runtime_receipt=runtime,
            protocol=spec,
            field_bundle=bundle,
        )
        self.assertEqual(
            set(result["opening_position_metrics"]),
            {"W1", "W2", "W3"},
        )
        self.assertEqual(
            result["fixed_opening_assumptions"],
            {"D1": 100.0, "D2": 100.0},
        )

    def test_threshold_failure_returns_failed_receipt_not_fake_pass(self):
        runtime, bundle = self.bundle(offset=200.0)
        result = validate_contam_against_field(
            layout=self.layout,
            runtime_receipt=runtime,
            protocol=protocol(),
            field_bundle=bundle,
        )
        self.assertEqual(result["status"], "FIELD_VALIDATION_FAILED")
        self.assertFalse(result["field_validation_verified"])
        self.assertFalse(result["engineering_truth"])
        self.assertFalse(result["co2_metrics"]["living"]["rmse_pass"])

    def test_missing_runtime_step_is_rejected(self):
        runtime, bundle = self.bundle()
        bundle["samples"].pop()
        with self.assertRaisesRegex(ValueError, "every runtime prediction step"):
            validate_contam_against_field(
                layout=self.layout,
                runtime_receipt=runtime,
                protocol=protocol(),
                field_bundle=bundle,
            )

    def test_measurement_bundle_cannot_supply_post_hoc_thresholds(self):
        runtime, bundle = self.bundle()
        bundle["thresholds"] = {"co2_rmse_ppm_max": 9999}
        with self.assertRaisesRegex(ValueError, "must not carry thresholds"):
            validate_contam_against_field(
                layout=self.layout,
                runtime_receipt=runtime,
                protocol=protocol(),
                field_bundle=bundle,
            )

    def test_stale_protocol_hash_is_rejected(self):
        runtime, bundle = self.bundle()
        bundle["protocol_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "protocol_sha256 mismatch"):
            validate_contam_against_field(
                layout=self.layout,
                runtime_receipt=runtime,
                protocol=protocol(),
                field_bundle=bundle,
            )

    def test_tampered_runtime_prediction_series_is_rejected(self):
        runtime, bundle = self.bundle()
        runtime["prediction_series"][0]["co2_ppm"]["living"] += 500.0
        payload = dict(runtime)
        payload.pop("runtime_receipt_sha256")
        runtime["runtime_receipt_sha256"] = sha(payload)
        with self.assertRaisesRegex(
            ValueError,
            "prediction_series SHA-256 integrity",
        ):
            validate_contam_against_field(
                layout=self.layout,
                runtime_receipt=runtime,
                protocol=protocol(),
                field_bundle=bundle,
            )

    def test_measurements_before_protocol_approval_are_rejected(self):
        runtime, bundle = self.bundle()
        bundle["captured_at"] = "2026-10-06T14:00:00+08:00"
        with self.assertRaisesRegex(
            ValueError,
            "captured before protocol approval",
        ):
            validate_contam_against_field(
                layout=self.layout,
                runtime_receipt=runtime,
                protocol=protocol(),
                field_bundle=bundle,
            )

    def test_uncalibrated_field_source_is_rejected(self):
        runtime, bundle = self.bundle()
        bundle["source"]["calibration_ref"] = ""
        with self.assertRaisesRegex(
            ValueError,
            "requires model, serial, and calibration_ref",
        ):
            validate_contam_against_field(
                layout=self.layout,
                runtime_receipt=runtime,
                protocol=protocol(),
                field_bundle=bundle,
            )

    def test_unapproved_protocol_is_rejected(self):
        runtime, bundle = self.bundle()
        spec = protocol()
        spec["approval"]["approved"] = False
        with self.assertRaisesRegex(ValueError, "approved=true"):
            validate_contam_against_field(
                layout=self.layout,
                runtime_receipt=runtime,
                protocol=spec,
                field_bundle=bundle,
            )


if __name__ == "__main__":
    unittest.main()
