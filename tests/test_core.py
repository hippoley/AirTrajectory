import hashlib
import json
import importlib.util
import tempfile
import unittest
from airtrajectory.trajectory import Trajectory, TrajectoryStep, TransitionAction, RewardVector
from pathlib import Path

from airtrajectory import (
    ActuatorFeedback, BuildingTopology, FastFlowField, OpeningEdge, SemanticAction,
    SensorReading, ToyMultizoneEnvironment, TransitionAction, ZoneNode,
    TrajectoryStore, exhaustive_opening_search, fork_actions, fork_window_levels, rollout,
)


from airtrajectory.physical import DriverCapabilities, PhysicalWindowEnvironment, RulePolicy, SafetyResolver, Tau0ProbePolicy, record_physical_trajectory, validate_physical_tau0
from airtrajectory.drivers import FakePhysicalWindowDriver, WindowPilotHTTPDriver
from airtrajectory.api import fork_request
from airtrajectory.telemetry import DecisionTelemetry
from airtrajectory.dataset import transition_rows, counterfactual_rows, audited_physical_transition_rows
from airtrajectory.bc import TabularBC
from airtrajectory.offline_rl import OfflineQ
from airtrajectory.commissioning import require_commissioning_behavior
from airtrajectory.sensor_lineage import build_sensor_evidence
from airtrajectory.lineage import require_hardware_site_lineage, require_hardware_thingmodel_lineage




def _windowpilot_command_response(action, target_pct=None, *, simulated=False):
    payload={
        "schema_version":"0.1",
        "receipt":"windowpilot-command-ack-v1",
        "accepted":True,
        "accepted_at":1234.0,
        "action":action,
        "target_pct":target_pct,
        "execution_backend":"simulator" if simulated else "cwds-ca01-thingmodel",
        "transport":"in-process" if simulated else "thingmodel-http",
        "simulated":bool(simulated),
        "hardware_identity_sha256":"f"*64,
        "physical_write_ready":False if simulated else True,
        "write_contract_ready":False if simulated else True,
        "motion_semantics_ready":False if simulated else True,
        "write_blockers":["execution backend is simulated"] if simulated else [],
        "evidence_kind":"synthetic-command" if simulated else "physical-command-accepted",
    }
    raw=json.dumps(
        payload,
        sort_keys=True,
        separators=(",",":"),
        ensure_ascii=False,
    ).encode("utf-8")
    ack={
        **payload,
        "command_ack_sha256":hashlib.sha256(raw).hexdigest(),
    }
    return {
        "ok":True,
        "action":action,
        "target_pct":target_pct,
        "command_ack":ack,
    }

def _hardware_identity(identity_sha):
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


def _sensor_binding(kind):
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


