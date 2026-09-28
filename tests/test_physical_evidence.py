import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from airtrajectory.evidence import verify_physical_tau0_artifacts
from airtrajectory.lineage import require_hardware_site_lineage, require_hardware_thingmodel_lineage


def _identity(identity_sha="same-hardware"):
    return {
        "identity_sha256":identity_sha,
        "device_id":"window-device-01",
        "thingmodel_product_model":"CWDS-CA01",
        "thingmodel_product_key":"6nZ1oIh6VNu",
        "thingmodel_version":"v1",
        "thingmodel_source_sha256":"1"*64,
        "thingmodel_source_bundle_sha256":"2"*64,
        "thingmodel_registry_sha256":"3"*64,
        "thingmodel_contract_sha256":"4"*64,
        "site_id":"test.single-room",
        "room_id":"living",
        "device_instance_id":"living.window.primary",
        "site_device_id":"window-device-01",
        "site_product_model":"CWDS-CA01",
        "site_product_key":"6nZ1oIh6VNu",
        "site_manifest_sha256":"8"*64,
        "site_instance_contract_sha256":"9"*64,
        "site_contract_sha256":"a"*64,
    }


def _binding(kind):
    if kind=="co2":
        return {
            "product_model":"KKCA-WD01",
            "product_key":"ojMicFXQWTs",
            "device_id":"co2-device-01",
            "property":"airSensor.co2",
            "source_sha256":"5"*64,
            "source_bundle_sha256":"2"*64,
            "registry_sha256":"3"*64,
            "contract_sha256":"6"*64,
            "site_id":"test.single-room",
            "site_instance_id":"living.air.primary",
            "site_manifest_sha256":"8"*64,
            "site_contract_sha256":"a"*64,
        }
    return {
        "product_model":"CWDS-CA01",
        "product_key":"6nZ1oIh6VNu",
        "device_id":"window-device-01",
        "property":"rainSensor.rainDetect",
        "source_sha256":"1"*64,
        "source_bundle_sha256":"2"*64,
        "registry_sha256":"3"*64,
        "contract_sha256":"7"*64,
        "site_id":"test.single-room",
        "site_instance_id":"living.window.primary",
        "site_manifest_sha256":"8"*64,
        "site_contract_sha256":"a"*64,
    }


class PhysicalArtifactVerifierTests(unittest.TestCase):
    def _make_bundle(self,path):
        identity=_identity()
        payload={
            "status":"PASS",
            "hardware_identity":identity,
            "preflight":{
                "receipt_sha256":"a"*64,
                "hardware_identity_sha256":"same-hardware",
                "gateway_contract_sha256":"b"*64,
            },
        }
        path.write_text(json.dumps(payload),encoding="utf-8")
        return payload

    def _make_trajectory(self,path,commission_sha):
        identity=_identity()
        payload={
            "id":"trajectory-1",
            "environment_kind":"physical",
            "context":{
                "commissioning_identity_sha256":"same-hardware",
                "commissioning_hardware_identity":identity,
                "runtime_hardware_identity":identity,
                "thingmodel_lineage":require_hardware_thingmodel_lineage(identity),
                "site_lineage":require_hardware_site_lineage(identity),
                "commissioning_bundle_sha256":commission_sha,
                "preflight_receipt_sha256":"a"*64,
                "preflight_hardware_identity_sha256":"same-hardware",
                "gateway_contract_sha256":"b"*64,
            },
            "steps":[{
                "sensor_readings":[
                    {
                        "sensor_type":"co2","timestamp":100.0,
                        "provenance":_binding("co2"),
                    },
                    {
                        "sensor_type":"rain","timestamp":100.0,
                        "provenance":_binding("rain"),
                    },
                ],
                "actuator_feedback":[
                    {"timestamp":101.0,"measured_position_pct":5.0}
                ],
                "next_sensor_readings":[
                    {
                        "sensor_type":"co2","timestamp":102.0,
                        "provenance":_binding("co2"),
                    },
                    {
                        "sensor_type":"rain","timestamp":102.0,
                        "provenance":_binding("rain"),
                    },
                ],
            }],
        }
        path.write_text(json.dumps(payload)+"\n",encoding="utf-8")
        return payload

    def _make_receipt(self,path,trajectory_path,commission_sha):
        identity=_identity()
        payload={
            "trajectory_id":"trajectory-1",
            "valid_tau0":True,
            "environment_kind":"physical",
            "steps":1,
            "commissioning_identity_sha256":"same-hardware",
            "commissioning_hardware_identity":identity,
            "runtime_hardware_identity":identity,
            "thingmodel_lineage":require_hardware_thingmodel_lineage(identity),
            "site_lineage":require_hardware_site_lineage(identity),
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
        self.assertEqual(
            report["thingmodel_lineage"]["thingmodel_product_model"],
            "CWDS-CA01",
        )
        self.assertEqual(
            report["site_lineage"]["device_instance_id"],
            "living.window.primary",
        )

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

    def test_thingmodel_lineage_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle=root/"bringup.json"
            trajectory=root/"tau0.jsonl"
            receipt=root/"audit.json"
            self._make_bundle(bundle)
            commission_sha=hashlib.sha256(bundle.read_bytes()).hexdigest()
            self._make_trajectory(trajectory,commission_sha)
            payload=self._make_receipt(receipt,trajectory,commission_sha)
            payload["runtime_hardware_identity"]["thingmodel_contract_sha256"]="9"*64
            receipt.write_text(json.dumps(payload),encoding="utf-8")
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertTrue(any("ThingModel lineage" in reason for reason in report["reasons"]))

    def test_missing_sensor_thingmodel_and_site_provenance_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle=root/"bringup.json"
            trajectory=root/"tau0.jsonl"
            receipt=root/"audit.json"
            self._make_bundle(bundle)
            commission_sha=hashlib.sha256(bundle.read_bytes()).hexdigest()
            payload=self._make_trajectory(trajectory,commission_sha)
            payload["steps"][0]["sensor_readings"][0]["provenance"]={}
            trajectory.write_text(json.dumps(payload)+"\n",encoding="utf-8")
            self._make_receipt(receipt,trajectory,commission_sha)
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertTrue(any("ThingModel/site provenance" in reason for reason in report["reasons"]))

    def test_cross_site_sensor_provenance_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle=root/"bringup.json"
            trajectory=root/"tau0.jsonl"
            receipt=root/"audit.json"
            self._make_bundle(bundle)
            commission_sha=hashlib.sha256(bundle.read_bytes()).hexdigest()
            payload=self._make_trajectory(trajectory,commission_sha)
            payload["steps"][0]["sensor_readings"][0]["provenance"]["site_id"]="other.site"
            trajectory.write_text(json.dumps(payload)+"\n",encoding="utf-8")
            self._make_receipt(receipt,trajectory,commission_sha)
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertTrue(any(
            "different physical site contract" in reason
            for reason in report["reasons"]
        ))

    def test_site_lineage_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle=root/"bringup.json"
            trajectory=root/"tau0.jsonl"
            receipt=root/"audit.json"
            self._make_bundle(bundle)
            commission_sha=hashlib.sha256(bundle.read_bytes()).hexdigest()
            self._make_trajectory(trajectory,commission_sha)
            payload=self._make_receipt(receipt,trajectory,commission_sha)
            payload["runtime_hardware_identity"]["device_instance_id"]="bedroom.window.primary"
            receipt.write_text(json.dumps(payload),encoding="utf-8")
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertTrue(any(
            "physical-site lineage" in reason or "site" in reason
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
