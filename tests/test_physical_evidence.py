import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from airtrajectory.commissioning import require_commissioning_behavior
from airtrajectory.evidence import verify_physical_tau0_artifacts
from airtrajectory.lineage import (
    require_hardware_site_lineage,
    require_hardware_thingmodel_lineage,
)
from airtrajectory.sensor_lineage import build_sensor_evidence


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


def _acceptance_policy():
    return {
        "max_first_excursion_pct":5.0,
        "requested_excursion_pct":5.0,
        "position_tolerance_pct":1.0,
        "minimum_stop_hold_samples":2,
        "stop_hold_samples":2,
        "max_polls":20,
        "poll_interval_s":0.25,
        "source_timestamps_strictly_increasing":True,
        "requires_positive_open_delta":True,
        "requires_negative_close_delta":True,
    }


def _commissioning():
    return {
        "excursion_pct":5.0,
        "acceptance_policy":_acceptance_policy(),
        "phases":[
            {
                "phase":"READ",
                "commanded_pct":0.0,
                "measured_pct":0.0,
                "timestamp":101.0,
                "source":"bench-encoder",
                "quality":"measured",
                "observed_delta_pct":0.0,
                "sample_count":1,
                "position_span_pct":0.0,
                "timestamp_advanced":True,
            },
            {
                "phase":"OPEN_5",
                "commanded_pct":5.0,
                "measured_pct":5.0,
                "timestamp":102.0,
                "source":"bench-encoder",
                "quality":"measured",
                "observed_delta_pct":5.0,
                "sample_count":1,
                "position_span_pct":0.0,
                "timestamp_advanced":True,
            },
            {
                "phase":"STOP",
                "commanded_pct":5.0,
                "measured_pct":5.0,
                "timestamp":104.0,
                "source":"bench-encoder",
                "quality":"measured",
                "observed_delta_pct":0.0,
                "sample_count":2,
                "position_span_pct":0.0,
                "timestamp_advanced":True,
            },
            {
                "phase":"CLOSE",
                "commanded_pct":0.0,
                "measured_pct":0.0,
                "timestamp":105.0,
                "source":"bench-encoder",
                "quality":"measured",
                "observed_delta_pct":-5.0,
                "sample_count":1,
                "position_span_pct":0.0,
                "timestamp_advanced":True,
            },
        ],
        "behavior_witness":{
            "initial_closed_observed":True,
            "open_observed_delta_pct":5.0,
            "stop_sample_count":2,
            "stop_position_span_pct":0.0,
            "close_observed_delta_pct":-5.0,
            "source_timestamps":[101.0,102.0,104.0,105.0],
            "timestamps_strictly_increasing":True,
            "reality_delta_observed":True,
        },
    }


def _bundle_payload():
    return {
        "schema_version":"0.3",
        "status":"PASS",
        "hardware_identity":_identity(),
        "preflight":{
            "receipt_sha256":"a"*64,
            "hardware_identity_sha256":"same-hardware",
            "gateway_contract_sha256":"b"*64,
        },
        "commissioning":_commissioning(),
    }


def _sensor_evidence(commission_sha):
    readiness={
        "sensor_evidence_lineage":{
            "co2_ppm":{
                "timestamp":100.0,
                "quality":"measured",
                "source":"mqtt-co2-gateway",
                "source_scheme":"measured-runtime-source",
                "source_contract_sha256":None,
                "fresh":True,
                "measured":True,
                "registry_bound":True,
                "site_bound":True,
                "thingmodel_binding":_binding("co2"),
            },
            "rain":{
                "timestamp":100.0,
                "quality":"measured",
                "source":"mqtt-rain-gateway",
                "source_scheme":"measured-runtime-source",
                "source_contract_sha256":None,
                "fresh":True,
                "measured":True,
                "registry_bound":True,
                "site_bound":True,
                "thingmodel_binding":_binding("rain"),
            },
        }
    }
    return build_sensor_evidence(
        readiness=readiness,
        site_lineage=require_hardware_site_lineage(_identity()),
        commissioning_identity_sha256="same-hardware",
        commissioning_bundle_sha256=commission_sha,
    )


