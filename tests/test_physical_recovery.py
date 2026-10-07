import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from airtrajectory.physical import DriverCapabilities
from airtrajectory.physical_origin import verify_physical_origin_receipt
from airtrajectory.physical_origin_lease import (
    claim_physical_origin_execution,
    finalize_physical_origin_execution,
    verify_physical_origin_execution_lease,
)
from airtrajectory.trajectory import ActuatorFeedback


ROOT=Path(__file__).resolve().parents[1]
EXAMPLES=ROOT/"examples"
if str(EXAMPLES) not in sys.path:
    sys.path.insert(0,str(EXAMPLES))

SPEC=importlib.util.spec_from_file_location(
    "recover_physical_origin",
    EXAMPLES/"recover_physical_origin.py",
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


def previous_origin():
    origin={
        "co2_ppm":{"living":1388.0,"bedroom":875.0},
        "opening_pct":{"W1":5.0,"W2":0.0},
        "scalar_values":{"rain":0.0},
    }
    payload={
        "schema_version":"0.1",
        "source":"windowpilot-replanned-physical-step-v1",
        "origin":origin,
        "parent_physical_origin_sha256":"1"*64,
        "parent_physical_origin_receipt_sha256":"2"*64,
        "replanned_action_authorization_sha256":"3"*64,
        "command_ack_sha256":"4"*64,
        "sensor_snapshot_sha256":"5"*64,
        "command_request_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "command_id":"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "command_accepted_at":18.0,
        "opening_id":"W1",
        "zone_id":"living",
        "measured_position_pct":5.0,
        "actuator_feedback_timestamp":19.0,
        "opening_hardware_identities":{"W1":"c"*64},
        "opening_observed_at":{"W1":19.0},
        "zone_observed_at":{"living":20.0},
        "rain_observed_at":20.0,
        "current_step_measured_zones":["living"],
        "current_step_measured_openings":["W1"],
        "measured_zones":["living"],
        "measured_openings":["W1"],
        "inherited_zones":["bedroom"],
        "inherited_openings":["W2"],
        "whole_home_measurement_skew_s":None,
        "whole_home_measurement_max_skew_s":10.0,
        "whole_home_physically_measured":False,
        "evidence_boundary":"fixture",
    }
    return {
        **payload,
        "origin_sha256":sha(origin),
        "physical_origin_receipt_sha256":sha(payload),
    }


def sensor_snapshot(after=25.0):
    payload={
        "schema_version":"0.1",
        "snapshot":"post-replanned-action-physical-v1",
        "after_timestamp":after,
        "co2_ppm":1200.0,
        "co2_timestamp":after+1.0,
        "rain":False,
        "rain_timestamp":after+1.0,
        "sensor_readings":[],
        "fresh_after_action":True,
    }
    return {**payload,"snapshot_sha256":sha(payload)}


class RecoveryDriver:
    def __init__(self, *, position=0.0, timestamp=25.0, identity="c"*64):
        self.position=float(position)
        self.timestamp=float(timestamp)
        self.identity=identity
        self.commanded=[]
        self.last_command_ack=None
        self.last_command_request_id=None

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
            "latest_position_feedback":{
                "position_pct":self.position,
                "timestamp":self.timestamp,
                "measured":True,
                "quality":"encoder-measured",
            },
        }

    def set_position(self, opening_id, target_pct):
        self.commanded.append((opening_id,float(target_pct)))
        self.position=float(target_pct)
        self.timestamp+=1.0
        self.last_command_request_id="cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        ack_payload={
            "schema_version":"0.1",
            "receipt":"windowpilot-command-ack-v2",
            "accepted":True,
            "accepted_at":self.timestamp-0.5,
            "request_id":self.last_command_request_id,
            "command_id":"dddddddd-dddd-4ddd-8ddd-dddddddddddd",
            "action":"close",
            "target_pct":0.0,
            "execution_backend":"cwds-ca01-thingmodel",
            "transport":"thingmodel-http",
            "simulated":False,
            "hardware_identity_sha256":self.identity,
            "physical_write_ready":True,
            "write_contract_ready":True,
            "motion_semantics_ready":True,
            "write_blockers":[],
            "evidence_kind":"physical-command-accepted",
        }
        self.last_command_ack={
            **ack_payload,
            "command_ack_sha256":sha(ack_payload),
        }
        return ActuatorFeedback(
            actuator_id=opening_id,
            timestamp=self.timestamp,
            measured_position_pct=self.position,
            quality="encoder-measured",
        )


