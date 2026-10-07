import hashlib
import json
import unittest

from airtrajectory.physical_replan_handoff import (
    authorize_replanned_physical_action,
    extract_replanned_physical_action,
)


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

    def test_planner_origin_mismatch_is_rejected(self):
        origin=physical_origin()
        payload=planner(origin)
        payload["receipt"]["steps"][0]["origin_sha256"]="f"*64
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