def _probe_readiness():
    rows={}
    for role,key,contract_sha,ts in (
        ("co2","co2_ppm","c"*64,100.0),
        ("rain","rain","d"*64,101.0),
    ):
        rows[key]={
            "timestamp":ts,
            "quality":"measured",
            "source":f"sensor-read-probe:{contract_sha}",
            "source_scheme":"sensor-read-probe",
            "source_contract_sha256":contract_sha,
            "fresh":True,
            "measured":True,
            "registry_bound":True,
            "site_bound":True,
            "thingmodel_binding":_binding(role),
        }
    return {"sensor_evidence_lineage":rows}


def _apply_receipt(role,commission_sha):
    return {
        "schema_version":"0.1",
        "status":"PASS",
        "network_requests_by_tool":3,
        "runtime_posts_by_tool":1,
        "actuator_writes_by_tool":0,
        "window_command_endpoints_called":0,
        "role":role,
        "role_key":"co2_ppm" if role=="co2" else "rain",
        "probe_receipt_sha256":"e"*64,
        "sensor_contract_sha256":"c"*64 if role=="co2" else "d"*64,
        "commissioning_bundle_sha256":commission_sha,
        "runtime_hardware_identity_sha256":"same-hardware",
        "site_id":"test.single-room",
        "site_manifest_sha256":"8"*64,
        "site_contract_sha256":"a"*64,
        "sample_timestamp":100.0 if role=="co2" else 101.0,
        "runtime_sensor_checks":{
            "fresh":True,
            "measured":True,
            "registry_bound":True,
            "site_bound":True,
        },
        "automation_evaluated":False,
        "actuator_command_issued":False,
    }