class PhysicalRecoveryTests(unittest.TestCase):
    def _artifacts(self, root):
        origin=previous_origin()
        origin_path=root/"previous-origin.json"
        origin_path.write_text(json.dumps(origin),encoding="utf-8")
        claim=claim_physical_origin_execution(
            lease_dir=root/"leases",
            origin_receipt_sha256=origin["physical_origin_receipt_sha256"],
            origin_sha256=origin["origin_sha256"],
            planner_receipt_sha256="6"*64,
            planner_step_sha256="7"*64,
            opening_id="W1",
            zone_id="living",
            claimed_at=21.0,
        )
        finalize_physical_origin_execution(
            lease_path=claim["lease_path"],
            status="RECOVERY_REQUIRED",
            finalized_at=22.0,
            recovery={
                "error":"sensor timeout",
                "requires_new_physical_origin":True,
            },
        )
        return origin_path,Path(claim["lease_path"])

    def test_already_closed_recovers_without_motion(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            origin_path,lease_path=self._artifacts(root)
            driver=RecoveryDriver(position=0.0,timestamp=25.0)
            result=module.recover_physical_origin(
                driver=driver,
                previous_origin_receipt=origin_path,
                lease_path=lease_path,
                recovery_origin_out=root/"recovered.json",
                summary_out=root/"summary.json",
                execute_closeout=False,
                snapshot_fn=lambda **kwargs:sensor_snapshot(25.0),
                clock_fn=lambda:25.5,
            )
            self.assertEqual(result["status"],"PASS")
            self.assertFalse(result["motion_performed"])
            self.assertEqual(driver.commanded,[])
            recovered=json.loads((root/"recovered.json").read_text())
            verified=verify_physical_origin_receipt(recovered)
            self.assertEqual(verified["measured_zones"],["living"])
            self.assertEqual(verified["measured_openings"],["W1"])
            self.assertEqual(verified["inherited_zones"],["bedroom"])
            self.assertEqual(verified["inherited_openings"],["W2"])
            self.assertEqual(verified["origin"]["opening_pct"]["W1"],0.0)
            self.assertEqual(verified["origin"]["co2_ppm"]["living"],1200.0)
            lease=verify_physical_origin_execution_lease(
                lease_path=lease_path,
                expected_origin_receipt_sha256=previous_origin()[
                    "physical_origin_receipt_sha256"
                ],
            )
            self.assertEqual(lease["status"],"RECOVERED")
            self.assertEqual(
                lease["recovery_origin_receipt_sha256"],
                recovered["physical_origin_receipt_sha256"],
            )

    def test_open_window_requires_explicit_closeout_and_does_not_mutate_lease(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            origin_path,lease_path=self._artifacts(root)
            driver=RecoveryDriver(position=5.0,timestamp=25.0)
            result=module.recover_physical_origin(
                driver=driver,
                previous_origin_receipt=origin_path,
                lease_path=lease_path,
                recovery_origin_out=root/"recovered.json",
                summary_out=root/"summary.json",
                execute_closeout=False,
                clock_fn=lambda:25.5,
            )
            self.assertEqual(result["status"],"CLOSEOUT_REQUIRED")
            self.assertEqual(driver.commanded,[])
            self.assertFalse((root/"recovered.json").exists())
            lease=verify_physical_origin_execution_lease(
                lease_path=lease_path
            )
            self.assertEqual(lease["status"],"RECOVERY_REQUIRED")

    def test_explicit_closeout_then_fresh_sensors_recovers_origin(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            origin_path,lease_path=self._artifacts(root)
            driver=RecoveryDriver(position=5.0,timestamp=25.0)
            result=module.recover_physical_origin(
                driver=driver,
                previous_origin_receipt=origin_path,
                lease_path=lease_path,
                recovery_origin_out=root/"recovered.json",
                summary_out=root/"summary.json",
                execute_closeout=True,
                snapshot_fn=lambda **kwargs:sensor_snapshot(26.0),
                clock_fn=lambda:25.5,
            )
            self.assertTrue(result["motion_performed"])
            self.assertEqual(driver.commanded,[("W1",0.0)])
            recovered=json.loads((root/"recovered.json").read_text())
            self.assertEqual(recovered["closeout_request_id"],driver.last_command_request_id)
            self.assertTrue(recovered["closeout_command_ack_sha256"])
            self.assertEqual(
                verify_physical_origin_execution_lease(
                    lease_path=lease_path
                )["status"],
                "RECOVERED",
            )

    def test_identity_mismatch_rejected_before_motion(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            origin_path,lease_path=self._artifacts(root)
            driver=RecoveryDriver(position=5.0,timestamp=25.0,identity="d"*64)
            with self.assertRaisesRegex(RuntimeError,"identity does not match"):
                module.recover_physical_origin(
                    driver=driver,
                    previous_origin_receipt=origin_path,
                    lease_path=lease_path,
                    recovery_origin_out=root/"recovered.json",
                    summary_out=root/"summary.json",
                    execute_closeout=True,
                    clock_fn=lambda:25.5,
                )
            self.assertEqual(driver.commanded,[])
            self.assertEqual(
                verify_physical_origin_execution_lease(
                    lease_path=lease_path
                )["status"],
                "RECOVERY_REQUIRED",
            )

    def test_stale_position_rejected_before_motion(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            origin_path,lease_path=self._artifacts(root)
            driver=RecoveryDriver(position=5.0,timestamp=10.0)
            with self.assertRaisesRegex(RuntimeError,"position feedback is stale"):
                module.recover_physical_origin(
                    driver=driver,
                    previous_origin_receipt=origin_path,
                    lease_path=lease_path,
                    recovery_origin_out=root/"recovered.json",
                    summary_out=root/"summary.json",
                    execute_closeout=True,
                    max_position_age_s=10.0,
                    clock_fn=lambda:25.5,
                )
            self.assertEqual(driver.commanded,[])

    def test_recovered_parent_origin_remains_single_use(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            origin_path,lease_path=self._artifacts(root)
            driver=RecoveryDriver(position=0.0,timestamp=25.0)
            module.recover_physical_origin(
                driver=driver,
                previous_origin_receipt=origin_path,
                lease_path=lease_path,
                recovery_origin_out=root/"recovered.json",
                summary_out=root/"summary.json",
                snapshot_fn=lambda **kwargs:sensor_snapshot(25.0),
                clock_fn=lambda:25.5,
            )
            origin=previous_origin()
            with self.assertRaisesRegex(RuntimeError,"already been claimed"):
                claim_physical_origin_execution(
                    lease_dir=root/"leases",
                    origin_receipt_sha256=origin[
                        "physical_origin_receipt_sha256"
                    ],
                    origin_sha256=origin["origin_sha256"],
                    planner_receipt_sha256="6"*64,
                    planner_step_sha256="7"*64,
                    opening_id="W1",
                    zone_id="living",
                    claimed_at=30.0,
                )


if __name__=="__main__":
    unittest.main()
