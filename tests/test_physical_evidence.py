import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from airtrajectory.evidence import verify_physical_tau0_artifacts


class PhysicalArtifactVerifierTests(unittest.TestCase):
    def _make_bundle(self,path):
        payload={
            "status":"PASS",
            "hardware_identity":{"identity_sha256":"same-hardware"},
            "preflight":{
                "receipt_sha256":"a"*64,
                "hardware_identity_sha256":"same-hardware",
                "gateway_contract_sha256":"b"*64,
            },
        }
        path.write_text(json.dumps(payload),encoding="utf-8")
        return payload

    def _make_trajectory(self,path,commission_sha):
        payload={
            "id":"trajectory-1",
            "environment_kind":"physical",
            "context":{
                "commissioning_identity_sha256":"same-hardware",
                "runtime_hardware_identity":{"identity_sha256":"same-hardware"},
                "commissioning_bundle_sha256":commission_sha,
                "preflight_receipt_sha256":"a"*64,
                "preflight_hardware_identity_sha256":"same-hardware",
                "gateway_contract_sha256":"b"*64,
            },
            "steps":[{
                "sensor_readings":[
                    {"sensor_type":"co2","timestamp":100.0},
                    {"sensor_type":"rain","timestamp":100.0},
                ],
                "actuator_feedback":[
                    {"timestamp":101.0,"measured_position_pct":5.0}
                ],
                "next_sensor_readings":[
                    {"sensor_type":"co2","timestamp":102.0},
                    {"sensor_type":"rain","timestamp":102.0},
                ],
            }],
        }
        path.write_text(json.dumps(payload)+"\n",encoding="utf-8")
        return payload

    def _make_receipt(self,path,trajectory_path,commission_sha):
        payload={
            "trajectory_id":"trajectory-1",
            "valid_tau0":True,
            "environment_kind":"physical",
            "steps":1,
            "commissioning_identity_sha256":"same-hardware",
            "runtime_hardware_identity":{"identity_sha256":"same-hardware"},
            "commissioning_bundle_sha256":commission_sha,
            "preflight_receipt_sha256":"a"*64,
            "preflight_hardware_identity_sha256":"same-hardware",
            "gateway_contract_sha256":"b"*64,
            "trajectory_sha256":hashlib.sha256(trajectory_path.read_bytes()).hexdigest(),
        }
        path.write_text(json.dumps(payload),encoding="utf-8")
        return payload

    def test_valid_artifact_chain_passes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle=root/"bringup.json"
            trajectory=root/"tau0.jsonl"
            receipt=root/"audit.json"
            self._make_bundle(bundle)
            commission_sha=hashlib.sha256(bundle.read_bytes()).hexdigest()
            self._make_trajectory(trajectory,commission_sha)
            self._make_receipt(receipt,trajectory,commission_sha)
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertTrue(report["valid_artifacts"],report["reasons"])
        self.assertEqual(report["trajectory_id"],"trajectory-1")

    def test_tampered_trajectory_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle=root/"bringup.json"
            trajectory=root/"tau0.jsonl"
            receipt=root/"audit.json"
            self._make_bundle(bundle)
            commission_sha=hashlib.sha256(bundle.read_bytes()).hexdigest()
            payload=self._make_trajectory(trajectory,commission_sha)
            self._make_receipt(receipt,trajectory,commission_sha)
            payload["steps"][0]["next_sensor_readings"][0]["timestamp"]=99.0
            trajectory.write_text(json.dumps(payload)+"\n",encoding="utf-8")
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertTrue(any("SHA-256" in reason for reason in report["reasons"]))

    def test_commissioning_lineage_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle=root/"bringup.json"
            trajectory=root/"tau0.jsonl"
            receipt=root/"audit.json"
            bundle_payload=self._make_bundle(bundle)
            commission_sha=hashlib.sha256(bundle.read_bytes()).hexdigest()
            self._make_trajectory(trajectory,commission_sha)
            self._make_receipt(receipt,trajectory,commission_sha)
            bundle_payload["preflight"]["gateway_contract_sha256"]="c"*64
            bundle.write_text(json.dumps(bundle_payload),encoding="utf-8")
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertTrue(any(
            "commissioning bundle SHA-256" in reason or "gateway contract lineage" in reason
            for reason in report["reasons"]
        ))

    def test_missing_artifact_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            report=verify_physical_tau0_artifacts(
                trajectory_path=root/"missing.jsonl",
                receipt_path=root/"missing-audit.json",
                commission_bundle_path=root/"missing-bringup.json",
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertEqual(len(report["reasons"]),3)


if __name__=="__main__":
    unittest.main()
