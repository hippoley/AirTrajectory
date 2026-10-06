import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from airtrajectory.field_capture_import import import_field_capture


def manifest():
    return {
        "schema_version": "0.1",
        "validation_id": "field-run-001",
        "protocol_id": "field-validation-v1",
        "protocol_sha256": "p" * 64,
        "topology_id": "demo.fixed-three-room.v1",
        "runtime_receipt_sha256": "r" * 64,
        "started_at": "2026-10-06T07:10:00Z",
        "source": {
            "kind": "site-sensor-system",
            "id": "gateway-001",
            "model": "gw-model",
            "serial": "GW-001",
            "calibration_ref": "CAL-001",
        },
    }


def rows():
    return [
        {
            "timestamp": "2026-10-06T07:11:00Z",
            "signal_type": "co2_ppm",
            "target_id": "living",
            "value": 1290.0,
            "unit": "ppm",
            "quality": "measured",
        },
        {
            "timestamp": "2026-10-06T07:11:00Z",
            "signal_type": "opening_pct",
            "target_id": "W1",
            "value": 75.0,
            "unit": "percent",
            "quality": "measured",
        },
    ]


class FieldCaptureImportTests(unittest.TestCase):
    def write_manifest(self, root):
        path = Path(root) / "capture.manifest.json"
        path.write_text(json.dumps(manifest()), encoding="utf-8")
        return path

    def test_jsonl_import_preserves_file_hash_and_normalizes_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self.write_manifest(tmp)
            records_path = Path(tmp) / "gateway.jsonl"
            raw = "".join(
                json.dumps(row) + "\n"
                for row in rows()
            ).encode("utf-8")
            records_path.write_bytes(raw)
            result = import_field_capture(
                manifest_path=manifest_path,
                records_path=records_path,
            )
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual(result["records"][0]["value"], 1290.0)
        self.assertEqual(
            result["import_provenance"]["records_format"],
            "jsonl",
        )
        self.assertEqual(
            result["import_provenance"]["records_sha256"],
            hashlib.sha256(raw).hexdigest(),
        )

    def test_csv_import_supports_gateway_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self.write_manifest(tmp)
            records_path = Path(tmp) / "gateway.csv"
            with records_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows()[0]))
                writer.writeheader()
                writer.writerows(rows())
            result = import_field_capture(
                manifest_path=manifest_path,
                records_path=records_path,
            )
        self.assertEqual(result["import_provenance"]["records_format"], "csv")
        self.assertEqual(
            [row["signal_type"] for row in result["records"]],
            ["co2_ppm", "opening_pct"],
        )

    def test_missing_csv_header_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self.write_manifest(tmp)
            records_path = Path(tmp) / "gateway.csv"
            records_path.write_text(
                "timestamp,target_id,value\n"
                "2026-10-06T07:11:00Z,living,1290\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "missing headers"):
                import_field_capture(
                    manifest_path=manifest_path,
                    records_path=records_path,
                )

    def test_manifest_cannot_hide_another_embedded_record_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = manifest()
            bad["records"] = rows()
            manifest_path = Path(tmp) / "capture.manifest.json"
            manifest_path.write_text(json.dumps(bad), encoding="utf-8")
            records_path = Path(tmp) / "gateway.jsonl"
            records_path.write_text(
                json.dumps(rows()[0]) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "must not embed records"):
                import_field_capture(
                    manifest_path=manifest_path,
                    records_path=records_path,
                )


if __name__ == "__main__":
    unittest.main()
