import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from airtrajectory.contam_field_validation import (
    validate_field_validation_protocol,
)
from airtrajectory.field_validation_pipeline import (
    run_field_validation_pipeline,
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
        "protocol_id": "pipeline-v1",
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
            "max_skew_s": 5.0,
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


def runtime(layout):
    series = [
        {
            "step": 0,
            "simulation_time_s": 60.0,
            "co2_ppm": {"living": 1300.0, "bedroom": 900.0, "study": 800.0},
            "opening_pct": {
                "W1": 75.0, "W2": 35.0, "W3": 0.0, "D1": 100.0, "D2": 100.0
            },
            "path_flow_kg_s": {
                "W1": 0.2, "W2": 0.1, "W3": 0.01, "D1": 0.05, "D2": 0.04
            },
        },
        {
            "step": 1,
            "simulation_time_s": 120.0,
            "co2_ppm": {"living": 1100.0, "bedroom": 850.0, "study": 790.0},
            "opening_pct": {
                "W1": 75.0, "W2": 35.0, "W3": 0.0, "D1": 100.0, "D2": 100.0
            },
            "path_flow_kg_s": {
                "W1": 0.18, "W2": 0.09, "W3": 0.01, "D1": 0.04, "D2": 0.03
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
        "simulation_time_step_s": 60.0,
        "prediction_time_origin": "post-reset-policy-step",
        "prediction_series": series,
        "prediction_series_sha256": sha(series),
    }
    return {**payload, "runtime_receipt_sha256": sha(payload)}


def make_records(offset=0.0):
    values = [
        (60, {"living":1290+offset,"bedroom":905+offset,"study":805+offset}),
        (120, {"living":1095+offset,"bedroom":855+offset,"study":795+offset}),
    ]
    rows=[]
    for seconds, co2 in values:
        stamp = (
            "2026-10-06T07:11:00Z"
            if seconds == 60
            else "2026-10-06T07:12:00Z"
        )
        for zone,value in co2.items():
            rows.append({
                "timestamp":stamp,"signal_type":"co2_ppm","target_id":zone,
                "value":value,"unit":"ppm","quality":"measured",
            })
        for opening,value in {
            "W1":75.0,"W2":35.0,"W3":0.0,"D1":100.0,"D2":100.0
        }.items():
            rows.append({
                "timestamp":stamp,"signal_type":"opening_pct","target_id":opening,
                "value":value,"unit":"percent","quality":"measured",
            })
    return rows


class FieldValidationPipelineTests(unittest.TestCase):
    def setUp(self):
        self.layout=LayoutContract.from_file(LAYOUT)

    def fixture(self,tmp,offset=0.0):
        run=runtime(self.layout)
        normalized=validate_field_validation_protocol(self.layout,protocol())
        manifest={
            "schema_version":"0.1",
            "validation_id":"pipeline-run-001",
            "protocol_id":"pipeline-v1",
            "protocol_sha256":normalized["protocol_sha256"],
            "topology_id":self.layout.topology_id,
            "runtime_receipt_sha256":run["runtime_receipt_sha256"],
            "started_at":"2026-10-06T07:10:00Z",
            "source":{
                "kind":"site-sensor-system","id":"gw-1","model":"rig",
                "serial":"SN-1","calibration_ref":"CAL-1",
            },
        }
        manifest_path=Path(tmp)/"capture.manifest.json"
        manifest_path.write_text(json.dumps(manifest),encoding="utf-8")
        records_path=Path(tmp)/"gateway.csv"
        with records_path.open("w",encoding="utf-8",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=[
                "timestamp","signal_type","target_id","value","unit","quality"
            ])
            writer.writeheader()
            writer.writerows(make_records(offset))
        return run,manifest_path,records_path

    def test_one_shot_pipeline_passes_and_binds_all_intermediate_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run,manifest_path,records_path=self.fixture(tmp)
            receipt,aligned=run_field_validation_pipeline(
                layout=self.layout,
                runtime_receipt=run,
                protocol=protocol(),
                manifest_path=manifest_path,
                records_path=records_path,
            )
        self.assertEqual(receipt["status"],"FIELD_VALIDATION_PASSED")
        self.assertTrue(receipt["field_validation_verified"])
        self.assertTrue(receipt["engineering_truth"])
        self.assertEqual(len(receipt["pipeline_receipt_sha256"]),64)
        self.assertEqual(
            receipt["source_records_sha256"],
            aligned["import_provenance"]["records_sha256"],
        )
        self.assertEqual(
            receipt["alignment_sha256"],
            aligned["alignment_receipt"]["alignment_sha256"],
        )

    def test_one_shot_pipeline_returns_failed_receipt_when_metrics_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            run,manifest_path,records_path=self.fixture(tmp,offset=200.0)
            receipt,_=run_field_validation_pipeline(
                layout=self.layout,
                runtime_receipt=run,
                protocol=protocol(),
                manifest_path=manifest_path,
                records_path=records_path,
            )
        self.assertEqual(receipt["status"],"FIELD_VALIDATION_FAILED")
        self.assertFalse(receipt["field_validation_verified"])
        self.assertFalse(receipt["engineering_truth"])


if __name__ == "__main__":
    unittest.main()
