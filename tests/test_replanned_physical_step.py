import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from airtrajectory.physical import DriverCapabilities
from airtrajectory.trajectory import ActuatorFeedback
from airtrajectory.physical_origin import verify_physical_origin_receipt


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
        "origin":origin,
        "evidence_boundary":"single physical opening/zone updated from measured terminal state",
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


def command_ack(target=5.0):
    payload={
        "schema_version":"0.1",
        "receipt":"windowpilot-command-ack-v1",
        "accepted":True,
        "accepted_at":20.0,
        "action":"open",
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
    def __init__(self):
        self.commanded=[]
        self.last_command_ack=None

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
            "hardware_identity":{"identity_sha256":"c"*64},
        }

    def set_position(self,opening_id,target_pct):
        self.commanded.append((opening_id,float(target_pct)))
        self.last_command_ack=command_ack(float(target_pct))
        return ActuatorFeedback(
            actuator_id=opening_id,
            timestamp=21.0,
            measured_position_pct=float(target_pct)-0.1,
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
            )
            self.assertEqual(out["status"],"READY_FOR_EXPLICIT_EXECUTION")
            self.assertFalse(out["motion_performed"])
            self.assertEqual(driver.commanded,[])
            self.assertFalse((root/"next.json").exists())

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
                snapshot_fn=lambda **kwargs:snapshot(),
            )
            self.assertEqual(out["status"],"PASS")
            self.assertTrue(out["motion_performed"])
            self.assertTrue(out["next_origin_ready"])
            self.assertEqual(driver.commanded,[("W1",5.0)])
            next_payload=json.loads((root/"next.json").read_text(encoding="utf-8"))
            verified=verify_physical_origin_receipt(next_payload)
            self.assertEqual(verified["origin"]["co2_ppm"]["living"],1320.0)
            self.assertAlmostEqual(verified["origin"]["opening_pct"]["W1"],4.9)

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
                snapshot_fn=lambda **kwargs:snapshot(),
            )
            self.assertAlmostEqual(out["authorized_target_pct"],10.2)
            self.assertEqual(driver.commanded,[("W1",10.2)])
            self.assertEqual(
                out["intervention"],
                "REPLANNED_ACTION_BOUNDED_BY_FIELD_RAMP_LIMIT",
            )

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
                    snapshot_fn=lambda **kwargs:(_ for _ in ()).throw(
                        RuntimeError("sensor timeout")
                    ),
                )
            partial=json.loads((root/"summary.json").read_text(encoding="utf-8"))
            self.assertEqual(partial["status"],"BLOCKED_POST_ACTION_SENSORS")
            self.assertTrue(partial["motion_performed"])
            self.assertFalse(partial["next_origin_ready"])
            self.assertIn("sensor timeout",partial["error"])


if __name__=="__main__":
    unittest.main()
