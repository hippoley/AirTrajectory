"""One-command, fail-closed field handoff for AirTrajectory + WindowPilot.

Default mode is read-only. Real actuator motion requires --execute.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from airtrajectory.drivers import WindowPilotHTTPDriver
from airtrajectory.evidence import verify_physical_tau0_artifacts
from airtrajectory.physical_handoff import extract_closed_loop_opening_action
from airtrajectory.physical_origin import physical_next_origin_from_reconcile

from check_physical_tau0_preflight import check_physical_tau0_preflight
from capture_physical_tau0 import capture_physical_tau0


def _sha256_payload(payload) -> str:
    raw=json.dumps(
        payload,
        sort_keys=True,
        separators=(",",":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def run_field_handoff(
    *,
    driver,
    commission_bundle,
    opening_id,
    topology_id,
    preflight_receipt,
    trajectory_out,
    tau0_receipt,
    summary_receipt,
    sensor_apply_receipts=None,
    execute=False,
    closed_loop_receipt=None,
    closed_loop_step_index=0,
    predicted_zone_id=None,
    current_origin=None,
    physical_origin_out=None,
):
    sensor_apply_receipts=list(sensor_apply_receipts or [])

    preflight=check_physical_tau0_preflight(
        driver=driver,
        commission_bundle=commission_bundle,
        receipt=preflight_receipt,
        sensor_apply_receipts=sensor_apply_receipts,
    )

    base={
        "schema_version":"0.1",
        "workflow":"airtrajectory-windowpilot-field-handoff-v1",
        "mode":"execute" if execute else "read-only",
        "windowpilot_preflight_passed":True,
        "preflight_receipt":str(preflight_receipt),
        "commission_bundle":str(commission_bundle),
        "opening_id":str(opening_id),
        "topology_id":str(topology_id),
    }

    if not execute:
        payload={
            **base,
            "status":"READY_FOR_EXPLICIT_EXECUTION",
            "motion_performed":False,
            "next_command":"rerun with --execute after human review of the preflight receipt",
            "tau0_captured":False,
            "artifacts_verified":False,
            "physical_origin_ready":False,
        }
        final={**payload,"field_handoff_sha256":_sha256_payload(payload)}
        path=Path(summary_receipt)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding="utf-8")
        return final

    planner_handoff=None
    closed_loop_path=None
    if closed_loop_receipt is not None:
        closed_loop_path=Path(closed_loop_receipt)
        closed_loop_payload=json.loads(closed_loop_path.read_text(encoding="utf-8"))
        planner_handoff=extract_closed_loop_opening_action(
            closed_loop_payload,
            step_index=int(closed_loop_step_index),
            opening_id=str(opening_id),
        )

    if (current_origin is None) != (physical_origin_out is None):
        raise RuntimeError(
            "current_origin and physical_origin_out must be supplied together"
        )
    if current_origin is not None and planner_handoff is None:
        raise RuntimeError(
            "physical next-origin generation requires a closed-loop planner receipt"
        )
    if planner_handoff is not None and current_origin is not None and not predicted_zone_id:
        raise RuntimeError(
            "physical next-origin generation requires predicted_zone_id"
        )

    capture=capture_physical_tau0(
        driver=driver,
        opening_id=opening_id,
        topology_id=topology_id,
        steps=1,
        out=trajectory_out,
        receipt=tau0_receipt,
        commission_bundle=commission_bundle,
        sensor_apply_receipts=sensor_apply_receipts,
        planner_handoff=planner_handoff,
        predicted_zone_id=predicted_zone_id,
    )

    verification=verify_physical_tau0_artifacts(
        trajectory_path=trajectory_out,
        receipt_path=tau0_receipt,
        commission_bundle_path=commission_bundle,
    )
    if verification.get("valid_artifacts") is not True:
        raise RuntimeError(
            "persisted physical artifacts failed independent verification: "
            +"; ".join(verification.get("reasons") or [])
        )

    physical_origin_receipt=None
    if current_origin is not None:
        reconcile=capture.get("physical_reconcile")
        if not isinstance(reconcile,dict):
            raise RuntimeError(
                "capture did not produce physical reconcile for next-origin generation"
            )
        current_payload=json.loads(Path(current_origin).read_text(encoding="utf-8"))
        physical_origin_receipt=physical_next_origin_from_reconcile(
            current_origin=current_payload,
            reconcile=reconcile,
            zone_id=str(predicted_zone_id),
        )
        out_path=Path(physical_origin_out)
        out_path.parent.mkdir(parents=True,exist_ok=True)
        out_path.write_text(
            json.dumps(physical_origin_receipt,ensure_ascii=False,indent=2),
            encoding="utf-8",
        )

    payload={
        **base,
        "status":"PASS",
        "motion_performed":True,
        "tau0_captured":True,
        "tau0_valid":bool(capture.get("valid_tau0")),
        "sim_to_physical_handoff_verified":bool(
            capture.get("sim_to_physical_handoff_verified")
        ),
        "artifacts_verified":True,
        "trajectory":str(trajectory_out),
        "trajectory_sha256":capture.get("trajectory_sha256"),
        "tau0_receipt":str(tau0_receipt),
        "verified_tau0_receipt_sha256":verification.get("receipt_sha256"),
        "commissioning_identity_sha256":verification.get(
            "commissioning_identity_sha256"
        ),
        "runtime_hardware_identity_sha256":verification.get(
            "runtime_hardware_identity_sha256"
        ),
        "closed_loop_receipt":str(closed_loop_path) if closed_loop_path else None,
        "planner_handoff_sha256":(
            planner_handoff.get("planner_handoff_sha256")
            if isinstance(planner_handoff,dict) else None
        ),
        "command_ack_sha256":(
            (capture.get("physical_reconcile") or {}).get("command_ack_sha256")
        ),
        "physical_reconcile_sha256":(
            (capture.get("physical_reconcile") or {}).get(
                "physical_reconcile_sha256"
            )
        ),
        "physical_next_origin_ready":bool(
            (capture.get("physical_reconcile") or {}).get(
                "physical_next_origin_ready"
            )
        ),
        "physical_origin_receipt":(
            str(physical_origin_out) if physical_origin_receipt is not None else None
        ),
        "physical_origin_receipt_sha256":(
            physical_origin_receipt.get("physical_origin_receipt_sha256")
            if physical_origin_receipt is not None else None
        ),
        "next_gate":(
            "controller may replan from physical_origin_receipt"
            if physical_origin_receipt is not None
            else "field tau0 captured; provide planner receipt/current origin to close the replan loop"
        ),
    }
    final={**payload,"field_handoff_sha256":_sha256_payload(payload)}
    path=Path(summary_receipt)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding="utf-8")
    return final


def main(argv=None):
    parser=argparse.ArgumentParser(
        description=(
            "Fail-closed WindowPilot field handoff. Defaults to read-only "
            "preflight; --execute is required for real actuator motion."
        )
    )
    parser.add_argument("--windowpilot",default="http://127.0.0.1:8001")
    parser.add_argument("--commission-bundle",required=True)
    parser.add_argument("--opening-id",default="W1")
    parser.add_argument("--topology-id",default="physical-single-window")
    parser.add_argument(
        "--sensor-apply-receipt",
        action="append",
        default=[],
    )
    parser.add_argument(
        "--preflight-receipt",
        default="artifacts/physical-tau0-preflight.json",
    )
    parser.add_argument(
        "--trajectory-out",
        default="artifacts/physical-tau0.jsonl",
    )
    parser.add_argument(
        "--tau0-receipt",
        default="artifacts/physical-tau0-audit.json",
    )
    parser.add_argument(
        "--summary-receipt",
        default="artifacts/physical-field-handoff.json",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Explicitly allow the bounded physical tau0 motion after preflight.",
    )
    parser.add_argument("--closed-loop-receipt",type=Path)
    parser.add_argument("--closed-loop-step-index",type=int,default=0)
    parser.add_argument("--predicted-zone-id")
    parser.add_argument("--current-origin",type=Path)
    parser.add_argument("--physical-origin-out",type=Path)
    args=parser.parse_args(argv)

    payload=run_field_handoff(
        driver=WindowPilotHTTPDriver(args.windowpilot),
        commission_bundle=args.commission_bundle,
        opening_id=args.opening_id,
        topology_id=args.topology_id,
        preflight_receipt=args.preflight_receipt,
        trajectory_out=args.trajectory_out,
        tau0_receipt=args.tau0_receipt,
        summary_receipt=args.summary_receipt,
        sensor_apply_receipts=args.sensor_apply_receipt,
        execute=args.execute,
        closed_loop_receipt=args.closed_loop_receipt,
        closed_loop_step_index=args.closed_loop_step_index,
        predicted_zone_id=args.predicted_zone_id,
        current_origin=args.current_origin,
        physical_origin_out=args.physical_origin_out,
    )
    print(json.dumps(payload,ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