class PhysicalArtifactVerifierTests(unittest.TestCase):
    def _make_bundle(self,path):
        payload=_bundle_payload()
        path.write_text(json.dumps(payload),encoding="utf-8")
        return payload

    def _behavior(self,bundle):
        return require_commissioning_behavior(bundle)

    def _make_trajectory(self,path,commission_sha,behavior):
        identity=_identity()
        sensor_evidence=_sensor_evidence(commission_sha)
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
                "commissioning_behavior_witness":behavior["normalized"],
                "commissioning_behavior_sha256":behavior["sha256"],
                "sensor_evidence_origin":sensor_evidence["sensor_evidence_origin"],
                "runtime_sensor_lineage":sensor_evidence["runtime_sensor_lineage"],
                "sensor_staging_lineage":sensor_evidence["sensor_staging_lineage"],
                "sensor_evidence_sha256":sensor_evidence["sensor_evidence_sha256"],
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

    def _make_receipt(self,path,trajectory_path,commission_sha,behavior):
        identity=_identity()
        sensor_evidence=_sensor_evidence(commission_sha)
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
            "commissioning_behavior_witness":behavior["normalized"],
            "commissioning_behavior_sha256":behavior["sha256"],
            "sensor_evidence_origin":sensor_evidence["sensor_evidence_origin"],
            "runtime_sensor_lineage":sensor_evidence["runtime_sensor_lineage"],
            "sensor_staging_lineage":sensor_evidence["sensor_staging_lineage"],
            "sensor_evidence_sha256":sensor_evidence["sensor_evidence_sha256"],
            "trajectory_sha256":hashlib.sha256(trajectory_path.read_bytes()).hexdigest(),
        }
        path.write_text(json.dumps(payload),encoding="utf-8")
        return payload

    def _valid_chain(self,root):
        bundle=root/"bringup.json"
        trajectory=root/"tau0.jsonl"
        receipt=root/"audit.json"
        bundle_payload=self._make_bundle(bundle)
        behavior=self._behavior(bundle_payload)
        commission_sha=hashlib.sha256(bundle.read_bytes()).hexdigest()
        self._make_trajectory(trajectory,commission_sha,behavior)
        self._make_receipt(receipt,trajectory,commission_sha,behavior)
        return bundle,trajectory,receipt,bundle_payload,behavior,commission_sha

    def test_valid_artifact_chain_passes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle,trajectory,receipt,_,behavior,_=self._valid_chain(root)
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
        self.assertEqual(
            report["commissioning_behavior_sha256"],
            behavior["sha256"],
        )
        self.assertEqual(
            report["sensor_evidence_origin"],
            "runtime-measured-lineage",
        )
        self.assertTrue(report["sensor_evidence_sha256"])
        self.assertEqual(
            report["sensor_staging_replay_status"],
            "NOT_APPLICABLE",
        )
        self.assertFalse(report["sensor_staging_receipts_reverified"])

    def test_probe_apply_audited_artifacts_can_replay_original_receipts(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle,trajectory,receipt,_,behavior,commission_sha=self._valid_chain(root)

            apply_paths=[]
            for role in ("co2","rain"):
                path=root/f"{role}-apply.json"
                path.write_text(
                    json.dumps(_apply_receipt(role,commission_sha)),
                    encoding="utf-8",
                )
                apply_paths.append(path)

            audited=build_sensor_evidence(
                readiness=_probe_readiness(),
                site_lineage=require_hardware_site_lineage(_identity()),
                commissioning_identity_sha256="same-hardware",
                commissioning_bundle_sha256=commission_sha,
                sensor_apply_receipts=apply_paths,
            )

            trajectory_payload=json.loads(
                trajectory.read_text(encoding="utf-8").strip()
            )
            trajectory_payload["context"].update({
                "sensor_evidence_origin":audited["sensor_evidence_origin"],
                "runtime_sensor_lineage":audited["runtime_sensor_lineage"],
                "sensor_staging_lineage":audited["sensor_staging_lineage"],
                "sensor_evidence_sha256":audited["sensor_evidence_sha256"],
            })
            trajectory.write_text(
                json.dumps(trajectory_payload)+"\n",
                encoding="utf-8",
            )

            receipt_payload=json.loads(
                receipt.read_text(encoding="utf-8")
            )
            receipt_payload.update({
                "sensor_evidence_origin":audited["sensor_evidence_origin"],
                "runtime_sensor_lineage":audited["runtime_sensor_lineage"],
                "sensor_staging_lineage":audited["sensor_staging_lineage"],
                "sensor_evidence_sha256":audited["sensor_evidence_sha256"],
                "trajectory_sha256":hashlib.sha256(
                    trajectory.read_bytes()
                ).hexdigest(),
            })
            receipt.write_text(
                json.dumps(receipt_payload),
                encoding="utf-8",
            )

            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
                sensor_apply_receipt_paths=apply_paths,
            )

        self.assertTrue(report["valid_artifacts"],report["reasons"])
        self.assertEqual(
            report["sensor_evidence_origin"],
            "probe-apply-audited",
        )
        self.assertEqual(
            report["sensor_staging_replay_status"],
            "VERIFIED",
        )
        self.assertTrue(report["sensor_staging_receipts_reverified"])

    def test_sensor_evidence_origin_mismatch_between_trajectory_and_receipt_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle,trajectory,receipt,_,_,_=self._valid_chain(root)
            payload=json.loads(trajectory.read_text(encoding="utf-8"))
            payload["context"]["sensor_evidence_origin"]="probe-labeled"
            trajectory.write_text(json.dumps(payload)+"\n",encoding="utf-8")
            receipt_payload=json.loads(receipt.read_text(encoding="utf-8"))
            receipt_payload["trajectory_sha256"]=hashlib.sha256(
                trajectory.read_bytes()
            ).hexdigest()
            receipt.write_text(json.dumps(receipt_payload),encoding="utf-8")
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertTrue(any(
            "sensor_evidence_origin" in reason
            for reason in report["reasons"]
        ))

    def test_tampered_trajectory_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle,trajectory,receipt,_,_,_=self._valid_chain(root)
            payload=json.loads(trajectory.read_text(encoding="utf-8"))
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
            bundle,trajectory,receipt,bundle_payload,_,_=self._valid_chain(root)
            bundle_payload["preflight"]["gateway_contract_sha256"]="c"*64
            bundle.write_text(json.dumps(bundle_payload),encoding="utf-8")
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertTrue(any(
            "commissioning bundle SHA-256" in reason or
            "gateway contract lineage" in reason
            for reason in report["reasons"]
        ))

    def test_thingmodel_lineage_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle,trajectory,receipt,_,_,_=self._valid_chain(root)
            payload=json.loads(receipt.read_text(encoding="utf-8"))
            payload["runtime_hardware_identity"]["thingmodel_contract_sha256"]="9"*64
            receipt.write_text(json.dumps(payload),encoding="utf-8")
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertTrue(any(
            "ThingModel lineage" in reason
            for reason in report["reasons"]
        ))

    def test_missing_sensor_thingmodel_and_site_provenance_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle,trajectory,receipt,_,_,_=self._valid_chain(root)
            payload=json.loads(trajectory.read_text(encoding="utf-8"))
            payload["steps"][0]["sensor_readings"][0]["provenance"]={}
            trajectory.write_text(json.dumps(payload)+"\n",encoding="utf-8")
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertTrue(any(
            "ThingModel/site provenance" in reason
            for reason in report["reasons"]
        ))

    def test_cross_site_sensor_provenance_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle,trajectory,receipt,_,_,_=self._valid_chain(root)
            payload=json.loads(trajectory.read_text(encoding="utf-8"))
            payload["steps"][0]["sensor_readings"][0]["provenance"]["site_id"]="other.site"
            trajectory.write_text(json.dumps(payload)+"\n",encoding="utf-8")
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
            bundle,trajectory,receipt,_,_,_=self._valid_chain(root)
            payload=json.loads(receipt.read_text(encoding="utf-8"))
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

    def test_missing_commissioning_acceptance_policy_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle,trajectory,receipt,bundle_payload,_,_=self._valid_chain(root)
            bundle_payload["commissioning"].pop("acceptance_policy")
            bundle.write_text(json.dumps(bundle_payload),encoding="utf-8")
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertTrue(any(
            "acceptance_policy is missing" in reason
            for reason in report["reasons"]
        ))

    def test_weakened_commissioning_tolerance_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle,trajectory,receipt,bundle_payload,_,_=self._valid_chain(root)
            bundle_payload["commissioning"]["acceptance_policy"][
                "position_tolerance_pct"
            ]=5.0
            bundle.write_text(json.dumps(bundle_payload),encoding="utf-8")
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertTrue(any(
            "position tolerance must be >0 and <=1%" in reason
            for reason in report["reasons"]
        ))

    def test_reduced_stop_hold_policy_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle,trajectory,receipt,bundle_payload,_,_=self._valid_chain(root)
            bundle_payload["commissioning"]["acceptance_policy"][
                "stop_hold_samples"
            ]=1
            bundle.write_text(json.dumps(bundle_payload),encoding="utf-8")
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertTrue(any(
            "STOP hold samples must be >=2" in reason
            for reason in report["reasons"]
        ))

    def test_missing_commissioning_behavior_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle,trajectory,receipt,bundle_payload,_,_=self._valid_chain(root)
            bundle_payload["commissioning"].pop("behavior_witness")
            bundle.write_text(json.dumps(bundle_payload),encoding="utf-8")
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertTrue(any(
            "behavior_witness" in reason
            for reason in report["reasons"]
        ))

    def test_commissioning_phase_delta_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle,trajectory,receipt,bundle_payload,_,_=self._valid_chain(root)
            bundle_payload["commissioning"]["phases"][1]["observed_delta_pct"]=0.0
            bundle.write_text(json.dumps(bundle_payload),encoding="utf-8")
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertTrue(any(
            "OPEN_5 observed_delta_pct" in reason
            for reason in report["reasons"]
        ))

    def test_receipt_commissioning_behavior_hash_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle,trajectory,receipt,_,_,_=self._valid_chain(root)
            payload=json.loads(receipt.read_text(encoding="utf-8"))
            payload["commissioning_behavior_sha256"]="f"*64
            receipt.write_text(json.dumps(payload),encoding="utf-8")
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertTrue(any(
            "behavior witness/hash mismatch" in reason or
            "behavior SHA-256" in reason
            for reason in report["reasons"]
        ))

    def test_trajectory_commissioning_behavior_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle,trajectory,receipt,_,_,_=self._valid_chain(root)
            payload=json.loads(trajectory.read_text(encoding="utf-8"))
            payload["context"]["commissioning_behavior_witness"][
                "behavior_witness"
            ]["stop_sample_count"]=1
            trajectory.write_text(json.dumps(payload)+"\n",encoding="utf-8")
            report=verify_physical_tau0_artifacts(
                trajectory_path=trajectory,
                receipt_path=receipt,
                commission_bundle_path=bundle,
            )
        self.assertFalse(report["valid_artifacts"])
        self.assertTrue(any(
            "trajectory commissioning behavior" in reason or
            "behavior witness/hash mismatch" in reason
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
