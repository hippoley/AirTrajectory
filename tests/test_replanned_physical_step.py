import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from airtrajectory.physical import DriverCapabilities
from airtrajectory.physical_cycle_verify import verify_persisted_physical_cycle
from airtrajectory.trajectory import ActuatorFeedback
from airtrajectory.physical_origin import verify_physical_origin_receipt
from airtrajectory.physical_origin_lease import verify_physical_origin_execution_lease


ROOT=Path(__file__).resolve().parents[1]
EXAMPLES=ROOT/"examples"
if str(EXAMPLES) not in sys.path:
    sys.path.insert(0,str(EXAMPLES))

SPEC=importlib.util.spec_from_file_location(
    "run_replanned_physical_step",
    EXAMPLES/"run_replanned_physical_step.py",
)
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


REQUEST_IDS=[
    "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
]
COMMAND_IDS=[
    "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
]


def sha(payload):
    raw=json.dumps(
        payload,
        sort_keys=True,
        separators=(",",":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def physical_origin_payload():
    origin={
        "co2_ppm":{"living":1388.0,"bedroom":875.0,"study":800.0},
        "opening_pct":{"W1":0.2,"W2":0.1,"W3":55.0,"D1":100.0,"D2":100.0},
        "scalar_values":{"rain":0.0},
    }
    payload={
        "schema_version":"0.1",
        "source":"windowpilot-physical-reconcile-v1",
        "zone_id":"living",
        "opening_id":"W1",
        "physical_reconcile_sha256":"a"*64,
        "terminal_snapshot_sha256":"b"*64,
        "opening_hardware_identities":{"W1":"c"*64},
        "opening_observed_at":{"W1":21.0},
        "zone_observed_at":{"living":22.0},
        "rain_observed_at":22.0,
        "origin":origin,
        "evidence_boundary":"single physical opening/zone updated from measured terminal state",
    }
    return {
        **payload,
        "origin_sha256":sha(origin),
        "physical_origin_receipt_sha256":sha(payload),
    }


def recovery_origin_payload():
    origin={
        "co2_ppm":{"living":1250.0,"bedroom":875.0,"study":800.0},
        "opening_pct":{"W1":3.0,"W2":0.1,"W3":55.0,"D1":100.0,"D2":100.0},
        "scalar_values":{"rain":0.0},
    }
    snapshot={
        "opening_id":"W1",
        "zone_id":"living",
        "hardware_identity_sha256":"c"*64,
        "position_pct":3.0,
        "position_timestamp":21.0,
        "co2_ppm":1250.0,
        "co2_timestamp":22.0,
        "rain":False,
        "rain_timestamp":22.0,
        "captured_at":22.5,
        "max_observation_age_s":10.0,
    }
    payload={
        "schema_version":"0.1",
        "source":"windowpilot-recovery-physical-origin-v1",
        "parent_physical_origin_sha256":"1"*64,
        "parent_physical_origin_receipt_sha256":"2"*64,
        "recovery_execution_lease_sha256":"3"*64,
        "recovery_snapshot":snapshot,
        "recovery_snapshot_sha256":sha(snapshot),
        "opening_id":"W1",
        "zone_id":"living",
        "origin":origin,
        "opening_hardware_identities":{"W1":"c"*64},
        "opening_observed_at":{"W1":21.0},
        "zone_observed_at":{"living":22.0},
        "rain_observed_at":22.0,
        "measured_zones":["living"],
        "measured_openings":["W1"],
        "inherited_zones":["bedroom","study"],
        "inherited_openings":["D1","D2","W2","W3"],
        "whole_home_physically_measured":False,
        "recovery_observation_age_s":{"opening":1.5,"rain":0.5,"zone":0.5},
        "evidence_boundary":"synthetic recovery-origin execution contract fixture",
    }
    return {
        **payload,
        "origin_sha256":sha(origin),
        "physical_origin_receipt_sha256":sha(payload),
    }


def planner_payload(origin_receipt,target=5.0):
    origin_sha=origin_receipt["origin_sha256"]
    step_payload={
        "step_index":0,
        "origin":origin_receipt["origin"],
        "origin_sha256":origin_sha,
        "candidate_count":2,
        "selected_label":"joint-balanced-medium",
        "selected_actions":[
            {"kind":"opening","opening_id":"W1","target_pct":target},
            {"kind":"opening","opening_id":"W2","target_pct":35.0},
        ],
        "objective_score":1.2,
        "prediction_horizon_steps":3,
        "evaluation_evidence":{"origin_kind":"prj-reseed-verified"},
        "observation":origin_receipt["origin"],
        "next_origin":origin_receipt["origin"],
        "next_origin_sha256":origin_sha,
    }
    step={**step_payload,"step_sha256":sha(step_payload)}
    receipt_payload={
        "schema_version":"0.1",
        "controller":"receding-horizon-joint-v1",
        "control_steps":1,
        "prediction_horizon_steps":3,
        "initial_origin_sha256":origin_sha,
        "final_origin_sha256":origin_sha,
        "backend_capability":{
            "backend":"contamxpy",
            "physics_fidelity":"CONTAM",
            "state_reinjection_verified":True,
            "continuation_mode":"prj-section15-reseed-verified",
            "evidence_boundary":"verified contaminant-state continuation",
        },
        "steps":[step],
        "closed_loop_replanning_executed":False,
    }
    receipt={**receipt_payload,"receipt_sha256":sha(receipt_payload)}
    return {
        "marker":"REAL_CONTAM_REPLAN_FROM_PHYSICAL_ORIGIN",
        "candidate_mode":"adaptive",
        "physics_fidelity":"CONTAM",
        "evidence_level":"real-contam-transient-receding-horizon-demo",
        "engineering_truth":False,
        "field_validated":False,
        "full_restart_verified":False,
        "physical_origin_consumed":True,
        "physical_origin_evidence":{
            "source":origin_receipt["source"],
            "origin":origin_receipt["origin"],
            "origin_sha256":origin_sha,
            "receipt_sha256":origin_receipt["physical_origin_receipt_sha256"],
            "receipt_hash_field":"physical_origin_receipt_sha256",
            "whole_home_physically_measured":False,
            "measured_zones":["living"],
            "measured_openings":["W1"],
            "evidence_boundary":origin_receipt["evidence_boundary"],
        },
        "evidence_boundary":"one real-ContamX planning step starts from a verified physical-origin receipt",
        "receipt":receipt,
    }


def command_ack(
    target=5.0,
    *,
    request_id=REQUEST_IDS[0],
    command_id=COMMAND_IDS[0],
    accepted_at=20.0,
):
    payload={
        "schema_version":"0.1",
        "receipt":"windowpilot-command-ack-v2",
        "accepted":True,
        "accepted_at":accepted_at,
        "request_id":request_id,
        "command_id":command_id,
        "action":"close" if float(target)<=0 else "open",
        "target_pct":target,
        "execution_backend":"cwds-ca01-thingmodel",
        "transport":"thingmodel-http",
        "simulated":False,
        "hardware_identity_sha256":"c"*64,
        "physical_write_ready":True,
        "write_contract_ready":True,
        "motion_semantics_ready":True,
        "write_blockers":[],
        "evidence_kind":"physical-command-accepted",
    }
    return {**payload,"command_ack_sha256":sha(payload)}


def snapshot():
    payload={
        "schema_version":"0.1",
        "snapshot":"post-replanned-action-physical-v1",
        "after_timestamp":21.0,
        "co2_ppm":1320.0,
        "co2_timestamp":22.0,
        "rain":False,
        "rain_timestamp":22.0,
        "sensor_readings":[],
        "fresh_after_action":True,
    }
    return {**payload,"snapshot_sha256":sha(payload)}


class FakeDriver:
    def __init__(self, identity="c"*64):
        self.commanded=[]
        self.last_command_ack=None
        self.last_command_request_id=None
        self.identity=identity

    def capabilities(self):
        return DriverCapabilities(
            transport="thingmodel-http",
            simulated=False,
            measured_position=True,
            sensor_types=("co2","rain"),
        )

    def physical_readiness(self):
        return {
            "physical_write_ready":True,
            "write_blockers":[],
            "hardware_identity":{"identity_sha256":self.identity},
        }

    def set_position(self,opening_id,target_pct):
        self.commanded.append((opening_id,float(target_pct)))
        index=min(len(self.commanded)-1,len(REQUEST_IDS)-1)
        self.last_command_request_id=REQUEST_IDS[index]
        self.last_command_ack=command_ack(
            float(target_pct),
            request_id=self.last_command_request_id,
            command_id=COMMAND_IDS[index],
            accepted_at=20.0 + index,
        )
        if self.identity!="c"*64:
            ack_payload={
                key:value
                for key,value in self.last_command_ack.items()
                if key!="command_ack_sha256"
            }
            ack_payload["hardware_identity_sha256"]=self.identity
            self.last_command_ack={
                **ack_payload,
                "command_ack_sha256":sha(ack_payload),
            }
        return ActuatorFeedback(
            actuator_id=opening_id,
            timestamp=21.0 + len(self.commanded) - 1,
            measured_position_pct=max(0.0,float(target_pct)-0.1),
            quality="encoder-measured",
        )


class ReplannedPhysicalStepTests(unittest.TestCase):
    def _files(self,root,target=5.0):
        physical=root/"physical-origin.json"
        planner=root/"planner.json"
        physical.write_text(json.dumps(physical_origin_payload()),encoding="utf-8")
        planner.write_text(
            json.dumps(planner_payload(physical_origin_payload(),target=target)),
            encoding="utf-8",
        )
        return physical,planner

    def test_default_mode_never_moves_hardware(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            physical,planner=self._files(root)
            driver=FakeDriver()
            out=module.run_replanned_physical_step(
                driver=driver,
                physical_origin_receipt=physical,
                planner_receipt=planner,
                opening_id="W1",
                zone_id="living",
                max_delta_pct=10.0,
                summary_out=root/"summary.json",
                next_origin_out=root/"next.json",
                execute=False,
                clock_fn=lambda:23.0,
            )
            self.assertEqual(out["status"],"READY_FOR_EXPLICIT_EXECUTION")
            self.assertFalse(out["motion_performed"])
            self.assertEqual(driver.commanded,[])
            self.assertFalse((root/"next.json").exists())
            self.assertFalse((root/"physical-origin-leases").exists())

    def test_execute_requires_explicit_lease_namespace_before_motion(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            physical,planner=self._files(root)
            driver=FakeDriver()
            with self.assertRaisesRegex(
                RuntimeError,
                "requires an explicit durable lease_dir",
            ):
                module.run_replanned_physical_step(
                    driver=driver,
                    physical_origin_receipt=physical,
                    planner_receipt=planner,
                    opening_id="W1",
                    zone_id="living",
                    max_delta_pct=10.0,
                    summary_out=root/"a"/"summary.json",
                    next_origin_out=root/"a"/"next.json",
                    execute=True,
                    snapshot_fn=lambda **kwargs:snapshot(),
                    clock_fn=lambda:23.0,
                )
            self.assertEqual(driver.commanded,[])
            self.assertFalse((root/"a"/"summary.json").exists())

    def test_same_origin_cannot_replay_across_different_output_directories(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            physical,planner=self._files(root)
            lease_dir=root/"shared-leases"
            first_driver=FakeDriver()
            module.run_replanned_physical_step(
                driver=first_driver,
                physical_origin_receipt=physical,
                planner_receipt=planner,
                opening_id="W1",
                zone_id="living",
                max_delta_pct=10.0,
                summary_out=root/"run-a"/"summary.json",
                next_origin_out=root/"run-a"/"next.json",
                execute=True,
                lease_dir=lease_dir,
                snapshot_fn=lambda **kwargs:snapshot(),
                clock_fn=lambda:23.0,
            )
            second_driver=FakeDriver()
            with self.assertRaisesRegex(RuntimeError,"already been claimed"):
                module.run_replanned_physical_step(
                    driver=second_driver,
                    physical_origin_receipt=physical,
                    planner_receipt=planner,
                    opening_id="W1",
                    zone_id="living",
                    max_delta_pct=10.0,
                    summary_out=root/"run-b"/"summary.json",
                    next_origin_out=root/"run-b"/"next.json",
                    execute=True,
                    lease_dir=lease_dir,
                    snapshot_fn=lambda **kwargs:snapshot(),
                    clock_fn=lambda:23.5,
                )
            self.assertEqual(second_driver.commanded,[])
            self.assertFalse((root/"run-b"/"summary.json").exists())

    def test_recovery_origin_can_drive_next_bounded_physical_step(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            origin=recovery_origin_payload()
            physical=root/"recovery-origin.json"
            planner=root/"planner.json"
            physical.write_text(json.dumps(origin),encoding="utf-8")
            planner.write_text(
                json.dumps(planner_payload(origin,target=8.0)),
                encoding="utf-8",
            )
            driver=FakeDriver()
            out=module.run_replanned_physical_step(
                driver=driver,
                physical_origin_receipt=physical,
                planner_receipt=planner,
                opening_id="W1",
                zone_id="living",
                max_delta_pct=10.0,
                summary_out=root/"summary.json",
                next_origin_out=root/"next.json",
                execute=True,
                lease_dir=root/"physical-origin-leases",
                snapshot_fn=lambda **kwargs:snapshot(),
                clock_fn=lambda:23.0,
            )
            self.assertEqual(out["status"],"PASS")
            self.assertEqual(driver.commanded,[("W1",8.0)])
            next_payload=json.loads((root/"next.json").read_text(encoding="utf-8"))
            verified=verify_physical_origin_receipt(next_payload)
            self.assertEqual(verified["source"],"windowpilot-replanned-physical-step-v1")
            self.assertAlmostEqual(verified["origin"]["opening_pct"]["W1"],7.9)
            self.assertEqual(verified["origin"]["co2_ppm"]["living"],1320.0)

    def test_execute_emits_verified_next_physical_origin(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            physical,planner=self._files(root)
            driver=FakeDriver()
            out=module.run_replanned_physical_step(
                driver=driver,
                physical_origin_receipt=physical,
                planner_receipt=planner,
                opening_id="W1",
                zone_id="living",
                max_delta_pct=10.0,
                summary_out=root/"summary.json",
                next_origin_out=root/"next.json",
                execute=True,
                lease_dir=root/"physical-origin-leases",
                snapshot_fn=lambda **kwargs:snapshot(),
                clock_fn=lambda:23.0,
            )
            self.assertEqual(out["status"],"PASS")
            self.assertTrue(out["motion_performed"])
            self.assertTrue(out["next_origin_ready"])
            self.assertEqual(driver.commanded,[("W1",5.0)])
            next_payload=json.loads((root/"next.json").read_text(encoding="utf-8"))
            verified=verify_physical_origin_receipt(next_payload)
            self.assertEqual(verified["origin"]["co2_ppm"]["living"],1320.0)
            self.assertAlmostEqual(verified["origin"]["opening_pct"]["W1"],4.9)
            leases=list((root/"physical-origin-leases").glob("*.json"))
            self.assertEqual(len(leases),1)
            lease=verify_physical_origin_execution_lease(
                lease_path=leases[0],
                expected_origin_receipt_sha256=out[
                    "physical_origin_receipt_sha256"
                ],
            )
            self.assertEqual(lease["status"],"ADVANCED")
            self.assertEqual(
                lease["next_physical_origin_receipt_sha256"],
                next_payload["physical_origin_receipt_sha256"],
            )
            self.assertEqual(
                lease["step_summary_sha256"],
                out["replanned_physical_step_sha256"],
            )

    def test_successfully_consumed_origin_cannot_execute_twice(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            physical,planner=self._files(root)
            first_driver=FakeDriver()
            module.run_replanned_physical_step(
                driver=first_driver,
                physical_origin_receipt=physical,
                planner_receipt=planner,
                opening_id="W1",
                zone_id="living",
                max_delta_pct=10.0,
                summary_out=root/"first-summary.json",
                next_origin_out=root/"first-next.json",
                execute=True,
                lease_dir=root/"physical-origin-leases",
                snapshot_fn=lambda **kwargs:snapshot(),
                clock_fn=lambda:23.0,
            )
            second_driver=FakeDriver()
            with self.assertRaisesRegex(RuntimeError,"already been claimed"):
                module.run_replanned_physical_step(
                    driver=second_driver,
                    physical_origin_receipt=physical,
                    planner_receipt=planner,
                    opening_id="W1",
                    zone_id="living",
                    max_delta_pct=10.0,
                    summary_out=root/"second-summary.json",
                    next_origin_out=root/"second-next.json",
                    execute=True,
                    lease_dir=root/"physical-origin-leases",
                    snapshot_fn=lambda **kwargs:snapshot(),
                    clock_fn=lambda:23.5,
                )
            self.assertEqual(second_driver.commanded,[])

    def test_recovery_required_origin_cannot_be_replayed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            physical,planner=self._files(root)
            first_driver=FakeDriver()
            with self.assertRaisesRegex(RuntimeError,"fresh sensor capture failed"):
                module.run_replanned_physical_step(
                    driver=first_driver,
                    physical_origin_receipt=physical,
                    planner_receipt=planner,
                    opening_id="W1",
                    zone_id="living",
                    max_delta_pct=10.0,
                    summary_out=root/"failed-summary.json",
                    next_origin_out=root/"failed-next.json",
                    execute=True,
                    lease_dir=root/"physical-origin-leases",
                    snapshot_fn=lambda **kwargs:(_ for _ in ()).throw(
                        RuntimeError("sensor timeout")
                    ),
                    clock_fn=lambda:23.0,
                )
            second_driver=FakeDriver()
            with self.assertRaisesRegex(RuntimeError,"already been claimed"):
                module.run_replanned_physical_step(
                    driver=second_driver,
                    physical_origin_receipt=physical,
                    planner_receipt=planner,
                    opening_id="W1",
                    zone_id="living",
                    max_delta_pct=10.0,
                    summary_out=root/"retry-summary.json",
                    next_origin_out=root/"retry-next.json",
                    execute=True,
                    lease_dir=root/"physical-origin-leases",
                    snapshot_fn=lambda **kwargs:snapshot(),
                    clock_fn=lambda:23.5,
                )
            self.assertEqual(second_driver.commanded,[])

    def test_persisted_success_cycle_independently_verifies(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            physical,planner=self._files(root)
            driver=FakeDriver()
            module.run_replanned_physical_step(
                driver=driver,
                physical_origin_receipt=physical,
                planner_receipt=planner,
                opening_id="W1",
                zone_id="living",
                max_delta_pct=10.0,
                summary_out=root/"summary.json",
                next_origin_out=root/"next.json",
                execute=True,
                lease_dir=root/"physical-origin-leases",
                snapshot_fn=lambda **kwargs:snapshot(),
                clock_fn=lambda:23.0,
            )
            result=verify_persisted_physical_cycle(
                previous_origin_receipt=json.loads(
                    physical.read_text(encoding="utf-8")
                ),
                planner_payload=json.loads(
                    planner.read_text(encoding="utf-8")
                ),
                step_summary=json.loads(
                    (root/"summary.json").read_text(encoding="utf-8")
                ),
                next_origin_receipt=json.loads(
                    (root/"next.json").read_text(encoding="utf-8")
                ),
            )
            self.assertEqual(result["status"],"PASS")
            self.assertTrue(result["field_transition_contract_verified"])
            self.assertEqual(result["opening_id"],"W1")
            self.assertEqual(result["zone_id"],"living")
            self.assertEqual(len(result["physical_cycle_verification_sha256"]),64)

    def test_persisted_cycle_rejects_replayed_ack_with_other_request_id(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            physical,planner=self._files(root)
            driver=FakeDriver()
            module.run_replanned_physical_step(
                driver=driver,
                physical_origin_receipt=physical,
                planner_receipt=planner,
                opening_id="W1",
                zone_id="living",
                max_delta_pct=10.0,
                summary_out=root/"summary.json",
                next_origin_out=root/"next.json",
                execute=True,
                lease_dir=root/"physical-origin-leases",
                snapshot_fn=lambda **kwargs:snapshot(),
                clock_fn=lambda:23.0,
            )
            summary=json.loads(
                (root/"summary.json").read_text(encoding="utf-8")
            )
            replay=command_ack(
                5.0,
                request_id="eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
                command_id="ffffffff-ffff-4fff-8fff-ffffffffffff",
                accepted_at=20.0,
            )
            summary["command_ack"]=replay
            summary["command_ack_sha256"]=replay["command_ack_sha256"]
            summary_payload={
                key:value
                for key,value in summary.items()
                if key!="replanned_physical_step_sha256"
            }
            summary["replanned_physical_step_sha256"]=sha(summary_payload)
            with self.assertRaisesRegex(RuntimeError,"request_id does not match"):
                verify_persisted_physical_cycle(
                    previous_origin_receipt=json.loads(
                        physical.read_text(encoding="utf-8")
                    ),
                    planner_payload=json.loads(
                        planner.read_text(encoding="utf-8")
                    ),
                    step_summary=summary,
                    next_origin_receipt=json.loads(
                        (root/"next.json").read_text(encoding="utf-8")
                    ),
                )

    def test_hash_valid_summary_cannot_fake_origin_freshness(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            physical,planner=self._files(root)
            driver=FakeDriver()
            module.run_replanned_physical_step(
                driver=driver,
                physical_origin_receipt=physical,
                planner_receipt=planner,
                opening_id="W1",
                zone_id="living",
                max_delta_pct=10.0,
                summary_out=root/"summary.json",
                next_origin_out=root/"next.json",
                execute=True,
                lease_dir=root/"physical-origin-leases",
                snapshot_fn=lambda **kwargs:snapshot(),
                clock_fn=lambda:23.0,
            )
            summary=json.loads((root/"summary.json").read_text(encoding="utf-8"))
            summary["origin_freshness_checked_at"]=40.0
            summary_payload={
                key:value
                for key,value in summary.items()
                if key!="replanned_physical_step_sha256"
            }
            summary["replanned_physical_step_sha256"]=sha(summary_payload)
            with self.assertRaisesRegex(
                RuntimeError,
                "evidence ages do not match|exceeded max age",
            ):
                verify_persisted_physical_cycle(
                    previous_origin_receipt=json.loads(
                        physical.read_text(encoding="utf-8")
                    ),
                    planner_payload=json.loads(
                        planner.read_text(encoding="utf-8")
                    ),
                    step_summary=summary,
                    next_origin_receipt=json.loads(
                        (root/"next.json").read_text(encoding="utf-8")
                    ),
                )

    def test_hash_valid_summary_cannot_swap_origin_hardware_identity(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            physical,planner=self._files(root)
            driver=FakeDriver()
            module.run_replanned_physical_step(
                driver=driver,
                physical_origin_receipt=physical,
                planner_receipt=planner,
                opening_id="W1",
                zone_id="living",
                max_delta_pct=10.0,
                summary_out=root/"summary.json",
                next_origin_out=root/"next.json",
                execute=True,
                lease_dir=root/"physical-origin-leases",
                snapshot_fn=lambda **kwargs:snapshot(),
                clock_fn=lambda:23.0,
            )
            summary=json.loads((root/"summary.json").read_text(encoding="utf-8"))
            summary["origin_hardware_identity_sha256"]="d"*64
            summary_payload={
                key:value
                for key,value in summary.items()
                if key!="replanned_physical_step_sha256"
            }
            summary["replanned_physical_step_sha256"]=sha(summary_payload)
            with self.assertRaisesRegex(
                RuntimeError,
                "origin hardware identity does not match",
            ):
                verify_persisted_physical_cycle(
                    previous_origin_receipt=json.loads(
                        physical.read_text(encoding="utf-8")
                    ),
                    planner_payload=json.loads(
                        planner.read_text(encoding="utf-8")
                    ),
                    step_summary=summary,
                    next_origin_receipt=json.loads(
                        (root/"next.json").read_text(encoding="utf-8")
                    ),
                )

    def test_hash_valid_summary_cannot_change_persisted_authorization(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            physical,planner=self._files(root)
            driver=FakeDriver()
            module.run_replanned_physical_step(
                driver=driver,
                physical_origin_receipt=physical,
                planner_receipt=planner,
                opening_id="W1",
                zone_id="living",
                max_delta_pct=10.0,
                summary_out=root/"summary.json",
                next_origin_out=root/"next.json",
                execute=True,
                lease_dir=root/"physical-origin-leases",
                snapshot_fn=lambda **kwargs:snapshot(),
                clock_fn=lambda:23.0,
            )
            summary=json.loads(
                (root/"summary.json").read_text(encoding="utf-8")
            )
            summary["authorization"]["authorized_target_pct"]=42.0
            summary_payload={
                key:value
                for key,value in summary.items()
                if key!="replanned_physical_step_sha256"
            }
            summary["replanned_physical_step_sha256"]=sha(summary_payload)
            with self.assertRaisesRegex(
                RuntimeError,
                "persisted authorization does not match",
            ):
                verify_persisted_physical_cycle(
                    previous_origin_receipt=json.loads(
                        physical.read_text(encoding="utf-8")
                    ),
                    planner_payload=json.loads(
                        planner.read_text(encoding="utf-8")
                    ),
                    step_summary=summary,
                    next_origin_receipt=json.loads(
                        (root/"next.json").read_text(encoding="utf-8")
                    ),
                )

    def test_large_planner_jump_is_bounded_before_execution(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            physical,planner=self._files(root,target=75.0)
            driver=FakeDriver()
            out=module.run_replanned_physical_step(
                driver=driver,
                physical_origin_receipt=physical,
                planner_receipt=planner,
                opening_id="W1",
                zone_id="living",
                max_delta_pct=10.0,
                summary_out=root/"summary.json",
                next_origin_out=root/"next.json",
                execute=True,
                lease_dir=root/"physical-origin-leases",
                snapshot_fn=lambda **kwargs:snapshot(),
                clock_fn=lambda:23.0,
            )
            self.assertAlmostEqual(out["authorized_target_pct"],10.2)
            self.assertEqual(driver.commanded,[("W1",10.2)])
            self.assertEqual(
                out["intervention"],
                "REPLANNED_ACTION_BOUNDED_BY_FIELD_RAMP_LIMIT",
            )

    def test_rainy_physical_origin_forces_close_even_when_planner_opens(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            origin=physical_origin_payload()
            origin["origin"]["scalar_values"]["rain"]=1.0
            payload={
                key:value
                for key,value in origin.items()
                if key not in {"origin_sha256","physical_origin_receipt_sha256"}
            }
            origin["origin_sha256"]=sha(origin["origin"])
            origin["physical_origin_receipt_sha256"]=sha(payload)
            physical=root/"physical-origin.json"
            planner=root/"planner.json"
            physical.write_text(json.dumps(origin),encoding="utf-8")
            planner.write_text(
                json.dumps(planner_payload(origin,target=75.0)),
                encoding="utf-8",
            )
            driver=FakeDriver()
            out=module.run_replanned_physical_step(
                driver=driver,
                physical_origin_receipt=physical,
                planner_receipt=planner,
                opening_id="W1",
                zone_id="living",
                max_delta_pct=10.0,
                summary_out=root/"summary.json",
                next_origin_out=root/"next.json",
                execute=True,
                lease_dir=root/"physical-origin-leases",
                snapshot_fn=lambda **kwargs:snapshot(),
                clock_fn=lambda:23.0,
            )
            self.assertEqual(out["authorized_target_pct"],0.0)
            self.assertEqual(out["intervention"],"RAIN_SAFE_CLOSE")
            self.assertEqual(driver.commanded,[("W1",0.0)])
            next_payload=json.loads((root/"next.json").read_text(encoding="utf-8"))
            verified=verify_physical_origin_receipt(next_payload)
            self.assertEqual(verified["origin"]["opening_pct"]["W1"],0.0)

    def test_stale_physical_origin_is_rejected_before_motion(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            physical,planner=self._files(root)
            driver=FakeDriver()
            with self.assertRaisesRegex(RuntimeError,"physical origin is stale"):
                module.run_replanned_physical_step(
                    driver=driver,
                    physical_origin_receipt=physical,
                    planner_receipt=planner,
                    opening_id="W1",
                    zone_id="living",
                    max_delta_pct=10.0,
                    max_origin_age_s=5.0,
                    summary_out=root/"summary.json",
                    next_origin_out=root/"next.json",
                    execute=True,
                    lease_dir=root/"physical-origin-leases",
                    clock_fn=lambda:40.0,
                )
            self.assertEqual(driver.commanded,[])

    def test_origin_hardware_identity_mismatch_is_rejected_before_motion(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            physical,planner=self._files(root)
            driver=FakeDriver(identity="d"*64)
            with self.assertRaisesRegex(RuntimeError,"does not match.*physical-origin identity"):
                module.run_replanned_physical_step(
                    driver=driver,
                    physical_origin_receipt=physical,
                    planner_receipt=planner,
                    opening_id="W1",
                    zone_id="living",
                    max_delta_pct=10.0,
                    summary_out=root/"summary.json",
                    next_origin_out=root/"next.json",
                    execute=True,
                    lease_dir=root/"physical-origin-leases",
                    clock_fn=lambda:23.0,
                )
            self.assertEqual(driver.commanded,[])

    def test_legacy_origin_without_execution_lineage_is_readable_but_not_executable(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            origin=physical_origin_payload()
            for key in (
                "opening_hardware_identities",
                "opening_observed_at",
                "zone_observed_at",
                "rain_observed_at",
            ):
                origin.pop(key,None)
            payload={
                key:value
                for key,value in origin.items()
                if key not in {"origin_sha256","physical_origin_receipt_sha256"}
            }
            origin["physical_origin_receipt_sha256"]=sha(payload)
            physical=root/"legacy-origin.json"
            planner=root/"planner.json"
            physical.write_text(json.dumps(origin),encoding="utf-8")
            planner.write_text(json.dumps(planner_payload(origin)),encoding="utf-8")
            self.assertEqual(
                verify_physical_origin_receipt(origin)["opening_hardware_identities"],
                {},
            )
            driver=FakeDriver()
            with self.assertRaisesRegex(RuntimeError,"lacks hardware identity"):
                module.run_replanned_physical_step(
                    driver=driver,
                    physical_origin_receipt=physical,
                    planner_receipt=planner,
                    opening_id="W1",
                    zone_id="living",
                    max_delta_pct=10.0,
                    summary_out=root/"summary.json",
                    next_origin_out=root/"next.json",
                    execute=True,
                    lease_dir=root/"physical-origin-leases",
                    clock_fn=lambda:23.0,
                )
            self.assertEqual(driver.commanded,[])

    def test_sensor_failure_persists_partial_execution_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            physical,planner=self._files(root)
            driver=FakeDriver()
            with self.assertRaisesRegex(RuntimeError,"fresh sensor capture failed"):
                module.run_replanned_physical_step(
                    driver=driver,
                    physical_origin_receipt=physical,
                    planner_receipt=planner,
                    opening_id="W1",
                    zone_id="living",
                    max_delta_pct=10.0,
                    summary_out=root/"summary.json",
                    next_origin_out=root/"next.json",
                    execute=True,
                    lease_dir=root/"physical-origin-leases",
                    snapshot_fn=lambda **kwargs:(_ for _ in ()).throw(
                        RuntimeError("sensor timeout")
                    ),
                    clock_fn=lambda:23.0,
                )
            partial=json.loads((root/"summary.json").read_text(encoding="utf-8"))
            self.assertEqual(
                partial["status"],
                "SAFE_CLOSED_POST_ACTION_SENSORS_BLOCKED",
            )
            self.assertTrue(partial["motion_performed"])
            self.assertFalse(partial["next_origin_ready"])
            self.assertIn("sensor timeout",partial["sensor_failure"])
            self.assertTrue(partial["safe_closeout"]["attempted"])
            self.assertTrue(partial["safe_closeout"]["confirmed_closed"])
            self.assertEqual(driver.commanded,[("W1",5.0),("W1",0.0)])
            self.assertFalse((root/"next.json").exists())
            leases=list((root/"physical-origin-leases").glob("*.json"))
            self.assertEqual(len(leases),1)
            lease=verify_physical_origin_execution_lease(
                lease_path=leases[0],
                expected_origin_receipt_sha256=partial[
                    "physical_origin_receipt_sha256"
                ],
            )
            self.assertEqual(lease["status"],"RECOVERY_REQUIRED")
            self.assertTrue(
                lease["recovery"]["requires_new_physical_origin"]
            )


if __name__=="__main__":
    unittest.main()
