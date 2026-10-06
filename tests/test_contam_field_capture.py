from pathlib import Path
import unittest

from airtrajectory.contam_field_capture import compile_field_capture_bundle
from airtrajectory.contam_field_validation import (
    validate_field_validation_protocol,
)
from airtrajectory.layout import LayoutContract


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "web" / "data" / "home_topology.fixed.json"


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
            "approved_at": "2026-10-06T07:00:00Z",
        },
    }


def runtime_receipt(layout):
    return {
        "schema_version": "0.1",
        "status": "ENGINEERING_RUNTIME_VERIFIED",
        "topology_id": layout.topology_id,
        "runtime_receipt_sha256": "r" * 64,
        "steps": 2,
        "prediction_series": [
            {"step": 0, "simulation_time_s": 60.0},
            {"step": 1, "simulation_time_s": 120.0},
        ],
    }


def capture(layout, protocol_sha):
    started = "2026-10-06T07:10:00Z"
    targets = {
        "co2_ppm": [
            ("living", 1290.0, "ppm"),
            ("bedroom", 905.0, "ppm"),
            ("study", 805.0, "ppm"),
        ],
        "opening_pct": [
            ("W1", 75.0, "percent"),
            ("W2", 35.0, "percent"),
            ("W3", 0.0, "percent"),
            ("D1", 100.0, "percent"),
            ("D2", 100.0, "percent"),
        ],
    }
    records = []
    for step, stamp in enumerate(
        ("2026-10-06T07:11:02Z", "2026-10-06T07:11:58Z")
    ):
        for signal_type, rows in targets.items():
            for target_id, value, unit in rows:
                records.append(
                    {
                        "timestamp": stamp,
                        "signal_type": signal_type,
                        "target_id": target_id,
                        "value": (
                            value - step
                            if signal_type == "co2_ppm"
                            else value
                        ),
                        "unit": unit,
                        "quality": "measured",
                    }
                )
    return {
        "schema_version": "0.1",
        "validation_id": "capture-001",
        "protocol_id": "field-validation-v1",
        "protocol_sha256": protocol_sha,
        "topology_id": layout.topology_id,
        "runtime_receipt_sha256": "r" * 64,
        "started_at": started,
        "source": {
            "kind": "site-sensor-system",
            "id": "gateway-001",
            "model": "test-rig",
            "serial": "SN-001",
            "calibration_ref": "CAL-001",
        },
        "records": records,
    }


class ContamFieldCaptureTests(unittest.TestCase):
    def setUp(self):
        self.layout = LayoutContract.from_file(LAYOUT)
        self.normalized = validate_field_validation_protocol(
            self.layout,
            protocol(),
        )

    def test_timestamped_events_compile_to_complete_validation_samples(self):
        raw = capture(
            self.layout,
            self.normalized["protocol_sha256"],
        )
        result = compile_field_capture_bundle(
            layout=self.layout,
            runtime_receipt=runtime_receipt(self.layout),
            protocol=protocol(),
            capture=raw,
        )
        self.assertEqual(len(result["samples"]), 2)
        self.assertEqual(
            set(result["samples"][0]["co2_ppm"]),
            {"living", "bedroom", "study"},
        )
        self.assertEqual(
            set(result["samples"][0]["opening_pct"]),
            {"W1", "W2", "W3", "D1", "D2"},
        )
        self.assertEqual(
            result["alignment_receipt"]["selected_record_count"],
            16,
        )
        self.assertEqual(
            len(result["alignment_receipt"]["alignments"]),
            16,
        )
        self.assertEqual(
            result["alignment_receipt"]["alignments"][0][
                "simulation_time_s"
            ],
            60.0,
        )
        self.assertEqual(len(result["raw_capture_sha256"]), 64)
        self.assertEqual(
            len(result["alignment_receipt"]["alignment_sha256"]),
            64,
        )

    def test_bad_quality_nearest_record_is_ignored_for_valid_record(self):
        raw = capture(
            self.layout,
            self.normalized["protocol_sha256"],
        )
        raw["records"].append(
            {
                "timestamp": "2026-10-06T07:11:00Z",
                "signal_type": "co2_ppm",
                "target_id": "living",
                "value": 10.0,
                "unit": "ppm",
                "quality": "estimated",
            }
        )
        result = compile_field_capture_bundle(
            layout=self.layout,
            runtime_receipt=runtime_receipt(self.layout),
            protocol=protocol(),
            capture=raw,
        )
        self.assertEqual(result["samples"][0]["co2_ppm"]["living"], 1290.0)

    def test_tampered_import_provenance_is_rejected(self):
        raw = capture(
            self.layout,
            self.normalized["protocol_sha256"],
        )
        raw["import_provenance"] = {
            "adapter": "field-capture-importer-v1",
            "records_format": "csv",
            "manifest_filename": "capture.manifest.json",
            "manifest_sha256": "a" * 64,
            "records_filename": "gateway.csv",
            "records_sha256": "b" * 64,
            "record_count": len(raw["records"]),
            "import_receipt_sha256": "0" * 64,
        }
        with self.assertRaisesRegex(
            ValueError,
            "import_provenance SHA-256 integrity",
        ):
            compile_field_capture_bundle(
                layout=self.layout,
                runtime_receipt=runtime_receipt(self.layout),
                protocol=protocol(),
                capture=raw,
            )

    def test_record_outside_alignment_window_fails_closed(self):
        raw = capture(
            self.layout,
            self.normalized["protocol_sha256"],
        )
        for row in raw["records"]:
            if (
                row["signal_type"] == "co2_ppm"
                and row["target_id"] == "living"
                and row["timestamp"] == "2026-10-06T07:11:02Z"
            ):
                row["timestamp"] = "2026-10-06T07:11:30Z"
        with self.assertRaisesRegex(
            ValueError,
            "no acceptable co2_ppm record for living at step 0",
        ):
            compile_field_capture_bundle(
                layout=self.layout,
                runtime_receipt=runtime_receipt(self.layout),
                protocol=protocol(),
                capture=raw,
            )

    def test_one_record_cannot_be_reused_for_multiple_prediction_steps(self):
        spec = protocol()
        spec["alignment"]["max_skew_s"] = 60.0
        normalized = validate_field_validation_protocol(
            self.layout,
            spec,
        )
        raw = capture(self.layout, normalized["protocol_sha256"])
        raw["records"] = [
            row
            for row in raw["records"]
            if not (
                row["signal_type"] == "co2_ppm"
                and row["target_id"] == "living"
            )
        ]
        raw["records"].append(
            {
                "timestamp": "2026-10-06T07:11:30Z",
                "signal_type": "co2_ppm",
                "target_id": "living",
                "value": 1200.0,
                "unit": "ppm",
                "quality": "measured",
            }
        )
        with self.assertRaisesRegex(
            ValueError,
            "no acceptable co2_ppm record for living at step 1",
        ):
            compile_field_capture_bundle(
                layout=self.layout,
                runtime_receipt=runtime_receipt(self.layout),
                protocol=spec,
                capture=raw,
            )


if __name__ == "__main__":
    unittest.main()
