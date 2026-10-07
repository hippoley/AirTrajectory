"""Recover a fresh physical origin from a RECOVERY_REQUIRED execution lease."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import time

from airtrajectory.drivers import WindowPilotHTTPDriver
from airtrajectory.physical_action_snapshot import capture_post_action_snapshot
from airtrajectory.physical_origin import verify_physical_origin_receipt
from airtrajectory.physical_origin_lease import (
    record_physical_origin_recovery,
    verify_physical_origin_execution_lease,
)
from airtrajectory.physical_recovery import build_recovery_physical_origin


def _sha256(payload):
    raw=json.dumps(
        payload,
        sort_keys=True,
        separators=(",",":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _prepare_atomic(path, payload):
    target=Path(path)
    target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_name(target.name+".pending")
    data=(
        json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n"
    ).encode("utf-8")
    fd=os.open(
        str(temp),
        os.O_WRONLY|os.O_CREAT|os.O_TRUNC,
        0o600,
    )
    try:
        with os.fdopen(fd,"wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        raise
    return temp,target


def _write(path, payload):
    target=Path(path)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(
        json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )


def recover_physical_origin(
    *,
    driver,
    previous_origin_receipt,
    lease_path,
    recovery_origin_out,
    summary_out,
    execute_closeout=False,
    position_tolerance_pct=1.0,
    max_position_age_s=10.0,
    snapshot_fn=capture_post_action_snapshot,
    clock_fn=time.time,
):
    previous_payload=json.loads(
        Path(previous_origin_receipt).read_text(encoding="utf-8")
    )
    previous=verify_physical_origin_receipt(previous_payload)
    lease=verify_physical_origin_execution_lease(
        lease_path=lease_path,
        expected_origin_receipt_sha256=previous["receipt_sha256"],
    )
    if lease["status"]!="RECOVERY_REQUIRED":
        raise RuntimeError(
            "physical recovery requires a RECOVERY_REQUIRED execution lease"
        )

    opening_id=str(lease["opening_id"])
    zone_id=str(lease["zone_id"])
    expected_identity=str(
        previous["opening_hardware_identities"].get(opening_id) or ""
    )
    if not expected_identity:
        raise RuntimeError(
            "previous physical origin lacks hardware identity for recovery opening"
        )

    caps=driver.capabilities()
    if caps.simulated:
        raise RuntimeError("physical recovery requires a non-simulated driver")
    if caps.measured_position is not True:
        raise RuntimeError("physical recovery requires measured position feedback")

    readiness=driver.physical_readiness()
    if not isinstance(readiness,dict):
        raise RuntimeError("WindowPilot recovery readiness is invalid")
    identity_payload=readiness.get("hardware_identity") or {}
    readiness_identity=(
        str(identity_payload.get("identity_sha256") or "")
        if isinstance(identity_payload,dict)
        else ""
    )
    if readiness_identity!=expected_identity:
        raise RuntimeError(
            "WindowPilot recovery hardware identity does not match previous origin"
        )

    position_feedback=readiness.get("latest_position_feedback")
    if not isinstance(position_feedback,dict):
        raise RuntimeError("physical recovery lacks latest_position_feedback")
    if position_feedback.get("measured") is not True:
        raise RuntimeError("physical recovery position feedback is not measured")
    position_pct=float(position_feedback.get("position_pct"))
    position_ts=float(position_feedback.get("timestamp") or 0)
    now=float(clock_fn())
    max_age=float(max_position_age_s)
    if not 0<max_age<=60:
        raise ValueError("max_position_age_s must be within (0,60]")
    age=now-position_ts
    if position_ts<=0:
        raise RuntimeError("physical recovery position timestamp is invalid")
    if age < -1.0:
        raise RuntimeError("physical recovery position feedback is future-dated")
    if age>max_age:
        raise RuntimeError(
            f"physical recovery position feedback is stale: {age:.3f}s > {max_age:.3f}s"
        )

    tolerance=float(position_tolerance_pct)
    if not 0<tolerance<=1.0:
        raise ValueError("position_tolerance_pct must be within (0,1]")

    closeout_ack=None
    motion_performed=False
    if position_pct>tolerance:
        if not execute_closeout:
            payload={
                "schema_version":"0.1",
                "workflow":"recover-physical-origin-v1",
                "status":"CLOSEOUT_REQUIRED",
                "motion_performed":False,
                "opening_id":opening_id,
                "zone_id":zone_id,
                "measured_position_pct":position_pct,
                "position_tolerance_pct":tolerance,
                "physical_origin_receipt_sha256":previous["receipt_sha256"],
                "execution_lease_sha256":lease["lease_sha256"],
                "next_action":(
                    "rerun with --execute-closeout to perform an idempotent "
                    "measured close command before recovery observation"
                ),
            }
            final={**payload,"recovery_summary_sha256":_sha256(payload)}
            _write(summary_out,final)
            return final

        if readiness.get("physical_write_ready") is not True:
            blockers=readiness.get("write_blockers") or ["not physical_write_ready"]
            raise RuntimeError(
                "physical recovery closeout is not write-ready: "
                +"; ".join(str(item) for item in blockers)
            )
        feedback=driver.set_position(opening_id,0.0)
        if feedback.measured_position_pct is None:
            raise RuntimeError("physical recovery closeout lacks measured feedback")
        if float(feedback.measured_position_pct)>tolerance:
            raise RuntimeError("physical recovery closeout did not reach closed state")
        position_feedback=asdict(feedback)
        position_pct=float(feedback.measured_position_pct)
        position_ts=float(feedback.timestamp)
        closeout_ack=getattr(driver,"last_command_ack",None)
        if not isinstance(closeout_ack,dict):
            raise RuntimeError("physical recovery closeout lacks command acknowledgement")
        motion_performed=True

    snapshot=snapshot_fn(
        driver=driver,
        after_timestamp=position_ts,
    )
    recovery_origin=build_recovery_physical_origin(
        previous_origin_receipt=previous_payload,
        recovery_lease=lease,
        hardware_identity_sha256=readiness_identity,
        position_feedback=position_feedback,
        sensor_snapshot=snapshot,
        closeout_command_ack=closeout_ack,
        position_tolerance_pct=tolerance,
    )

    summary_payload={
        "schema_version":"0.1",
        "workflow":"recover-physical-origin-v1",
        "status":"PASS",
        "motion_performed":motion_performed,
        "opening_id":opening_id,
        "zone_id":zone_id,
        "physical_origin_receipt_sha256":previous["receipt_sha256"],
        "execution_lease_sha256":lease["lease_sha256"],
        "readiness_hardware_identity_sha256":readiness_identity,
        "position_feedback":position_feedback,
        "closeout_command_ack":closeout_ack,
        "sensor_snapshot":snapshot,
        "recovery_origin":str(recovery_origin_out),
        "recovery_origin_sha256":recovery_origin["origin_sha256"],
        "recovery_origin_receipt_sha256":recovery_origin[
            "physical_origin_receipt_sha256"
        ],
        "evidence_boundary":(
            "re-entry is allowed only through a newly observed physical origin; "
            "the consumed parent origin remains non-replayable"
        ),
    }
    summary={
        **summary_payload,
        "recovery_summary_sha256":_sha256(summary_payload),
    }

    recovered_at=max(
        float(clock_fn()),
        float(lease.get("finalized_at") or 0)+1e-6,
        float(snapshot["co2_timestamp"]),
        float(snapshot["rain_timestamp"]),
    )
    origin_temp,origin_target=_prepare_atomic(
        recovery_origin_out,
        recovery_origin,
    )
    summary_temp,summary_target=_prepare_atomic(
        summary_out,
        summary,
    )
    try:
        record_physical_origin_recovery(
            lease_path=lease_path,
            recovered_at=recovered_at,
            recovery_origin_sha256=recovery_origin["origin_sha256"],
            recovery_origin_receipt_sha256=recovery_origin[
                "physical_origin_receipt_sha256"
            ],
            recovery_summary_sha256=summary["recovery_summary_sha256"],
        )
        os.replace(origin_temp,origin_target)
        os.replace(summary_temp,summary_target)
    except Exception:
        # Pending files intentionally remain when possible. The consumed lease
        # is never rolled back to RECOVERY_REQUIRED/available automatically.
        raise
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(
        description=(
            "Recover a new physical origin from a RECOVERY_REQUIRED cycle. "
            "Never reuses the consumed parent origin."
        )
    )
    parser.add_argument("--windowpilot",default="http://127.0.0.1:8001")
    parser.add_argument("--previous-origin-receipt",required=True)
    parser.add_argument("--lease",required=True)
    parser.add_argument(
        "--recovery-origin-out",
        default="artifacts/physical-recovery-origin.json",
    )
    parser.add_argument(
        "--summary-out",
        default="artifacts/physical-recovery-summary.json",
    )
    parser.add_argument("--position-tolerance-pct",type=float,default=1.0)
    parser.add_argument("--max-position-age-s",type=float,default=10.0)
    parser.add_argument(
        "--execute-closeout",
        action="store_true",
        help="Explicitly allow a measured 0% closeout when the window is not closed.",
    )
    args=parser.parse_args(argv)

    result=recover_physical_origin(
        driver=WindowPilotHTTPDriver(args.windowpilot),
        previous_origin_receipt=args.previous_origin_receipt,
        lease_path=args.lease,
        recovery_origin_out=args.recovery_origin_out,
        summary_out=args.summary_out,
        execute_closeout=args.execute_closeout,
        position_tolerance_pct=args.position_tolerance_pct,
        max_position_age_s=args.max_position_age_s,
    )
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
