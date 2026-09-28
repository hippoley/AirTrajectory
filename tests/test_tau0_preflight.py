import json
from pathlib import Path
import tempfile
import unittest

from airtrajectory.physical import DriverCapabilities
from airtrajectory.tau0_preflight import validate_physical_tau0_preconditions


def _binding(role):
    return {
        "product_model":"SENSOR-"+role.upper(),
        "product_key":"pk-"+role,
        "device_id":"device-"+role,
        "property":"airSensor.co2" if role=="co2" else "rainSensor.rainDetect",
        "source_sha256":"1"*64,
        "source_bundle_sha256":"2"*64,
        "registry_sha256":"3"*64,
        "contract_sha256":"4"*64,
        "site_id":"site-1",
        "site_instance_id":"living."+role+".primary",
        "site_manifest_sha256":"5"*64,
        "site_contract_sha256":"7"*64,
    }


def _identity():
    return {
        "identity_sha256":"same-hardware",
        "device_id":"window-device-1",
        "thingmodel_product_model":"CWDS-CA01",
        "thingmodel_product_key":"pk-window",
        "thingmodel_version":"1.0",
        "thingmodel_source_sha256":"1"*64,
        "thingmodel_source_bundle_sha256":"2"*64,
        "thingmodel_registry_sha256":"3"*64,
        "thingmodel_contract_sha256":"4"*64,
        "site_id":"site-1",
        "room_id":"living",
        "device_instance_id":"living.window.primary",
        "site_device_id":"window-device-1",
        "site_product_model":"CWDS-CA01",
        "site_product_key":"pk-window",
        "site_manifest_sha256":"5"*64,
        "site_instance_contract_sha256":"6"*64,
        "site_contract_sha256":"7"*64,
    }


