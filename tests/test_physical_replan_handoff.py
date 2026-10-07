import hashlib
import json
import unittest

from airtrajectory.physical_origin import verify_physical_origin_receipt
from airtrajectory.physical_replan_handoff import (
    authorize_replanned_physical_action,
    build_replanned_physical_step_origin,
    extract_replanned_physical_action,
)


REQUEST_ID="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
COMMAND_ID="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def sha(payload):
    raw=json.dumps(
        payload,
        sort_keys=True,
        separators=(",",":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def physical_origin():
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
        "hardware_identity_by_opening":{"W1":"c"*64},
        "origin":origin,
        "evidence_boundary":"single physical opening/zone updated from measured terminal state",
    }
    return {
        **payload,
        "origin_sha256":sha(origin),
        "physical_origin_receipt_sha256":sha(payload),
    }


def planner(origin_receipt, *, target=75.0):
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


class PhysicalReplanHandoffTests(unittest.TestCase):
    def test_extracts_next_action_bound_to_same_physical_origin(self):
        origin=physical_origin()
        handoff=extract_replanned_physical_action(
            planner_payload=planner(origin),
            physical_origin_receipt=origin,
            opening_id="W1",
        )
        self.assertEqual(handoff["current_measured_pct"],0.2)
        self.assertEqual(handoff["planned_target_pct"],75.0)
        self.assertAlmostEqual(handoff["planned_delta_pct"],74.8)
        self.assertEqual(
            handoff["physical_origin_sha256"],
            origin["origin_sha256"],
        )
        self.assertEqual(len(handoff["replanned_action_handoff_sha256"]),64)

    def test_bounds_second_action_by_explicit_ramp_limit(self):
        origin=physical_origin()
        handoff=extract_replanned_physical_action(
            planner_payload=planner(origin),
            physical_origin_receipt=origin,
            opening_id="W1",
        )
        authorization=authorize_replanned_physical_action(
            handoff,
            max_delta_pct=10.0,
        )
        self.assertAlmostEqual(authorization["authorized_target_pct"],10.2)
        self.assertAlmostEqual(authorization["authorized_delta_pct"],10.0)
        self.assertFalse(authorization["planner_action_fully_authorized"])
        self.assertEqual(
            authorization["intervention"],
            "REPLANNED_ACTION_BOUNDED_BY_FIELD_RAMP_LIMIT",
        )

    def test_small_second_action_can_be_fully_authorized(self):
        origin=physical_origin()
        handoff=extract_replanned_physical_action(
            planner_payload=planner(origin,target=5.0),
            physical_origin_receipt=origin,
            opening_id="W1",
        )
        authorization=authorize_replanned_physical_action(
            handoff,
            max_delta_pct=10.0,
        )
        self.assertEqual(authorization["authorized_target_pct"],5.0)
        self.assertTrue(authorization["planner_action_fully_authorized"])
        self.assertIsNone(authorization["intervention"])

    def test_executed_replanned_step_emits_next_verified_physical_origin(self):
        origin=physical_origin()
        handoff=extract_replanned_physical_action(
            planner_payload=planner(origin,target=5.0),
            physical_origin_receipt=origin,
            opening_id="W1",
        )
        authorization=authorize_replanned_physical_action(
            handoff,
            max_delta_pct=10.0,
        )
        ack_payload={
            "schema_version":"0.1",
            "receipt":"windowpilot-command-ack-v2",
            "accepted":True,
            "accepted_at":20.0,
            "request_id":REQUEST_ID,
            "command_id":COMMAND_ID,
            "action":"open",
            "target_pct":5.0,
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
        ack={**ack_payload,"command_ack_sha256":sha(ack_payload)}
        snapshot_payload={
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
        snapshot={
            **snapshot_payload,
            "snapshot_sha256":sha(snapshot_payload),
        }
        next_origin=build_replanned_physical_step_origin(
            previous_physical_origin_receipt=origin,
            authorization=authorization,
            command_ack=ack,
            expected_request_id=REQUEST_ID,
            feedback={
                "actuator_id":"W1",
                "timestamp":21.0,
                "measured_position_pct":4.9,
                "estimated_position_pct":None,
                "quality":"encoder-measured",
            },
            sensor_snapshot=snapshot,
            zone_id="living",
        )
        verified=verify_physical_origin_receipt(next_origin)
        self.assertEqual(verified["origin"]["co2_ppm"]["living"],1320.0)
        self.assertEqual(verified["origin"]["opening_pct"]["W1"],4.9)
        self.assertEqual(verified["origin_sha256"],next_origin["origin_sha256"])
        self.assertIn("living",verified["measured_zones"])
        self.assertIn("W1",verified["measured_openings"])

    def test_replanned_step_rejects_ack_from_different_hardware(self):
        origin=physical_origin()
        handoff=extract_replanned_physical_action(
            planner_payload=planner(origin,target=5.0),
            physical_origin_receipt=origin,
            opening_id="W1",
        )
        authorization=authorize_replanned_physical_action(
            handoff,
            max_delta_pct=10.0,
        )
        ack_payload={
            "schema_version":"0.1",
            "receipt":"windowpilot-command-ack-v2",
            "accepted":True,
            "accepted_at":20.0,
            "request_id":REQUEST_ID,
            "command_id":COMMAND_ID,
            "action":"open",
            "target_pct":5.0,
            "execution_backend":"cwds-ca01-thingmodel",
            "transport":"thingmodel-http",
            "simulated":False,
            "hardware_identity_sha256":"d"*64,
            "physical_write_ready":True,
            "write_contract_ready":True,
            "motion_semantics_ready":True,
            "write_blockers":[],
            "evidence_kind":"physical-command-accepted",
        }
        ack={**ack_payload,"command_ack_sha256":sha(ack_payload)}
        snapshot_payload={
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
        snapshot={**snapshot_payload,"snapshot_sha256":sha(snapshot_payload)}
        with self.assertRaisesRegex(RuntimeError,"differs from previous physical origin"):
            build_replanned_physical_step_origin(
                previous_physical_origin_receipt=origin,
                authorization=authorization,
                command_ack=ack,
                expected_request_id=REQUEST_ID,
                feedback={
                    "actuator_id":"W1",
                    "timestamp":21.0,
                    "measured_position_pct":4.9,
                    "estimated_position_pct":None,
                    "quality":"encoder-measured",
                },
                sensor_snapshot=snapshot,
                zone_id="living",
            )

    def test_replanned_step_rejects_replayed_ack_from_other_request(self):
        origin=physical_origin()
        handoff=extract_replanned_physical_action(
            planner_payload=planner(origin,target=5.0),
            physical_origin_receipt=origin,
            opening_id="W1",
        )
        authorization=authorize_replanned_physical_action(
            handoff,
            max_delta_pct=10.0,
        )
        ack_payload={
            "schema_version":"0.1",
            "receipt":"windowpilot-command-ack-v2",
            "accepted":True,
            "accepted_at":20.0,
            "request_id":"cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            "command_id":COMMAND_ID,
            "action":"open",
            "target_pct":5.0,
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
        ack={**ack_payload,"command_ack_sha256":sha(ack_payload)}
        snapshot_payload={
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
        snapshot={**snapshot_payload,"snapshot_sha256":sha(snapshot_payload)}
        with self.assertRaisesRegex(RuntimeError,"request_id does not match"):
            build_replanned_physical_step_origin(
                previous_physical_origin_receipt=origin,
                authorization=authorization,
                command_ack=ack,
                expected_request_id=REQUEST_ID,
                feedback={
                    "actuator_id":"W1",
                    "timestamp":21.0,
                    "measured_position_pct":4.9,
                    "estimated_position_pct":None,
                    "quality":"encoder-measured",
                },
                sensor_snapshot=snapshot,
                zone_id="living",
            )

    def test_replanned_step_rejects_feedback_before_ack(self):
        origin=physical_origin()
        handoff=extract_replanned_physical_action(
            planner_payload=planner(origin,target=5.0),
            physical_origin_receipt=origin,
            opening_id="W1",
        )
        authorization=authorize_replanned_physical_action(
            handoff,
            max_delta_pct=10.0,
        )
        ack_payload={
            "schema_version":"0.1",
            "receipt":"windowpilot-command-ack-v2",
            "accepted":True,
            "accepted_at":21.5,
            "request_id":REQUEST_ID,
            "command_id":COMMAND_ID,
            "action":"open",
            "target_pct":5.0,
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
        ack={**ack_payload,"command_ack_sha256":sha(ack_payload)}
        snapshot_payload={
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
        snapshot={**snapshot_payload,"snapshot_sha256":sha(snapshot_payload)}
        with self.assertRaisesRegex(RuntimeError,"predates command acknowledgement"):
            build_replanned_physical_step_origin(
                previous_physical_origin_receipt=origin,
                authorization=authorization,
                command_ack=ack,
                expected_request_id=REQUEST_ID,
                feedback={
                    "actuator_id":"W1",
                    "timestamp":21.0,
                    "measured_position_pct":4.9,
                    "estimated_position_pct":None,
                    "quality":"encoder-measured",
                },
                sensor_snapshot=snapshot,
                zone_id="living",
            )

    def test_replanned_step_rejects_stale_sensor_snapshot(self):
        origin=physical_origin()
        handoff=extract_replanned_physical_action(
            planner_payload=planner(origin,target=5.0),
            physical_origin_receipt=origin,
            opening_id="W1",
        )
        authorization=authorize_replanned_physical_action(
            handoff,
            max_delta_pct=10.0,
        )
        ack_payload={
            "schema_version":"0.1",
            "receipt":"windowpilot-command-ack-v2",
            "accepted":True,
            "accepted_at":20.0,
            "request_id":REQUEST_ID,
            "command_id":COMMAND_ID,
            "action":"open",
            "target_pct":5.0,
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
        ack={**ack_payload,"command_ack_sha256":sha(ack_payload)}
        snapshot_payload={
            "schema_version":"0.1",
            "snapshot":"post-replanned-action-physical-v1",
            "after_timestamp":21.0,
            "co2_ppm":1320.0,
            "co2_timestamp":20.0,
            "rain":False,
            "rain_timestamp":22.0,
            "sensor_readings":[],
            "fresh_after_action":True,
        }
        snapshot={
            **snapshot_payload,
            "snapshot_sha256":sha(snapshot_payload),
        }
        with self.assertRaisesRegex(RuntimeError,"not newer than actuator feedback"):
            build_replanned_physical_step_origin(
                previous_physical_origin_receipt=origin,
                authorization=authorization,
                command_ack=ack,
                expected_request_id=REQUEST_ID,
                feedback={
                    "actuator_id":"W1",
                    "timestamp":21.0,
                    "measured_position_pct":4.9,
                    "estimated_position_pct":None,
                    "quality":"encoder-measured",
                },
                sensor_snapshot=snapshot,
                zone_id="living",
            )

    def test_rain_overrides_replanned_open_to_safe_close(self):
        origin=physical_origin()
        origin_payload={
            **origin,
            "origin":{
                **origin["origin"],
                "scalar_values":{"rain":1.0},
            },
        }
        raw_payload={
            key:value
            for key,value in origin_payload.items()
            if key not in {"origin_sha256","physical_origin_receipt_sha256"}
        }
        origin_payload["origin_sha256"]=sha(origin_payload["origin"])
        origin_payload["physical_origin_receipt_sha256"]=sha(raw_payload)
        plan=planner(origin_payload,target=75.0)
        handoff=extract_replanned_physical_action(
            planner_payload=plan,
            physical_origin_receipt=origin_payload,
            opening_id="W1",
        )
        authorization=authorize_replanned_physical_action(
            handoff,
            max_delta_pct=10.0,
        )
        self.assertTrue(handoff["current_rain"])
        self.assertEqual(authorization["authorized_target_pct"],0.0)
        self.assertEqual(authorization["intervention"],"RAIN_SAFE_CLOSE")
        self.assertFalse(authorization["planner_action_fully_authorized"])

    def test_tampered_planner_step_without_outer_rehash_is_rejected(self):
        origin=physical_origin()
        payload=planner(origin)
        payload["receipt"]["steps"][0]["objective_score"]=999.0
        with self.assertRaisesRegex(
            RuntimeError,
            "planner closed-loop receipt SHA-256 mismatch",
        ):
            extract_replanned_physical_action(
                planner_payload=payload,
                physical_origin_receipt=origin,
                opening_id="W1",
            )

    def test_tampered_planner_step_hash_is_rejected_after_outer_rehash(self):
        origin=physical_origin()
        payload=planner(origin)
        receipt=payload["receipt"]
        receipt["steps"][0]["objective_score"]=999.0
        receipt_payload={
            key:value
            for key,value in receipt.items()
            if key!="receipt_sha256"
        }
        receipt["receipt_sha256"]=sha(receipt_payload)
        with self.assertRaisesRegex(
            RuntimeError,
            "planner closed-loop step SHA-256 mismatch",
        ):
            extract_replanned_physical_action(
                planner_payload=payload,
                physical_origin_receipt=origin,
                opening_id="W1",
            )

    def test_tampered_planner_receipt_hash_is_rejected(self):
        origin=physical_origin()
        payload=planner(origin)
        payload["receipt"]["prediction_horizon_steps"]=99
        with self.assertRaisesRegex(RuntimeError,"planner closed-loop receipt SHA-256 mismatch"):
            extract_replanned_physical_action(
                planner_payload=payload,
                physical_origin_receipt=origin,
                opening_id="W1",
            )

    def test_planner_origin_mismatch_is_rejected_even_with_valid_hashes(self):
        origin=physical_origin()
        payload=planner(origin)
        receipt=payload["receipt"]
        step=receipt["steps"][0]
        step["origin_sha256"]="f"*64
        step_payload={
            key:value
            for key,value in step.items()
            if key!="step_sha256"
        }
        step["step_sha256"]=sha(step_payload)
        receipt_payload={
            key:value
            for key,value in receipt.items()
            if key!="receipt_sha256"
        }
        receipt["receipt_sha256"]=sha(receipt_payload)
        with self.assertRaisesRegex(RuntimeError,"step origin"):
            extract_replanned_physical_action(
                planner_payload=payload,
                physical_origin_receipt=origin,
                opening_id="W1",
            )

    def test_missing_exact_opening_action_is_rejected(self):
        origin=physical_origin()
        with self.assertRaisesRegex(RuntimeError,"exactly one"):
            extract_replanned_physical_action(
                planner_payload=planner(origin),
                physical_origin_receipt=origin,
                opening_id="W9",
            )

    def test_tampered_handoff_is_rejected_before_authorization(self):
        origin=physical_origin()
        handoff=extract_replanned_physical_action(
            planner_payload=planner(origin),
            physical_origin_receipt=origin,
            opening_id="W1",
        )
        handoff["planned_target_pct"]=5.0
        with self.assertRaisesRegex(RuntimeError,"SHA-256 mismatch"):
            authorize_replanned_physical_action(
                handoff,
                max_delta_pct=10.0,
            )


if __name__=="__main__":
    unittest.main()
