"""Execute one bounded replanned WindowPilot action from a physical origin.

Default mode is read-only. Real motion requires --execute.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from airtrajectory.drivers import WindowPilotHTTPDriver
from airtrajectory.physical_action_snapshot import capture_post_action_snapshot
from airtrajectory.physical_replan_handoff import (
    authorize_replanned_physical_action,
    build_replanned_physical_step_origin,
    extract_replanned_physical_action,
)


def _sha256(payload) -> str:
    raw=json.dumps(
        payload,
        sort_keys=True,
        separators=(",",":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _write(path, payload):
    target=Path(path)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(
        json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True),
        encoding="utf-8",
    )


def run_replanned_physical_step(
    *,
    driver,
    physical_origin_receipt,
    planner_receipt,
    opening_id,
    zone_id,
    max_delta_pct,
    summary_out,
    next_origin_out,
    execute=False,
    snapshot_fn=capture_post_action_snapshot,
):
    physical_payload=json.loads(
        Path(physical_origin_receipt).read_text(encoding="utf-8")
    )
    planner_payload=json.loads(
        Path(planner_receipt).read_text(encoding="utf-8")
    )

    handoff=extract_replanned_physical_action(
        planner_payload=planner_payload,
        physical_origin_receipt=physical_payload,
        opening_id=opening_id,
    )
    authorization=authorize_replanned_physical_action(
        handoff,
        max_delta_pct=float(max_delta_pct),
    )

    readiness=driver.physical_readiness()
    if not isinstance(readiness,dict):
        raise RuntimeError("WindowPilot physical readiness returned invalid payload")
    if readiness.get("physical_write_ready") is not True:
        blockers=readiness.get("write_blockers") or ["not physical_write_ready"]
        raise RuntimeError(
            "replanned physical step is not write-ready: "
            +"; ".join(str(item) for item in blockers)
        )

    readiness_identity=readiness.get("hardware_identity") or {}
    readiness_identity_sha=(
        readiness_identity.get("identity_sha256")
        if isinstance(readiness_identity,dict) else None
    )

    base={
        "schema_version":"0.1",
        "workflow":"replanned-windowpilot-physical-step-v1",
        "mode":"execute" if execute else "read-only",
        "opening_id":str(opening_id),
        "zone_id":str(zone_id),
        "physical_origin_receipt":str(physical_origin_receipt),
        "planner_receipt":str(planner_receipt),
        "physical_origin_sha256":handoff["physical_origin_sha256"],
        "physical_origin_receipt_sha256":handoff[
            "physical_origin_receipt_sha256"
        ],
        "planner_receipt_sha256":handoff["planner_receipt_sha256"],
        "planner_step_sha256":handoff["planner_step_sha256"],
        "replanned_action_handoff_sha256":handoff[
            "replanned_action_handoff_sha256"
        ],
        "replanned_action_authorization_sha256":authorization[
            "replanned_action_authorization_sha256"
        ],
        "planned_target_pct":handoff["planned_target_pct"],
        "authorized_target_pct":authorization["authorized_target_pct"],
        "max_delta_pct":authorization["max_delta_pct"],
        "planner_action_fully_authorized":authorization[
            "planner_action_fully_authorized"
        ],
        "intervention":authorization["intervention"],
        "physical_write_ready":True,
        "readiness_hardware_identity_sha256":readiness_identity_sha,
    }

    if not execute:
        payload={
            **base,
            "status":"READY_FOR_EXPLICIT_EXECUTION",
            "motion_performed":False,
            "next_origin_ready":False,
            "next_action":(
                "rerun with --execute after reviewing the bounded authorization"
            ),
        }
        final={**payload,"replanned_physical_step_sha256":_sha256(payload)}
        _write(summary_out,final)
        return final

    feedback=driver.set_position(
        str(opening_id),
        float(authorization["authorized_target_pct"]),
    )
    feedback_row=asdict(feedback)
    if feedback.measured_position_pct is None:
        raise RuntimeError("replanned physical step lacks measured actuator feedback")
    if float(feedback.timestamp)<=0:
        raise RuntimeError("replanned physical feedback timestamp is invalid")

    command_ack=getattr(driver,"last_command_ack",None)
    if not isinstance(command_ack,dict):
        raise RuntimeError("replanned physical step missing verified command acknowledgement")
    if (
        readiness_identity_sha
        and command_ack.get("hardware_identity_sha256")!=readiness_identity_sha
    ):
        raise RuntimeError(
            "command acknowledgement hardware identity does not match readiness"
        )

    try:
        snapshot=snapshot_fn(
            driver=driver,
            after_timestamp=float(feedback.timestamp),
        )
    except Exception as exc:
        partial={
            **base,
            "status":"BLOCKED_POST_ACTION_SENSORS",
            "motion_performed":True,
            "next_origin_ready":False,
            "actuator_feedback":feedback_row,
            "command_ack":command_ack,
            "error":str(exc),
        }
        final={**partial,"replanned_physical_step_sha256":_sha256(partial)}
        _write(summary_out,final)
        raise RuntimeError(
            "replanned physical action executed but fresh sensor capture failed: "
            +str(exc)
        ) from exc

    next_origin=build_replanned_physical_step_origin(
        previous_physical_origin_receipt=physical_payload,
        authorization=authorization,
        command_ack=command_ack,
        feedback=feedback_row,
        sensor_snapshot=snapshot,
        zone_id=str(zone_id),
    )
    _write(next_origin_out,next_origin)

    payload={
        **base,
        "status":"PASS",
        "motion_performed":True,
        "next_origin_ready":True,
        "actuator_feedback":feedback_row,
        "command_ack_sha256":command_ack.get("command_ack_sha256"),
        "sensor_snapshot_sha256":snapshot.get("snapshot_sha256"),
        "next_physical_origin":str(next_origin_out),
        "next_physical_origin_sha256":next_origin["origin_sha256"],
        "next_physical_origin_receipt_sha256":next_origin[
            "physical_origin_receipt_sha256"
        ],
        "evidence_boundary":(
            "one bounded replanned physical action executed with measured position "
            "and fresh post-action CO2/rain; this is one field transition, not a "
            "multi-step field validation by itself"
        ),
    }
    final={**payload,"replanned_physical_step_sha256":_sha256(payload)}
    _write(summary_out,final)
    return final


def main(argv=None):
    parser=argparse.ArgumentParser(
        description=(
            "Run one bounded WindowPilot action selected by real ContamX from "
            "a verified physical origin. Defaults to read-only."
        )
    )
    parser.add_argument("--windowpilot",default="http://127.0.0.1:8001")
    parser.add_argument("--physical-origin-receipt",required=True)
    parser.add_argument("--planner-receipt",required=True)
    parser.add_argument("--opening-id",required=True)
    parser.add_argument("--zone-id",required=True)
    parser.add_argument("--max-delta-pct",type=float,required=True)
    parser.add_argument(
        "--summary-out",
        default="artifacts/replanned-physical-step.json",
    )
    parser.add_argument(
        "--next-origin-out",
        default="artifacts/physical-next-origin-2.json",
    )
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args(argv)

    result=run_replanned_physical_step(
        driver=WindowPilotHTTPDriver(args.windowpilot),
        physical_origin_receipt=args.physical_origin_receipt,
        planner_receipt=args.planner_receipt,
        opening_id=args.opening_id,
        zone_id=args.zone_id,
        max_delta_pct=args.max_delta_pct,
        summary_out=args.summary_out,
        next_origin_out=args.next_origin_out,
        execute=args.execute,
    )
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