def _readiness_sensor_lineage(*, probe_labeled=False, timestamp=100.0):
    co2_sha="c"*64
    rain_sha="d"*64
    def entry(kind,runtime_key,contract_sha):
        binding=_sensor_binding(kind)
        if probe_labeled:
            source=f"sensor-read-probe:{contract_sha}"
            scheme="sensor-read-probe"
            source_sha=contract_sha
        else:
            source=f"runtime-{kind}-sensor"
            scheme="measured-runtime-source"
            source_sha=None
        return {
            "timestamp":float(timestamp),
            "quality":"measured",
            "source":source,
            "source_scheme":scheme,
            "source_contract_sha256":source_sha,
            "measured":True,
            "fresh":True,
            "registry_bound":True,
            "site_bound":True,
            "thingmodel_binding":binding,
        }
    return {
        "co2_ppm":entry("co2","co2_ppm",co2_sha),
        "rain":entry("rain","rain",rain_sha),
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


def _commissioning_payload():
    return {
        "excursion_pct":5.0,
        "acceptance_policy":_acceptance_policy(),
        "phases":[
            {
                "phase":"READ","commanded_pct":0.0,"measured_pct":0.0,
                "timestamp":101.0,"source":"bench-encoder","quality":"measured",
                "observed_delta_pct":0.0,"sample_count":1,
                "position_span_pct":0.0,"timestamp_advanced":True,
            },
            {
                "phase":"OPEN_5","commanded_pct":5.0,"measured_pct":5.0,
                "timestamp":102.0,"source":"bench-encoder","quality":"measured",
                "observed_delta_pct":5.0,"sample_count":1,
                "position_span_pct":0.0,"timestamp_advanced":True,
            },
            {
                "phase":"STOP","commanded_pct":5.0,"measured_pct":5.0,
                "timestamp":104.0,"source":"bench-encoder","quality":"measured",
                "observed_delta_pct":0.0,"sample_count":2,
                "position_span_pct":0.0,"timestamp_advanced":True,
            },
            {
                "phase":"CLOSE","commanded_pct":0.0,"measured_pct":0.0,
                "timestamp":105.0,"source":"bench-encoder","quality":"measured",
                "observed_delta_pct":-5.0,"sample_count":1,
                "position_span_pct":0.0,"timestamp_advanced":True,
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


def _commission_bundle(identity, preflight=None):
    payload={
        "schema_version":"0.3",
        "status":"PASS",
        "hardware_identity":identity,
        "commissioning":_commissioning_payload(),
    }
    if preflight is not None:
        payload["preflight"]=preflight
    return payload


def _commissioning_behavior():
    return require_commissioning_behavior(
        {
            "schema_version":"0.3",
            "status":"PASS",
            "commissioning":_commissioning_payload(),
        }
    )


class CoreTests(unittest.TestCase):
    def test_physical_capture_aborts_before_command_on_simulator(self):
        spec=importlib.util.spec_from_file_location(
            "capture_physical_tau0",
            Path(__file__).resolve().parents[1]/"examples"/"capture_physical_tau0.py",
        )
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        class CommissionedFake(FakePhysicalWindowDriver):
            def physical_readiness(self):
                return {
                    "capture_preconditions":True,
                    "physical_write_ready":True,
                    "latest_position_feedback":{
                        "position_pct":0.0,
                        "timestamp":99.0,
                        "measured":True,
                        "quality":"encoder-measured",
                        "source":"test-window",
                    },
                    "hardware_identity":_hardware_identity("same"),
                    "registry_bound_sensors":{"co2_ppm":True,"rain":True},
                    "site_bound_sensors":{"co2_ppm":True,"rain":True},
                    "sensor_evidence_lineage":_readiness_sensor_lineage(),
                    "reasons":[],
                }
        driver=CommissionedFake(co2_ppm=1400,measured_feedback=True)
        with tempfile.TemporaryDirectory() as d:
            bundle=Path(d)/"commission.json"
            bundle.write_text(json.dumps(_commission_bundle(
                _hardware_identity("same"),
                {
                    "receipt_sha256":"a"*64,
                    "hardware_identity_sha256":"same",
                    "gateway_contract_sha256":"b"*64,
                },
            )))
            with self.assertRaisesRegex(RuntimeError,"still simulated"):
                module.capture_physical_tau0(
                    driver=driver,
                    opening_id="w1",
                    topology_id="physical-test",
                    steps=1,
                    out=Path(d)/"tau.jsonl",
                    receipt=Path(d)/"receipt.json",
                    commission_bundle=bundle,
                )
            self.assertFalse((Path(d)/"tau.jsonl").exists())
            self.assertFalse((Path(d)/"receipt.json").exists())

    def test_physical_capture_probe_labels_are_not_audited_without_apply_receipts(self):
        spec=importlib.util.spec_from_file_location(
            "capture_physical_tau0_probe_label",
            Path(__file__).resolve().parents[1]/"examples"/"capture_physical_tau0.py",
        )
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

        identity=_hardware_identity("same-hardware")

        class ContractReal(FakePhysicalWindowDriver):
            def __init__(self):
                super().__init__(
                    co2_ppm=1400,
                    measured_feedback=True,
                    thingmodel_provenance=True,
                )
            def capabilities(self):
                return DriverCapabilities(
                    "external-test-contract",
                    False,
                    True,
                    ("co2","rain"),
                )
            def physical_readiness(self):
                return {
                    "capture_preconditions":True,
                    "physical_write_ready":True,
                    "latest_position_feedback":{
                        "position_pct":0.0,
                        "timestamp":99.0,
                        "measured":True,
                        "quality":"encoder-measured",
                        "source":"test-window",
                    },
                    "hardware_identity":identity,
                    "registry_bound_sensors":{"co2_ppm":True,"rain":True},
                    "site_bound_sensors":{"co2_ppm":True,"rain":True},
                    "sensor_evidence_lineage":_readiness_sensor_lineage(
                        probe_labeled=True,
                    ),
                    "reasons":[],
                }

        driver=ContractReal()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle=root/"commission.json"
            bundle.write_text(json.dumps(_commission_bundle(
                identity,
                {
                    "receipt_sha256":"a"*64,
                    "hardware_identity_sha256":"same-hardware",
                    "gateway_contract_sha256":"b"*64,
                },
            )))
            receipt=root/"receipt.json"
            result=module.capture_physical_tau0(
                driver=driver,
                opening_id="w1",
                topology_id="physical-test",
                steps=1,
                out=root/"tau.jsonl",
                receipt=receipt,
                commission_bundle=bundle,
            )
            persisted=json.loads((root/"tau.jsonl").read_text().strip())

        self.assertTrue(result["valid_tau0"],result["reasons"])
        self.assertEqual(
            result["tau0_capture_policy"]["policy_id"],
            "physical-tau0-probe-v1",
        )
        self.assertEqual(
            persisted["steps"][0]["executed_actions"][0]["target_pct"],
            5.0,
        )
        self.assertEqual(result["sensor_evidence_origin"],"probe-labeled")
        self.assertIsNone(result["sensor_staging_lineage"])
        self.assertTrue(result["sensor_evidence_sha256"])
        self.assertEqual(
            result["runtime_sensor_lineage"]["co2"][
                "source_contract_sha256"
            ],
            "c"*64,
        )
        self.assertEqual(driver.position,0.0)
        self.assertTrue(result["closeout"]["confirmed_closed"])
        self.assertEqual(
            result["closeout"]["feedback"]["measured_position_pct"],
            0.0,
        )

    def test_physical_capture_failure_after_motion_still_closes_window(self):
        spec=importlib.util.spec_from_file_location(
            "capture_physical_tau0_cleanup_failure",
            Path(__file__).resolve().parents[1]/"examples"/"capture_physical_tau0.py",
        )
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

        identity=_hardware_identity("same-hardware")

        class PostActionSensorFailure(FakePhysicalWindowDriver):
            def __init__(self):
                super().__init__(
                    co2_ppm=1400,
                    measured_feedback=True,
                    thingmodel_provenance=True,
                )
                self.sensor_reads=0
            def capabilities(self):
                return DriverCapabilities(
                    "external-test-contract",
                    False,
                    True,
                    ("co2","rain"),
                )
            def physical_readiness(self):
                return {
                    "capture_preconditions":True,
                    "physical_write_ready":True,
                    "latest_position_feedback":{
                        "position_pct":0.0,
                        "timestamp":99.0,
                        "measured":True,
                        "quality":"encoder-measured",
                        "source":"test-window",
                    },
                    "hardware_identity":identity,
                    "registry_bound_sensors":{"co2_ppm":True,"rain":True},
                    "site_bound_sensors":{"co2_ppm":True,"rain":True},
                    "sensor_evidence_lineage":_readiness_sensor_lineage(),
                    "reasons":[],
                }
            def read_sensors(self):
                self.sensor_reads+=1
                if self.sensor_reads>=2:
                    raise RuntimeError("injected post-action sensor failure")
                return super().read_sensors()

        driver=PostActionSensorFailure()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            bundle=root/"commission.json"
            bundle.write_text(json.dumps(_commission_bundle(
                identity,
                {
                    "receipt_sha256":"a"*64,
                    "hardware_identity_sha256":"same-hardware",
                    "gateway_contract_sha256":"b"*64,
                },
            )))
            with self.assertRaisesRegex(
                RuntimeError,
                "injected post-action sensor failure",
            ):
                module.capture_physical_tau0(
                    driver=driver,
                    opening_id="w1",
                    topology_id="physical-test",
                    steps=1,
                    out=root/"tau.jsonl",
                    receipt=root/"receipt.json",
                    commission_bundle=bundle,
                )
        self.assertEqual(driver.position,0.0)

    def test_physical_capture_rejects_legacy_pass_bundle_without_behavior_before_runtime_contact(self):
        spec=importlib.util.spec_from_file_location(
            "capture_physical_tau0_legacy_commission",
            Path(__file__).resolve().parents[1]/"examples"/"capture_physical_tau0.py",
        )
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

        class NoTouch(FakePhysicalWindowDriver):
            def __init__(self):
                super().__init__(co2_ppm=1400,measured_feedback=True)
                self.readiness_called=False
                self.commanded=False
            def physical_readiness(self):
                self.readiness_called=True
                return {
                    "capture_preconditions":True,
                    "physical_write_ready":True,
                    "latest_position_feedback":{
                        "position_pct":0.0,
                        "timestamp":99.0,
                        "measured":True,
                        "quality":"encoder-measured",
                        "source":"test-window",
                    },
                    "hardware_identity":_hardware_identity("same"),
                    "registry_bound_sensors":{"co2_ppm":True,"rain":True},
                    "site_bound_sensors":{"co2_ppm":True,"rain":True},
                    "sensor_evidence_lineage":_readiness_sensor_lineage(),
                    "reasons":[],
                }
            def set_position(self,opening_id,target_pct):
                self.commanded=True
                return super().set_position(opening_id,target_pct)

        driver=NoTouch()
        with tempfile.TemporaryDirectory() as d:
            bundle=Path(d)/"commission.json"
            bundle.write_text(json.dumps({
                "schema_version":"0.2",
                "status":"PASS",
                "hardware_identity":_hardware_identity("same"),
                "preflight":{
                    "receipt_sha256":"a"*64,
                    "hardware_identity_sha256":"same",
                    "gateway_contract_sha256":"b"*64,
                },
            }))
            with self.assertRaisesRegex(RuntimeError,"schema must be >=0.3"):
                module.capture_physical_tau0(
                    driver=driver,
                    opening_id="w1",
                    topology_id="physical-test",
                    steps=1,
                    out=Path(d)/"tau.jsonl",
                    receipt=Path(d)/"receipt.json",
                    commission_bundle=bundle,
                )
        self.assertFalse(driver.readiness_called)
        self.assertFalse(driver.commanded)

    def test_physical_capture_rejects_commissioned_runtime_identity_mismatch_before_command(self):
        spec=importlib.util.spec_from_file_location(
            "capture_physical_tau0_identity",
            Path(__file__).resolve().parents[1]/"examples"/"capture_physical_tau0.py",
        )
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        class IdentityMismatch(FakePhysicalWindowDriver):
            def __init__(self):
                super().__init__(co2_ppm=1400,measured_feedback=True)
                self.commanded=False
            def capabilities(self):
                return DriverCapabilities("verified",False,True,("co2","rain"))
            def physical_readiness(self):
                return {
                    "capture_preconditions":True,
                    "physical_write_ready":True,
                    "latest_position_feedback":{
                        "position_pct":0.0,
                        "timestamp":99.0,
                        "measured":True,
                        "quality":"encoder-measured",
                        "source":"test-window",
                    },
                    "hardware_identity":_hardware_identity("runtime-B"),
                    "registry_bound_sensors":{"co2_ppm":True,"rain":True},
                    "site_bound_sensors":{"co2_ppm":True,"rain":True},
                    "sensor_evidence_lineage":_readiness_sensor_lineage(),
                    "reasons":[],
                }
            def set_position(self,opening_id,target_pct):
                self.commanded=True
                return super().set_position(opening_id,target_pct)
        driver=IdentityMismatch()
        with tempfile.TemporaryDirectory() as d:
            bundle=Path(d)/"commission.json"
            bundle.write_text(json.dumps(_commission_bundle(
                _hardware_identity("commission-A"),
                {
                    "receipt_sha256":"c"*64,
                    "hardware_identity_sha256":"commission-A",
                    "gateway_contract_sha256":"d"*64,
                },
            )))
            with self.assertRaisesRegex(RuntimeError,"does not match"):
                module.capture_physical_tau0(
                    driver=driver,
                    opening_id="w1",
                    topology_id="physical-test",
                    steps=1,
                    out=Path(d)/"tau.jsonl",
                    receipt=Path(d)/"receipt.json",
                    commission_bundle=bundle,
                )
            self.assertFalse(driver.commanded)


    def test_physical_capture_rejects_commissioning_without_preflight_lineage(self):
        spec=importlib.util.spec_from_file_location(
            "capture_physical_tau0_preflight",
            Path(__file__).resolve().parents[1]/"examples"/"capture_physical_tau0.py",
        )
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        class NoTouch(FakePhysicalWindowDriver):
            def __init__(self):
                super().__init__(co2_ppm=1400,measured_feedback=True)
                self.readiness_called=False
                self.commanded=False
            def physical_readiness(self):
                self.readiness_called=True
                return {
                    "capture_preconditions":True,
                    "physical_write_ready":True,
                    "latest_position_feedback":{
                        "position_pct":0.0,
                        "timestamp":99.0,
                        "measured":True,
                        "quality":"encoder-measured",
                        "source":"test-window",
                    },
                    "hardware_identity":{"identity_sha256":"same"},
                    "reasons":[],
                }
            def set_position(self,opening_id,target_pct):
                self.commanded=True
                return super().set_position(opening_id,target_pct)
        driver=NoTouch()
        with tempfile.TemporaryDirectory() as d:
            bundle=Path(d)/"commission.json"
            bundle.write_text(json.dumps(_commission_bundle(
                {"identity_sha256":"same"},
            )))
            with self.assertRaisesRegex(RuntimeError,"preflight lineage"):
                module.capture_physical_tau0(
                    driver=driver,
                    opening_id="w1",
                    topology_id="physical-test",
                    steps=1,
                    out=Path(d)/"tau.jsonl",
                    receipt=Path(d)/"receipt.json",
                    commission_bundle=bundle,
                )
        self.assertFalse(driver.readiness_called)
        self.assertFalse(driver.commanded)


    def test_windowpilot_bridge_is_explicitly_simulated_and_estimated_only(self):
        state={
            "thing_model":{
                "window":{"open_pct":40},
                "sensors":{"co2_ppm":1350,"rain":False,"temp_indoor":25.0,"humidity":55,"wind_speed":2.2},
            }
        }
        calls=[]
        def request(method,path,payload):
            calls.append((method,path,payload))
            return state
        driver=WindowPilotHTTPDriver(request_json=request)
        caps=driver.capabilities()
        self.assertTrue(caps.simulated)
        self.assertFalse(caps.measured_position)
        readings=driver.read_sensors()
        self.assertEqual({r.sensor_type for r in readings},{"co2","rain","temperature","humidity","wind_speed"})
        feedback=driver.set_position("w1",40)
        self.assertIsNone(feedback.measured_position_pct)
        self.assertEqual(feedback.estimated_position_pct,40)
        self.assertIn(("POST","/api/window/open",{"target_pct":40.0}),calls)

    def test_windowpilot_bridge_can_accept_verified_measured_feedback(self):
        now=1234.0
        state={
            "thing_model":{
                "window":{"open_pct":40},
                "sensors":{"co2_ppm":1350,"rain":False,"temp_indoor":25.0,"humidity":55,"wind_speed":2.2},
                "sensor_timestamps":{"co2_ppm":now,"rain":now,"temperature":now,"humidity":now,"wind_speed":now},
            }
        }
        caps={
            "execution":{"transport":"rs485-verified","simulated":False,"measured_position":True},
            "position_feedback":{"position_pct":40.5,"timestamp":now,"measured":True,"quality":"encoder-measured"},
            "command_ack_contract":"windowpilot-command-ack-v1",
        }
        def request(method,path,payload):
            if path=="/api/capabilities": return caps
            if path=="/api/window/open":
                return _windowpilot_command_response("open",40.0)
            return state
        driver=WindowPilotHTTPDriver(request_json=request,clock_fn=lambda: now,sleep_fn=lambda _:None)
        dc=driver.capabilities()
        self.assertFalse(dc.simulated)
        self.assertTrue(dc.measured_position)
        feedback=driver.set_position("w1",40)
        self.assertEqual(feedback.measured_position_pct,40.5)
        self.assertIsNone(feedback.estimated_position_pct)
        self.assertEqual(feedback.timestamp,now)

    def test_windowpilot_rejects_pre_command_measured_feedback(self):
        clock={"now":100.0}
        calls=[]
        state={
            "thing_model":{
                "window":{"open_pct":0},
                "sensors":{"co2_ppm":1350,"rain":False},
                "sensor_timestamps":{"co2_ppm":100.0,"rain":100.0},
            }
        }
        caps={
            "execution":{"transport":"verified","simulated":False,"measured_position":True},
            "position_feedback":{"position_pct":40.0,"timestamp":99.0,"measured":True,"quality":"stale"},
            "command_ack_contract":"windowpilot-command-ack-v1",
        }
        def request(method,path,payload):
            calls.append((method,path,payload))
            if path=="/api/capabilities": return caps
            if path=="/api/window/open":
                return _windowpilot_command_response("open",40.0)
            if path=="/api/window/stop":
                return _windowpilot_command_response("stop",None)
            return state
        def now():
            value=clock["now"]
            clock["now"]+=1.0
            return value
        driver=WindowPilotHTTPDriver(
            request_json=request,clock_fn=now,sleep_fn=lambda _:None,
            feedback_timeout_s=1.0,feedback_poll_interval_s=0,
        )
        with self.assertRaisesRegex(RuntimeError,"safety STOP acknowledged"):
            driver.set_position("w1",40)
        self.assertEqual(
            calls.count(("POST","/api/window/stop",{})),
            1,
        )


    def test_windowpilot_physical_write_requires_command_ack_contract_before_post(self):
        calls=[]
        caps={
            "execution":{"transport":"verified","simulated":False,"measured_position":True},
            "position_feedback":{"position_pct":0.0,"timestamp":100.0,"measured":True},
        }
        def request(method,path,payload):
            calls.append((method,path,payload))
            if path=="/api/capabilities":
                return caps
            raise AssertionError("physical POST must not occur without command_ack contract")
        driver=WindowPilotHTTPDriver(request_json=request)
        with self.assertRaisesRegex(RuntimeError,"acknowledgement contract is unavailable"):
            driver.set_position("w1",5)
        self.assertFalse(any(method=="POST" for method,_,_ in calls))

    def test_windowpilot_rejects_tampered_physical_command_ack(self):
        caps={
            "execution":{"transport":"verified","simulated":False,"measured_position":True},
            "position_feedback":{"position_pct":5.0,"timestamp":101.0,"measured":True},
            "command_ack_contract":"windowpilot-command-ack-v1",
        }
        bad=_windowpilot_command_response("open",5.0)
        bad["command_ack"]["target_pct"]=6.0
        def request(method,path,payload):
            if path=="/api/capabilities":
                return caps
            if path=="/api/window/open":
                return bad
            return {}
        driver=WindowPilotHTTPDriver(request_json=request)
        with self.assertRaisesRegex(RuntimeError,"target mismatch|SHA-256 mismatch"):
            driver.set_position("w1",5)

    def test_windowpilot_hardware_sensor_requires_measured_provenance_for_tau0_sensors(self):
        now=100.0
        state={
            "thing_model":{
                "window":{"open_pct":40},
                "sensors":{"co2_ppm":1350,"rain":False},
                "sensor_timestamps":{"co2_ppm":now,"rain":now},
                "sensor_evidence":{
                    "co2_ppm":{"timestamp":now,"quality":"synthetic","source":"ui","measured":False},
                    "rain":{"timestamp":now,"quality":"measured","source":"rain-1","measured":True},
                },
            }
        }
        caps={"execution":{"transport":"verified","simulated":False,"measured_position":True}}
        def request(method,path,payload):
            if path=="/api/capabilities": return caps
            return state
        driver=WindowPilotHTTPDriver(request_json=request)
        with self.assertRaisesRegex(RuntimeError,"not backed by measured evidence"):
            driver.read_sensors()

    def test_windowpilot_hardware_sensor_accepts_measured_co2_rain_and_skips_optional_defaults(self):
        now=100.0
        state={
            "thing_model":{
                "window":{"open_pct":40},
                "sensors":{
                    "co2_ppm":1350,"rain":False,
                    "temp_indoor":25.0,"humidity":55.0,"wind_speed":2.0,
                },
                "sensor_timestamps":{
                    "co2_ppm":now,"rain":now,
                    "temperature":0.0,"humidity":0.0,"wind_speed":0.0,
                },
                "sensor_evidence":{
                    "co2_ppm":{
                        "timestamp":now,"quality":"measured","source":"KKCA-WD01","measured":True,
                        "thingmodel_binding":_sensor_binding("co2"),
                    },
                    "rain":{
                        "timestamp":now,"quality":"measured","source":"CWDS-CA01","measured":True,
                        "thingmodel_binding":_sensor_binding("rain"),
                    },
                },
            }
        }
        caps={"execution":{"transport":"verified","simulated":False,"measured_position":True}}
        def request(method,path,payload):
            if path=="/api/capabilities": return caps
            return state
        driver=WindowPilotHTTPDriver(request_json=request)
        readings=driver.read_sensors()
        self.assertEqual({r.sensor_type for r in readings},{"co2","rain"})
        by_type={r.sensor_type:r for r in readings}
        self.assertEqual(by_type["co2"].sensor_id,"KKCA-WD01")
        self.assertEqual(by_type["rain"].sensor_id,"CWDS-CA01")
        self.assertEqual(by_type["co2"].quality,"measured")
        self.assertEqual(by_type["co2"].provenance["property"],"airSensor.co2")
        self.assertEqual(by_type["rain"].provenance["property"],"rainSensor.rainDetect")

    def test_windowpilot_hardware_sensor_requires_source_timestamp(self):
        state={
            "thing_model":{
                "window":{"open_pct":40},
                "sensors":{"co2_ppm":1350,"rain":False},
            }
        }
        caps={"execution":{"transport":"rs485-verified","simulated":False,"measured_position":True}}
        def request(method,path,payload):
            if path=="/api/capabilities": return caps
            return state
        driver=WindowPilotHTTPDriver(request_json=request)
        with self.assertRaises(RuntimeError):
            driver.read_sensors()

    def test_windowpilot_bridge_cannot_claim_real_tau0(self):
        state={
            "thing_model":{
                "window":{"open_pct":50},
                "sensors":{"co2_ppm":1400,"rain":False},
            }
        }
        def request(method,path,payload): return state
        env=PhysicalWindowEnvironment(WindowPilotHTTPDriver(request_json=request),"w1")
        with tempfile.TemporaryDirectory() as d:
            trajectory=record_physical_trajectory(env,RulePolicy("w1"),SafetyResolver(),"windowpilot-bridge",TrajectoryStore(Path(d)/"tau.jsonl"))
        report=validate_physical_tau0(trajectory)
        self.assertFalse(report.valid_tau0)
        self.assertTrue(any("simulated" in reason for reason in report.reasons))


    def test_rollout_safety_gate_preserves_proposal_and_records_intervention(self):
        from airtrajectory.scenario import generate_chain_scenario
        from airtrajectory.environment import ScenarioMultizoneEnvironment
        scenario=generate_chain_scenario(4,rooms=2)
        scenario=type(scenario)(
            id=scenario.id,topology=scenario.topology,initial_co2=scenario.initial_co2,
            occupancy=scenario.occupancy,rain=True,outdoor_co2=scenario.outdoor_co2,
            outdoor_temp_c=scenario.outdoor_temp_c,
        )
        env=ScenarioMultizoneEnvironment(scenario,horizon_steps=1)
        exterior=[e.id for e in scenario.topology.openings.values() if e.source==scenario.topology.outside_id or e.target==scenario.topology.outside_id]
        def unsafe(_):
            return [TransitionAction(e,100) for e in exterior]
        trajectory=rollout(env,unsafe,scenario.id,"unsafe",max_steps=1,safety_resolver=SafetyResolver())
        step=trajectory.steps[0]
        self.assertTrue(any(a.target_pct==100 for a in step.proposed_actions))
        self.assertTrue(all(a.target_pct==0 for a in step.executed_actions))
        self.assertEqual(step.intervention,"RAIN_SAFE_CLOSE")
        self.assertTrue(step.info["safety_intervened"])


    def test_offline_q_never_selects_unseen_action(self):
        rows=[
          {"observation":{"co2":1400},"next_observation":{"co2":1300},"action":[{"opening_id":"W1","target_pct":50}],"reward":1.0,"terminated":False,"is_counterfactual":False},
          {"observation":{"co2":1450},"next_observation":{"co2":1350},"action":[{"opening_id":"W1","target_pct":50}],"reward":1.0,"terminated":True,"is_counterfactual":False},
          {"observation":{"co2":1400},"next_observation":{"co2":900},"action":[{"opening_id":"W1","target_pct":100}],"reward":99.0,"terminated":True,"is_counterfactual":True},
        ]
        q=OfflineQ(); self.assertEqual(q.fit(rows),2)
        self.assertEqual(q.predict({"co2":1420}),50)
        self.assertEqual(q.predict({"co2":700}),0)


    def test_bc_learns_executed_behavior_and_ignores_counterfactuals(self):
        rows=[
            {"observation":{"co2":1400,"rain":True},"action":[{"opening_id":"W1","target_pct":0}],"is_counterfactual":False},
            {"observation":{"co2":1450,"rain":True},"action":[{"opening_id":"W1","target_pct":0}],"is_counterfactual":False},
            {"observation":{"co2":1400,"rain":True},"action":[{"opening_id":"W1","target_pct":100}],"is_counterfactual":True},
        ]
        model=TabularBC(); self.assertEqual(model.fit(rows),2)
        self.assertEqual(model.predict({"co2":1420,"rain":True}),0)
        self.assertEqual(model.evaluate(rows)["accuracy"],1.0)

    def test_bc_fails_closed_outside_dataset_support(self):
        model=TabularBC()
        model.fit([{"observation":{"co2":1300},"action":[{"opening_id":"W1","target_pct":50}],"is_counterfactual":False}])
        self.assertEqual(model.predict({"co2":700}),0)

    def test_audited_physical_dataset_rejects_uncommissioned_physical_trajectory(self):
        trajectory=Trajectory(
            "physical","rule",environment_kind="physical",
            context={"reset_info":{"driver_capabilities":{"simulated":False,"measured_position":True}}}
        )
        trajectory.append(TrajectoryStep(
            0,{"co2_ppm":1400,"rain":False},[TransitionAction("w1",50)],[TransitionAction("w1",50)],
            {"co2_ppm":1300,"rain":False},RewardVector(),
            sensor_readings=[SensorReading("co2","co2",1400,"ppm",10),SensorReading("rain","rain",0,"bool",10)],
            next_sensor_readings=[SensorReading("co2","co2",1300,"ppm",12),SensorReading("rain","rain",0,"bool",12)],
            actuator_feedback=[ActuatorFeedback("w1",11,measured_position_pct=50)],
        ))
        with self.assertRaisesRegex(ValueError,"failed evidence audit"):
            list(audited_physical_transition_rows(trajectory))

    def test_dataset_uses_executed_action_and_preserves_proposal(self):
        behavior=_commissioning_behavior()
        site_lineage=require_hardware_site_lineage(
            _hardware_identity("same-hardware")
        )
        sensor_evidence=build_sensor_evidence(
            readiness={
                "sensor_evidence_lineage":_readiness_sensor_lineage()
            },
            site_lineage=site_lineage,
            commissioning_identity_sha256="same-hardware",
            commissioning_bundle_sha256="e"*64,
        )
        trajectory=Trajectory("demo","rule",context={
            "preflight_receipt_sha256":"a"*64,
            "preflight_hardware_identity_sha256":"same-hardware",
            "gateway_contract_sha256":"b"*64,
            "commissioning_behavior_witness":behavior["normalized"],
            "commissioning_behavior_sha256":behavior["sha256"],
            "sensor_evidence_origin":sensor_evidence["sensor_evidence_origin"],
            "runtime_sensor_lineage":sensor_evidence["runtime_sensor_lineage"],
            "sensor_staging_lineage":sensor_evidence["sensor_staging_lineage"],
            "sensor_evidence_sha256":sensor_evidence["sensor_evidence_sha256"],
            "thingmodel_lineage":require_hardware_thingmodel_lineage(
                _hardware_identity("same-hardware")
            ),
            "site_lineage":site_lineage,
        })
        trajectory.append(TrajectoryStep(0,{"co2":1400},[TransitionAction("W1",50)],[TransitionAction("W1",0)],{"co2":1390},RewardVector(safety=-1),intervention="RAIN_SAFE_CLOSE",info={"trace_id":"trace-1","provenance":"physical"}))
        row=list(transition_rows(trajectory))[0]
        self.assertEqual(row["proposed_actions"][0]["target_pct"],50)
        self.assertEqual(row["action"][0]["target_pct"],0)
        self.assertEqual(row["trace_id"],"trace-1")
        self.assertEqual(row["preflight_receipt_sha256"],"a"*64)
        self.assertEqual(row["preflight_hardware_identity_sha256"],"same-hardware")
        self.assertEqual(row["gateway_contract_sha256"],"b"*64)
        self.assertEqual(row["commissioning_behavior_sha256"],behavior["sha256"])
        self.assertEqual(
            row["sensor_evidence_origin"],
            "runtime-measured-lineage",
        )
        self.assertEqual(
            row["runtime_sensor_lineage"]["co2"]["source"],
            "runtime-co2-sensor",
        )
        self.assertIsNone(row["sensor_staging_lineage"])
        self.assertEqual(
            row["sensor_evidence_sha256"],
            sensor_evidence["sensor_evidence_sha256"],
        )
        self.assertEqual(
            row["commissioning_behavior_witness"]["behavior_witness"]["reality_delta_observed"],
            True,
        )
        self.assertEqual(row["thingmodel_lineage"]["thingmodel_product_model"],"CWDS-CA01")
        self.assertEqual(row["site_lineage"]["device_instance_id"],"living.window.primary")
        self.assertFalse(row["is_counterfactual"])

    def test_counterfactual_rows_are_not_behavior_samples(self):
        artifact={"request_id":"r1","trace_id":"t1","topology_id":"demo-3zone","backend":"toy","origin_kind":"post-action-snapshot","branches":[{"label":"VENT50","target_pct":50,"end_co2_ppm":900,"return":1.2,"provenance":"backend-generated"}]}
        row=list(counterfactual_rows(artifact))[0]
        self.assertTrue(row["is_counterfactual"])
        self.assertEqual(row["trace_id"],"t1")

    def topology(self):
        return BuildingTopology.from_parts(
            [ZoneNode("living", 45), ZoneNode("bedroom", 30)],
            [
                OpeningEdge("w1", "living", "OUTSIDE", "window", 1.2),
                OpeningEdge("door", "living", "bedroom", "door", 1.8),
                OpeningEdge("w2", "bedroom", "OUTSIDE", "window", 1.0),
            ],
        )

    def test_opening_reduces_co2(self):
        env = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 900})
        before, _ = env.reset()
        after, _, _, _, _ = env.step([TransitionAction("w1", 100)])
        self.assertLess(after["co2_ppm"]["living"], before["co2_ppm"]["living"])

    def test_toy_backend_respects_dt_minutes(self):
        fast = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 900}, dt_minutes=1)
        slow = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 900}, dt_minutes=5)
        fast.reset(); slow.reset()
        a=[TransitionAction("w1",100)]
        fast_after,_,_,_,_=fast.step(a)
        slow_after,_,_,_,_=slow.step(a)
        self.assertLess(slow_after["co2_ppm"]["living"], fast_after["co2_ppm"]["living"])

    def test_rollout_preserves_learning_fields(self):
        env = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 900}, horizon_steps=4)
        def policy(_):
            return [TransitionAction("w1", 50), TransitionAction("door", 100)]
        trajectory = rollout(env, policy, "two-room", "fixed", max_steps=10)
        self.assertEqual(len(trajectory.steps), 4)
        self.assertEqual(trajectory.steps[0].proposed_actions, trajectory.steps[0].executed_actions)
        self.assertIn("co2_ppm", trajectory.steps[-1].next_observation)

    def test_physical_trajectory_schema_preserves_semantic_and_feedback_layers(self):
        env = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 900}, horizon_steps=1)
        trajectory = rollout(env, lambda _: [TransitionAction("w1", 50)], "two-room", "rule-v1", max_steps=1)
        step = trajectory.steps[0]
        step.semantic_actions.append(SemanticAction("window_group", "living_windows", "VENT", 50))
        step.sensor_readings.append(SensorReading("co2-living", "co2", 1400, "ppm", 1.0, "good"))
        step.next_sensor_readings.append(SensorReading("co2-living", "co2", 1320, "ppm", 3.0, "good"))
        step.actuator_feedback.append(ActuatorFeedback("actuator-w1", 2.0, measured_position_pct=48))
        payload = trajectory.to_dict()
        self.assertEqual(payload["schema_version"], "0.3")
        self.assertEqual(payload["steps"][0]["semantic_actions"][0]["command"], "VENT")
        self.assertEqual(payload["steps"][0]["actuator_feedback"][0]["measured_position_pct"], 48)
        self.assertEqual(payload["steps"][0]["next_sensor_readings"][0]["value"], 1320)
        self.assertIsNone(payload["steps"][0]["actuator_feedback"][0]["estimated_position_pct"])

    def test_feedback_separates_measured_and_estimated_position(self):
        feedback = ActuatorFeedback("actuator-w1", 1.0, estimated_position_pct=50, quality="estimated")
        self.assertIsNone(feedback.measured_position_pct)
        self.assertEqual(feedback.estimated_position_pct, 50)

    def test_fake_physical_runtime_records_tau0_contract(self):
        driver=FakePhysicalWindowDriver(co2_ppm=1400,measured_feedback=True)
        env=PhysicalWindowEnvironment(driver,"w1")
        with tempfile.TemporaryDirectory() as d:
            store=TrajectoryStore(Path(d)/"tau0.jsonl")
            trajectory=record_physical_trajectory(env,RulePolicy("w1"),SafetyResolver(),"physical-demo",store)
            payload=json.loads((Path(d)/"tau0.jsonl").read_text().strip())
        self.assertEqual(trajectory.environment_kind,"synthetic")
        report=validate_physical_tau0(trajectory)
        self.assertFalse(report.valid_tau0)
        self.assertTrue(any("simulated" in r for r in report.reasons))
        self.assertEqual(payload["context"]["reset_info"]["driver"],"FakePhysicalWindowDriver")
        self.assertEqual(payload["steps"][0]["semantic_actions"][0]["command"],"VENT")
        self.assertEqual(payload["steps"][0]["executed_actions"][0]["target_pct"],50)
        self.assertEqual(payload["steps"][0]["actuator_feedback"][0]["measured_position_pct"],50)

    def test_missing_rain_evidence_fails_closed(self):
        class NoRain(FakePhysicalWindowDriver):
            def read_sensors(self):
                return [r for r in super().read_sensors() if r.sensor_type!="rain"]
        env=PhysicalWindowEnvironment(NoRain(co2_ppm=1500),"w1")
        observation,_=env.reset()
        decision=SafetyResolver().resolve(observation,RulePolicy("w1")(observation))
        self.assertEqual(decision.intervention,"RAIN_EVIDENCE_MISSING")
        self.assertEqual(decision.executed[0].target_pct,0)

    def test_hold_with_unknown_position_does_not_invent_close(self):
        actions=RulePolicy("w1")({"co2_ppm":1000,"rain":False,"opening_pct":None})
        self.assertEqual(actions,[])

    def test_stale_actuator_feedback_is_rejected(self):
        class StaleFeedback(FakePhysicalWindowDriver):
            def set_position(self,opening_id,target_pct):
                f=super().set_position(opening_id,target_pct)
                return ActuatorFeedback(f.actuator_id,1.0,measured_position_pct=f.measured_position_pct,estimated_position_pct=f.estimated_position_pct,quality=f.quality)
        env=PhysicalWindowEnvironment(StaleFeedback(),"w1",max_feedback_age_s=1)
        observation,_=env.reset()
        with self.assertRaisesRegex(RuntimeError,"stale actuator feedback"):
            env.step([TransitionAction("w1",50)])

    def test_tau0_audit_accepts_non_simulated_measured_contract(self):
        class ContractReal(FakePhysicalWindowDriver):
            def capabilities(self):
                return DriverCapabilities("external-test-contract",False,True,("co2","rain"))
        identity=_hardware_identity("same-hardware")
        behavior=_commissioning_behavior()
        policy=Tau0ProbePolicy(
            "w1",
            target_pct=5.0,
            minimum_reality_delta_pct=2.0,
            position_tolerance_pct=1.0,
        )
        env=PhysicalWindowEnvironment(
            ContractReal(
                co2_ppm=1400,
                measured_feedback=True,
                thingmodel_provenance=True,
            ),
            "w1",
            require_measured_feedback=True,
        )
        with tempfile.TemporaryDirectory() as d:
            trajectory=record_physical_trajectory(
                env,policy,SafetyResolver(),"physical-contract",
                TrajectoryStore(Path(d)/"tau0.jsonl"),
                steps=1,
                context_extra={
                    "tau0_capture_policy":policy.capture_policy(),
                    "position_tolerance_pct":1.0,
                    "baseline_position_feedback":{
                        "position_pct":0.0,
                        "timestamp":99.0,
                        "measured":True,
                        "quality":"encoder-measured",
                        "source":"test-window",
                    },
                    "commissioning_identity_sha256":"same-hardware",
                    "commissioning_hardware_identity":identity,
                    "runtime_hardware_identity":identity,
                    "thingmodel_lineage":require_hardware_thingmodel_lineage(identity),
                    "site_lineage":require_hardware_site_lineage(identity),
                    "preflight_receipt_sha256":"a"*64,
                    "preflight_hardware_identity_sha256":"same-hardware",
                    "gateway_contract_sha256":"b"*64,
                    "commissioning_behavior_witness":behavior["normalized"],
                    "commissioning_behavior_sha256":behavior["sha256"],
                },
            )
        report=validate_physical_tau0(trajectory)
        self.assertTrue(report.valid_tau0,report.reasons)
        self.assertEqual(trajectory.policy_id,"physical-tau0-probe-v1")
        self.assertEqual(trajectory.steps[0].executed_actions[0].target_pct,5.0)
        self.assertEqual(
            trajectory.steps[0].actuator_feedback[0].measured_position_pct,
            5.0,
        )
        rows=list(audited_physical_transition_rows(trajectory))
        self.assertEqual(len(rows),1)
        self.assertEqual(
            rows[0]["tau0_capture_policy"]["policy_id"],
            "physical-tau0-probe-v1",
        )
        self.assertEqual(
            rows[0]["baseline_position_feedback"]["position_pct"],
            0.0,
        )

    def test_tau0_audit_rejects_stuck_actuator_zero_reality_delta(self):
        class StuckReal(FakePhysicalWindowDriver):
            def capabilities(self):
                return DriverCapabilities(
                    "external-test-contract",False,True,("co2","rain")
                )
            def set_position(self,opening_id,target_pct):
                import time
                self.position=0.0
                return ActuatorFeedback(
                    opening_id,time.time(),
                    measured_position_pct=0.0,
                    quality="stuck-measured",
                )

        identity=_hardware_identity("same-hardware")
        behavior=_commissioning_behavior()
        policy=Tau0ProbePolicy(
            "w1",
            target_pct=5.0,
            minimum_reality_delta_pct=2.0,
            position_tolerance_pct=1.0,
        )
        env=PhysicalWindowEnvironment(
            StuckReal(
                co2_ppm=1400,
                measured_feedback=True,
                thingmodel_provenance=True,
            ),
            "w1",
            require_measured_feedback=True,
        )
        with tempfile.TemporaryDirectory() as d:
            trajectory=record_physical_trajectory(
                env,policy,SafetyResolver(),"physical-contract",
                TrajectoryStore(Path(d)/"tau0.jsonl"),
                steps=1,
                context_extra={
                    "tau0_capture_policy":policy.capture_policy(),
                    "position_tolerance_pct":1.0,
                    "baseline_position_feedback":{
                        "position_pct":0.0,
                        "timestamp":99.0,
                        "measured":True,
                        "quality":"encoder-measured",
                        "source":"test-window",
                    },
                    "commissioning_identity_sha256":"same-hardware",
                    "commissioning_hardware_identity":identity,
                    "runtime_hardware_identity":identity,
                    "thingmodel_lineage":require_hardware_thingmodel_lineage(identity),
                    "site_lineage":require_hardware_site_lineage(identity),
                    "preflight_receipt_sha256":"a"*64,
                    "preflight_hardware_identity_sha256":"same-hardware",
                    "gateway_contract_sha256":"b"*64,
                    "commissioning_behavior_witness":behavior["normalized"],
                    "commissioning_behavior_sha256":behavior["sha256"],
                },
            )
        report=validate_physical_tau0(trajectory)
        self.assertFalse(report.valid_tau0)
        self.assertTrue(any(
            "positive measured Reality Delta" in reason
            for reason in report.reasons
        ))
        with self.assertRaisesRegex(ValueError,"failed evidence audit"):
            list(audited_physical_transition_rows(trajectory))

    def test_tau0_audit_rejects_missing_commissioning_identity(self):
        class ContractReal(FakePhysicalWindowDriver):
            def capabilities(self):
                return DriverCapabilities("external-test-contract",False,True,("co2","rain"))
        env=PhysicalWindowEnvironment(ContractReal(co2_ppm=1400,measured_feedback=True),"w1",require_measured_feedback=True)
        with tempfile.TemporaryDirectory() as d:
            trajectory=record_physical_trajectory(
                env,RulePolicy("w1"),SafetyResolver(),"physical-contract",
                TrajectoryStore(Path(d)/"tau0.jsonl"),
            )
        report=validate_physical_tau0(trajectory)
        self.assertFalse(report.valid_tau0)
        self.assertTrue(any("commissioning hardware identity" in reason for reason in report.reasons))

    def test_tau0_records_post_action_environmental_evidence(self):
        driver=FakePhysicalWindowDriver(co2_ppm=1400,measured_feedback=True)
        env=PhysicalWindowEnvironment(driver,"w1")
        with tempfile.TemporaryDirectory() as d:
            trajectory=record_physical_trajectory(env,RulePolicy("w1"),SafetyResolver(),"post-action-evidence",TrajectoryStore(Path(d)/"tau.jsonl"))
        step=trajectory.steps[0]
        self.assertEqual({r.sensor_type for r in step.next_sensor_readings},{"co2","rain"})
        feedback_ts=max(f.timestamp for f in step.actuator_feedback)
        self.assertTrue(all(r.timestamp>feedback_ts for r in step.next_sensor_readings))

    def test_tau0_audit_rejects_missing_post_action_environmental_evidence(self):
        trajectory=Trajectory("physical-contract","policy",environment_kind="physical",context={"reset_info":{"driver_capabilities":{"simulated":False,"measured_position":True}}})
        trajectory.append(TrajectoryStep(
            0,{"co2_ppm":1400,"rain":False},[TransitionAction("w1",50)],[TransitionAction("w1",50)],
            {"co2_ppm":1300,"rain":False},RewardVector(),
            sensor_readings=[SensorReading("co2","co2",1400,"ppm",10),SensorReading("rain","rain",0,"bool",10)],
            actuator_feedback=[ActuatorFeedback("w1",11,measured_position_pct=50)],
        ))
        report=validate_physical_tau0(trajectory)
        self.assertFalse(report.valid_tau0)
        self.assertTrue(any("post-action CO2" in reason for reason in report.reasons))

    def test_rain_safety_intervention_overrides_rule_policy(self):
        driver=FakePhysicalWindowDriver(co2_ppm=1400,rain=True)
        env=PhysicalWindowEnvironment(driver,"w1")
        with tempfile.TemporaryDirectory() as d:
            trajectory=record_physical_trajectory(env,RulePolicy("w1"),SafetyResolver(),"physical-demo",TrajectoryStore(Path(d)/"tau0.jsonl"))
        step=trajectory.steps[0]
        self.assertEqual(step.proposed_actions[0].target_pct,50)
        self.assertEqual(step.executed_actions[0].target_pct,0)
        self.assertEqual(step.intervention,"RAIN_SAFE_CLOSE")

    def test_stale_sensor_blocks_physical_control(self):
        env=PhysicalWindowEnvironment(FakePhysicalWindowDriver(sensor_age_s=30),"w1",max_sensor_age_s=5)
        with self.assertRaisesRegex(RuntimeError,"stale sensor"):
            env.reset()

    def test_measured_feedback_gate_rejects_estimate_only_driver(self):
        env=PhysicalWindowEnvironment(FakePhysicalWindowDriver(measured_feedback=False),"w1",require_measured_feedback=True)
        observation,_=env.reset()
        with self.assertRaisesRegex(RuntimeError,"measured actuator position required"):
            env.step(RulePolicy("w1")(observation))

    def test_invalid_topology_rejected(self):
        with self.assertRaises(ValueError):
            BuildingTopology.from_parts(
                [ZoneNode("living", 45)],
                [OpeningEdge("broken", "living", "missing", "door", 1.0)],
            )

    def test_forks_share_origin_and_restore_source(self):
        env = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 1100}, horizon_steps=20)
        env.reset()
        env.step([TransitionAction("door", 100)])
        origin = env.snapshot()
        branches = fork_actions(
            env,
            {
                "open25": [TransitionAction("w1", 25), TransitionAction("door", 100)],
                "open75": [TransitionAction("w1", 75), TransitionAction("door", 100)],
            },
            horizon_steps=5,
        )
        self.assertEqual(env.snapshot(), origin)
        self.assertLess(
            branches["open75"].observations[-1]["co2_ppm"]["living"],
            branches["open25"].observations[-1]["co2_ppm"]["living"],
        )

    def test_canonical_window_fork_has_five_branches_and_restores_origin(self):
        env=ToyMultizoneEnvironment(self.topology(),{"living":1400,"bedroom":900},horizon_steps=40)
        env.reset(); env.step([TransitionAction("door",100),TransitionAction("w1",50)])
        origin=env.snapshot()
        branches=fork_window_levels(env,"w1",horizon_steps=5)
        self.assertEqual(list(branches),["CLOSE","VENT25","VENT50","VENT75","OPEN100"])
        self.assertEqual(env.snapshot(),origin)
        self.assertLess(branches["OPEN100"].observations[-1]["co2_ppm"]["living"],branches["CLOSE"].observations[-1]["co2_ppm"]["living"])

    def test_fork_request_reconstructs_post_action_origin(self):
        response=fork_request({
            "request_id":"tau-01","topology_id":"demo-3zone","opening_id":"W1",
            "origin":{"co2_ppm":{"living":1400,"bedroom":980,"study":840},
                      "opening_pct":{"W1":50,"W2":0,"W3":0,"D1":100,"D2":100}},
            "horizon_minutes":5,
        })
        self.assertEqual(response["request_id"],"tau-01")
        self.assertEqual([b["label"] for b in response["branches"]],["CLOSE","VENT25","VENT50","VENT75","OPEN100"])
        self.assertLess(response["branches"][-1]["end_co2_ppm"],response["branches"][0]["end_co2_ppm"])
        self.assertTrue(all("backend-generated" in b["provenance"] for b in response["branches"]))

    def test_fork_request_writes_decision_trace(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"decisions.jsonl"
            telemetry=DecisionTelemetry(path)
            response=fork_request({"request_id":"tau-traced","topology_id":"demo-3zone","opening_id":"W1",
                "origin":{"co2_ppm":{"living":1400,"bedroom":980,"study":840},"opening_pct":{"W1":50,"W2":0,"W3":0,"D1":100,"D2":100}},
                "horizon_minutes":3},telemetry=telemetry)
            trace=json.loads(path.read_text().strip())
        self.assertEqual(response["request_id"],"tau-traced")
        self.assertEqual(trace["span_name"],"counterfactual.fork")
        self.assertEqual(trace["attributes"]["request_id"],"tau-traced")
        self.assertEqual(trace["attributes"]["branch.count"],5)
        self.assertEqual(len([e for e in trace["events"] if e["name"]=="branch.result"]),5)

    def test_fork_request_rejects_unknown_topology(self):
        with self.assertRaisesRegex(ValueError,"unsupported topology_id"):
            fork_request({"topology_id":"unknown","opening_id":"W1","origin":{"co2_ppm":1400,"opening_pct":50}})

    def test_fast_field_is_deterministic_and_opening_sensitive(self):
        field = FastFlowField(self.topology())
        points = [(10.0, 20.0), (30.0, 40.0)]
        closed = field.sample(points, {"w1": 0, "door": 0, "w2": 0}, 25, 2.8)
        opened = field.sample(points, {"w1": 75, "door": 100, "w2": 25}, 25, 2.8)
        repeated = field.sample(points, {"w1": 75, "door": 100, "w2": 25}, 25, 2.8)
        self.assertEqual(opened, repeated)
        self.assertNotEqual(closed.vectors, opened.vectors)
        self.assertEqual(opened.backend, "fast-field-v1")

    def test_exhaustive_search_ranks_and_restores(self):
        env = ToyMultizoneEnvironment(self.topology(), {"living": 1400, "bedroom": 1100}, horizon_steps=20)
        env.reset()
        env.step([TransitionAction("door", 100)])
        origin = env.snapshot()
        results = exhaustive_opening_search(
            env,
            ("w1", "w2"),
            levels=(0, 50, 100),
            fixed_actions=(TransitionAction("door", 100),),
            horizon_steps=5,
            top_k=3,
        )
        self.assertEqual(len(results), 3)
        self.assertEqual(env.snapshot(), origin)
        self.assertGreaterEqual(results[0].branch.return_value, results[1].branch.return_value)
        self.assertGreaterEqual(results[1].branch.return_value, results[2].branch.return_value)
        self.assertTrue(all(result.label.startswith("SEARCH · ") for result in results))

    def test_exhaustive_search_rejects_empty_openings(self):
        env = ToyMultizoneEnvironment(self.topology())
        env.reset()
        with self.assertRaises(ValueError):
            exhaustive_opening_search(env, (), top_k=1)


if __name__ == "__main__":
    unittest.main()