def _commissioning():
    policy={
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
    phases=[
        {
            "phase":"READ","commanded_pct":0.0,"measured_pct":0.0,
            "timestamp":101.0,"observed_delta_pct":0.0,
            "sample_count":1,"position_span_pct":0.0,"timestamp_advanced":True,
        },
        {
            "phase":"OPEN_5","commanded_pct":5.0,"measured_pct":5.0,
            "timestamp":102.0,"observed_delta_pct":5.0,
            "sample_count":1,"position_span_pct":0.0,"timestamp_advanced":True,
        },
        {
            "phase":"STOP","commanded_pct":5.0,"measured_pct":5.0,
            "timestamp":103.0,"observed_delta_pct":0.0,
            "sample_count":2,"position_span_pct":0.0,"timestamp_advanced":True,
        },
        {
            "phase":"CLOSE","commanded_pct":0.0,"measured_pct":0.0,
            "timestamp":104.0,"observed_delta_pct":-5.0,
            "sample_count":1,"position_span_pct":0.0,"timestamp_advanced":True,
        },
    ]
    witness={
        "initial_closed_observed":True,
        "open_observed_delta_pct":5.0,
        "stop_sample_count":2,
        "stop_position_span_pct":0.0,
        "close_observed_delta_pct":-5.0,
        "source_timestamps":[101.0,102.0,103.0,104.0],
        "timestamps_strictly_increasing":True,
        "reality_delta_observed":True,
    }
    return {
        "excursion_pct":5.0,
        "acceptance_policy":policy,
        "phases":phases,
        "behavior_witness":witness,
    }


def _bundle():
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


def _readiness(overrides=None):
    identity=_identity()
    payload={
        "capture_preconditions":True,
        "physical_write_ready":True,
        "write_blockers":[],
        "hardware_identity":identity,
        "latest_position_feedback":{
            "position_pct":0.0,
            "timestamp":199.0,
            "measured":True,
            "quality":"encoder-measured",
            "source":"CWDS-CA01",
        },
        "registry_bound_sensors":{"co2_ppm":True,"rain":True},
        "site_bound_sensors":{"co2_ppm":True,"rain":True},
        "sensor_evidence_lineage":{
            "co2_ppm":{
                "timestamp":200.0,
                "quality":"measured",
                "source":"mqtt-co2-gateway",
                "source_scheme":"measured-runtime-source",
                "source_contract_sha256":None,
                "fresh":True,"measured":True,
                "registry_bound":True,"site_bound":True,
                "thingmodel_binding":_binding("co2"),
            },
            "rain":{
                "timestamp":200.0,
                "quality":"measured",
                "source":"mqtt-rain-gateway",
                "source_scheme":"measured-runtime-source",
                "source_contract_sha256":None,
                "fresh":True,"measured":True,
                "registry_bound":True,"site_bound":True,
                "thingmodel_binding":_binding("rain"),
            },
        },
        "reasons":[],
    }
    if overrides:
        payload.update(overrides)
    return payload


class FakeDriver:
    def __init__(self,readiness=None,caps=None):
        self._readiness=readiness or _readiness()
        self._caps=caps or DriverCapabilities(
            transport="windowpilot-http",
            simulated=False,
            measured_position=True,
            sensor_types=("co2","rain"),
        )
    def physical_readiness(self):
        return self._readiness
    def capabilities(self):
        return self._caps


class PhysicalTau0PreflightTests(unittest.TestCase):
    def _write_bundle(self,root,payload=None):
        path=Path(root)/"bringup.json"
        path.write_text(json.dumps(payload or _bundle()),encoding="utf-8")
        return path

    def test_valid_preflight_passes_without_motion(self):
        with tempfile.TemporaryDirectory() as d:
            receipt=validate_physical_tau0_preconditions(
                driver=FakeDriver(),
                commission_bundle=self._write_bundle(d),
            )
        self.assertEqual(receipt["status"],"PASS")
        self.assertTrue(receipt["ready_for_tau0"])
        self.assertFalse(receipt["motion_performed"])
        self.assertEqual(receipt["commissioning_identity_sha256"],"same-hardware")
        self.assertEqual(receipt["runtime_hardware_identity"]["identity_sha256"],"same-hardware")
        self.assertEqual(receipt["sensor_evidence_origin"],"runtime-measured-lineage")
        self.assertEqual(receipt["baseline_position_feedback"]["position_pct"],0.0)
        self.assertEqual(receipt["position_tolerance_pct"],1.0)

    def test_open_baseline_is_rejected_before_motion_boundary(self):
        readiness=_readiness()
        readiness["latest_position_feedback"]["position_pct"]=4.0
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,"initially closed window"):
                validate_physical_tau0_preconditions(
                    driver=FakeDriver(readiness=readiness),
                    commission_bundle=self._write_bundle(d),
                )

    def test_write_gate_must_be_ready_even_when_capture_preconditions_pass(self):
        readiness=_readiness({
            "physical_write_ready":False,
            "write_blockers":["motion semantics not verified"],
        })
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,"physical write gate is not ready"):
                validate_physical_tau0_preconditions(
                    driver=FakeDriver(readiness=readiness),
                    commission_bundle=self._write_bundle(d),
                )

    def test_runtime_identity_drift_fails_closed(self):
        identity=_identity()
        identity["identity_sha256"]="other-hardware"
        readiness=_readiness({"hardware_identity":identity})
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,"does not match current WindowPilot runtime"):
                validate_physical_tau0_preconditions(
                    driver=FakeDriver(readiness=readiness),
                    commission_bundle=self._write_bundle(d),
                )

    def test_tampered_commissioning_behavior_is_rejected(self):
        bundle=_bundle()
        bundle["commissioning"]["acceptance_policy"]["stop_hold_samples"]=1
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,"STOP hold samples must be >=2"):
                validate_physical_tau0_preconditions(
                    driver=FakeDriver(),
                    commission_bundle=self._write_bundle(d,bundle),
                )

    def test_cross_site_sensor_lineage_is_rejected(self):
        readiness=_readiness()
        readiness["sensor_evidence_lineage"]["co2_ppm"][
            "thingmodel_binding"
        ]["site_id"]="other-site"
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,"different physical site"):
                validate_physical_tau0_preconditions(
                    driver=FakeDriver(readiness=readiness),
                    commission_bundle=self._write_bundle(d),
                )

    def test_simulated_runtime_is_rejected(self):
        caps=DriverCapabilities(
            transport="simulator",
            simulated=True,
            measured_position=True,
            sensor_types=("co2","rain"),
        )
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,"still simulated"):
                validate_physical_tau0_preconditions(
                    driver=FakeDriver(caps=caps),
                    commission_bundle=self._write_bundle(d),
                )


if __name__=="__main__":
    unittest.main()
