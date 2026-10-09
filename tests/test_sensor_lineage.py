import json
import tempfile
import unittest
from pathlib import Path

from airtrajectory.sensor_lineage import (
    build_sensor_evidence,
    validate_sensor_evidence_context,
)


def _site_lineage():
    return {
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


def _binding(role):
    if role=="co2":
        return {
            "product_model":"KKCA-WD01",
            "product_key":"ojMicFXQWTs",
            "device_id":"co2-device-01",
            "property":"airSensor.co2",
            "source_sha256":"1"*64,
            "source_bundle_sha256":"2"*64,
            "registry_sha256":"3"*64,
            "contract_sha256":"4"*64,
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
        "source_sha256":"5"*64,
        "source_bundle_sha256":"2"*64,
        "registry_sha256":"3"*64,
        "contract_sha256":"6"*64,
        "site_id":"test.single-room",
        "site_instance_id":"living.window.primary",
        "site_manifest_sha256":"8"*64,
        "site_contract_sha256":"a"*64,
    }


def _readiness(*,probe=False):
    rows={}
    for role,key,contract_sha,ts in (
        ("co2","co2_ppm","c"*64,100.0),
        ("rain","rain","d"*64,101.0),
    ):
        rows[key]={
            "timestamp":ts,
            "quality":"measured",
            "source":(
                f"sensor-read-probe:{contract_sha}"
                if probe else f"mqtt-{role}-gateway"
            ),
            "source_scheme":(
                "sensor-read-probe"
                if probe else "measured-runtime-source"
            ),
            "source_contract_sha256":contract_sha if probe else None,
            "measured":True,
            "fresh":True,
            "registry_bound":True,
            "site_bound":True,
            "thingmodel_binding":_binding(role),
        }
    return {
        "sensor_evidence_lineage":rows,
    }


def _apply_receipt(role,commission_sha,identity="same-hardware"):
    key="co2_ppm" if role=="co2" else "rain"
    contract_sha="c"*64 if role=="co2" else "d"*64
    timestamp=100.0 if role=="co2" else 101.0
    return {
        "schema_version":"0.1",
        "status":"PASS",
        "network_requests_by_tool":3,
        "runtime_posts_by_tool":1,
        "actuator_writes_by_tool":0,
        "window_command_endpoints_called":0,
        "role":role,
        "role_key":key,
        "probe_receipt_sha256":"e"*64,
        "sensor_contract_sha256":contract_sha,
        "commissioning_bundle_sha256":commission_sha,
        "runtime_hardware_identity_sha256":identity,
        "site_id":"test.single-room",
        "site_manifest_sha256":"8"*64,
        "site_contract_sha256":"a"*64,
        "sample_timestamp":timestamp,
        "runtime_sensor_checks":{
            "fresh":True,
            "measured":True,
            "registry_bound":True,
            "site_bound":True,
        },
        "automation_evaluated":False,
        "actuator_command_issued":False,
    }


class SensorLineageTests(unittest.TestCase):
    def test_generic_measured_runtime_source_stays_transport_neutral(self):
        evidence=build_sensor_evidence(
            readiness=_readiness(probe=False),
            site_lineage=_site_lineage(),
            commissioning_identity_sha256="same-hardware",
            commissioning_bundle_sha256="b"*64,
        )
        self.assertEqual(
            evidence["sensor_evidence_origin"],
            "runtime-measured-lineage",
        )
        self.assertIsNone(evidence["sensor_staging_lineage"])
        self.assertEqual(
            evidence["runtime_sensor_lineage"]["co2"]["source_scheme"],
            "measured-runtime-source",
        )
        validate_sensor_evidence_context(
            sensor_evidence_origin=evidence["sensor_evidence_origin"],
            runtime_sensor_lineage=evidence["runtime_sensor_lineage"],
            sensor_staging_lineage=evidence["sensor_staging_lineage"],
            sensor_evidence_sha256=evidence["sensor_evidence_sha256"],
            site_lineage=_site_lineage(),
            commissioning_identity_sha256="same-hardware",
            commissioning_bundle_sha256="b"*64,
        )

    def test_sensor_apply_receipt_counters_must_be_exact_integers(self):
        for invalid in (3.9, True, "3"):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as d:
                paths=[]
                for role in ("co2", "rain"):
                    receipt=_apply_receipt(role, "b"*64)
                    if role=="co2":
                        receipt["network_requests_by_tool"]=invalid
                    path=Path(d)/(role+".json")
                    path.write_text(json.dumps(receipt), encoding="utf-8")
                    paths.append(path)
                with self.assertRaisesRegex(RuntimeError, "network_requests_by_tool"):
                    build_sensor_evidence(
                        readiness=_readiness(probe=True),
                        site_lineage=_site_lineage(),
                        commissioning_identity_sha256="same-hardware",
                        commissioning_bundle_sha256="b"*64,
                        sensor_apply_receipts=paths,
                    )

    def test_nonfinite_live_sensor_timestamps_rejected(self):
        for role in ("co2_ppm", "rain"):
            for invalid in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(role=role, invalid=invalid):
                    readiness = _readiness(probe=False)
                    readiness["sensor_evidence_lineage"][role]["timestamp"] = invalid
                    with self.assertRaisesRegex(RuntimeError, "timestamp must be positive"):
                        build_sensor_evidence(
                            readiness=readiness,
                            site_lineage=_site_lineage(),
                            commissioning_identity_sha256="same-hardware",
                            commissioning_bundle_sha256="b"*64,
                        )

    def test_nonfinite_apply_timestamp_rejected(self):
        for invalid in (float("nan"), float("inf")):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as d:
                root=Path(d)
                records=[]
                for role in ("co2", "rain"):
                    receipt=_apply_receipt(role, "b"*64)
                    if role == "co2":
                        receipt["sample_timestamp"]=invalid
                    path=root/f"{role}.json"
                    path.write_text(json.dumps(receipt), encoding="utf-8")
                    records.append(path)
                with self.assertRaisesRegex(RuntimeError, "sample_timestamp must be finite"):
                    build_sensor_evidence(
                        readiness=_readiness(probe=True),
                        site_lineage=_site_lineage(),
                        commissioning_identity_sha256="same-hardware",
                        commissioning_bundle_sha256="b"*64,
                        sensor_apply_receipts=records,
                    )

    def test_probe_labeled_sources_are_not_audited_without_apply_receipts(self):
        evidence=build_sensor_evidence(
            readiness=_readiness(probe=True),
            site_lineage=_site_lineage(),
            commissioning_identity_sha256="same-hardware",
            commissioning_bundle_sha256="b"*64,
        )
        self.assertEqual(evidence["sensor_evidence_origin"],"probe-labeled")
        self.assertIsNone(evidence["sensor_staging_lineage"])

    def test_exactly_two_apply_receipts_upgrade_to_audited(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            commission_sha="b"*64
            paths=[]
            for role in ("co2","rain"):
                path=root/f"{role}-apply.json"
                path.write_text(
                    json.dumps(_apply_receipt(role,commission_sha)),
                    encoding="utf-8",
                )
                paths.append(path)
            evidence=build_sensor_evidence(
                readiness=_readiness(probe=True),
                site_lineage=_site_lineage(),
                commissioning_identity_sha256="same-hardware",
                commissioning_bundle_sha256=commission_sha,
                sensor_apply_receipts=paths,
            )

        self.assertEqual(
            evidence["sensor_evidence_origin"],
            "probe-apply-audited",
        )
        self.assertEqual(
            set(evidence["sensor_staging_lineage"]),
            {"co2","rain"},
        )
        self.assertEqual(
            evidence["sensor_staging_lineage"]["co2"][
                "sensor_contract_sha256"
            ],
            "c"*64,
        )
        validate_sensor_evidence_context(
            sensor_evidence_origin=evidence["sensor_evidence_origin"],
            runtime_sensor_lineage=evidence["runtime_sensor_lineage"],
            sensor_staging_lineage=evidence["sensor_staging_lineage"],
            sensor_evidence_sha256=evidence["sensor_evidence_sha256"],
            site_lineage=_site_lineage(),
            commissioning_identity_sha256="same-hardware",
            commissioning_bundle_sha256="b"*64,
        )

    def test_partial_apply_receipt_set_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"co2.json"
            path.write_text(
                json.dumps(_apply_receipt("co2","b"*64)),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "exactly two",
            ):
                build_sensor_evidence(
                    readiness=_readiness(probe=True),
                    site_lineage=_site_lineage(),
                    commissioning_identity_sha256="same-hardware",
                    commissioning_bundle_sha256="b"*64,
                    sensor_apply_receipts=[path],
                )

    def test_apply_receipt_contract_must_match_live_source(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            co2=_apply_receipt("co2","b"*64)
            co2["sensor_contract_sha256"]="f"*64
            p1=root/"co2.json"
            p1.write_text(json.dumps(co2),encoding="utf-8")
            p2=root/"rain.json"
            p2.write_text(
                json.dumps(_apply_receipt("rain","b"*64)),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "live sensor contract SHA",
            ):
                build_sensor_evidence(
                    readiness=_readiness(probe=True),
                    site_lineage=_site_lineage(),
                    commissioning_identity_sha256="same-hardware",
                    commissioning_bundle_sha256="b"*64,
                    sensor_apply_receipts=[p1,p2],
                )

    def test_apply_receipt_cross_site_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            co2=_apply_receipt("co2","b"*64)
            co2["site_id"]="other.site"
            p1=root/"co2.json"
            p1.write_text(json.dumps(co2),encoding="utf-8")
            p2=root/"rain.json"
            p2.write_text(
                json.dumps(_apply_receipt("rain","b"*64)),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "physical-site lineage mismatch",
            ):
                build_sensor_evidence(
                    readiness=_readiness(probe=True),
                    site_lineage=_site_lineage(),
                    commissioning_identity_sha256="same-hardware",
                    commissioning_bundle_sha256="b"*64,
                    sensor_apply_receipts=[p1,p2],
                )

    def test_apply_receipt_wrong_runtime_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            co2=_apply_receipt("co2","b"*64,identity="other-hardware")
            p1=root/"co2.json"
            p1.write_text(json.dumps(co2),encoding="utf-8")
            p2=root/"rain.json"
            p2.write_text(
                json.dumps(_apply_receipt("rain","b"*64)),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "hardware identity",
            ):
                build_sensor_evidence(
                    readiness=_readiness(probe=True),
                    site_lineage=_site_lineage(),
                    commissioning_identity_sha256="same-hardware",
                    commissioning_bundle_sha256="b"*64,
                    sensor_apply_receipts=[p1,p2],
                )

    def test_context_hash_tamper_is_rejected(self):
        evidence=build_sensor_evidence(
            readiness=_readiness(probe=False),
            site_lineage=_site_lineage(),
            commissioning_identity_sha256="same-hardware",
            commissioning_bundle_sha256="b"*64,
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "context/hash mismatch",
        ):
            validate_sensor_evidence_context(
                sensor_evidence_origin=evidence["sensor_evidence_origin"],
                runtime_sensor_lineage=evidence["runtime_sensor_lineage"],
                sensor_staging_lineage=evidence["sensor_staging_lineage"],
                sensor_evidence_sha256="f"*64,
                site_lineage=_site_lineage(),
                commissioning_identity_sha256="same-hardware",
                commissioning_bundle_sha256="b"*64,
            )

    def test_readiness_binding_must_belong_to_commissioned_site(self):
        readiness=_readiness(probe=False)
        readiness["sensor_evidence_lineage"]["co2_ppm"][
            "thingmodel_binding"
        ]["site_id"]="other.site"
        with self.assertRaisesRegex(
            RuntimeError,
            "different physical site",
        ):
            build_sensor_evidence(
                readiness=readiness,
                site_lineage=_site_lineage(),
                commissioning_identity_sha256="same-hardware",
                commissioning_bundle_sha256="b"*64,
            )


if __name__=="__main__":
    unittest.main()
