"""Execute one bounded replanned WindowPilot action from a physical origin.

Default mode is read-only. Real motion requires --execute.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

from airtrajectory.drivers import WindowPilotHTTPDriver
from airtrajectory.physical_action_snapshot import capture_post_action_snapshot
from airtrajectory.physical_origin import verify_physical_origin_receipt
from airtrajectory.physical_origin_lease import (
    claim_physical_origin_execution,
    finalize_physical_origin_execution,
    verify_physical_origin_execution_lease,
)
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


def _safe_closeout_after_sensor_failure(driver, opening_id, prior_feedback):
    """Best-effort measured closeout after an executed step loses fresh sensors."""
    result={
        "attempted":False,
        "required":False,
        "confirmed_closed":False,
        "feedback":None,
        "command_ack":None,
        "error":None,
    }
    measured=getattr(prior_feedback,"measured_position_pct",None)
    if measured is None:
        result["required"]=True
    else:
        result["required"]=float(measured)>1.0
    if not result["required"]:
        result["confirmed_closed"]=True
        result["feedback"]=asdict(prior_feedback)
        return result

    result["attempted"]=True
    try:
        close_feedback=driver.set_position(str(opening_id),0.0)
        result["feedback"]=asdict(close_feedback)
        result["command_ack"]=getattr(driver,"last_command_ack",None)
        close_measured=close_feedback.measured_position_pct
        if close_measured is None:
            raise RuntimeError("safe closeout lacks measured position feedback")
        if abs(float(close_measured))>1.0:
            raise RuntimeError(
                f"safe closeout remained at {float(close_measured):.2f}%"
            )
        if float(close_feedback.timestamp)<=float(prior_feedback.timestamp):
            raise RuntimeError("safe closeout feedback is not newer than prior action")
        result["confirmed_closed"]=True
        return result
    except Exception as exc:
        result["error"]=str(exc)
        return result


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
    max_origin_age_s=30.0,
    clock_fn=time.time,
    lease_dir=None,
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

    verified_origin=verify_physical_origin_receipt(physical_payload)
    max_age=float(max_origin_age_s)
    if max_age<=0:
        raise ValueError("max_origin_age_s must be positive")
    target_opening=str(opening_id)
    target_zone=str(zone_id)

    origin_identity=str(
        verified_origin["opening_hardware_identities"].get(target_opening) or ""
    )
    if len(origin_identity)!=64 or any(
        ch not in "0123456789abcdef" for ch in origin_identity.lower()
    ):
        raise RuntimeError(
            "physical origin lacks hardware identity for target opening"
        )

    opening_ts=verified_origin["opening_observed_at"].get(target_opening)
    zone_ts=verified_origin["zone_observed_at"].get(target_zone)
    rain_ts=verified_origin.get("rain_observed_at")
    if opening_ts is None:
        raise RuntimeError(
            "physical origin lacks observation timestamp for target opening"
        )
    if zone_ts is None:
        raise RuntimeError(
            "physical origin lacks observation timestamp for target zone"
        )
    if rain_ts is None:
        raise RuntimeError("physical origin lacks rain observation timestamp")

    now=float(clock_fn())
    ages={
        "opening":now-float(opening_ts),
        "zone":now-float(zone_ts),
        "rain":now-float(rain_ts),
    }
    future=[key for key,age in ages.items() if age < -1.0]
    if future:
        raise RuntimeError(
            "physical origin contains future-dated observations: "
            + ",".join(sorted(future))
        )
    stale={
        key:age
        for key,age in ages.items()
        if age>max_age
    }
    if stale:
        rendered=", ".join(
            f"{key}={age:.3f}s"
            for key,age in sorted(stale.items())
        )
        raise RuntimeError(
            "physical origin is stale for replanned execution: "
            +rendered+f" > {max_age:.3f}s"
        )

    caps=driver.capabilities()
    if caps.simulated:
        raise RuntimeError("replanned physical step requires a non-simulated driver")
    if caps.measured_position is not True:
        raise RuntimeError("replanned physical step requires measured position feedback")

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
    identity=str(readiness_identity_sha or "")
    if len(identity)!=64 or any(
        ch not in "0123456789abcdef" for ch in identity.lower()
    ):
        raise RuntimeError(
            "replanned physical step readiness lacks stable hardware identity"
        )
    if identity!=origin_identity:
        raise RuntimeError(
            "WindowPilot readiness hardware identity does not match "
            "the target opening's physical-origin identity"
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
        "origin_hardware_identity_sha256":origin_identity,
        "max_origin_age_s":max_age,
        "origin_freshness_checked_at":now,
        "origin_evidence_age_s":dict(sorted(ages.items())),
        "handoff":handoff,
        "authorization":authorization,
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

    resolved_lease_dir=(
        Path(lease_dir)
        if lease_dir is not None
        else Path(summary_out).parent/"physical-origin-leases"
    )
    lease_claim=claim_physical_origin_execution(
        lease_dir=resolved_lease_dir,
        origin_receipt_sha256=handoff["physical_origin_receipt_sha256"],
        origin_sha256=handoff["physical_origin_sha256"],
        planner_receipt_sha256=handoff["planner_receipt_sha256"],
        planner_step_sha256=handoff["planner_step_sha256"],
        opening_id=str(opening_id),
        zone_id=str(zone_id),
        claimed_at=now,
    )
    base={
        **base,
        "execution_lease_path":lease_claim["lease_path"],
        "execution_lease_claim_sha256":lease_claim["lease_sha256"],
    }

    try:
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
        command_request_id=getattr(driver,"last_command_request_id",None)
        if not isinstance(command_ack,dict):
            raise RuntimeError("replanned physical step missing verified command acknowledgement")
        if not command_request_id:
            raise RuntimeError(
                "replanned physical step missing request-bound command identity"
            )
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
            recovery=_safe_closeout_after_sensor_failure(
                driver,
                str(opening_id),
                feedback,
            )
            status=(
                "SAFE_CLOSED_POST_ACTION_SENSORS_BLOCKED"
                if recovery["confirmed_closed"]
                else "BLOCKED_POST_ACTION_SENSORS_CLOSEOUT_FAILED"
            )
            partial={
                **base,
                "status":status,
                "motion_performed":True,
                "next_origin_ready":False,
                "actuator_feedback":feedback_row,
                "command_request_id":str(command_request_id),
                "command_ack":command_ack,
                "sensor_failure":str(exc),
                "safe_closeout":recovery,
                "evidence_boundary":(
                    "the replanned action executed, but fresh post-action sensors "
                    "were unavailable; a measured safe closeout was attempted and "
                    "no next physical origin is emitted"
                ),
            }
            final={**partial,"replanned_physical_step_sha256":_sha256(partial)}
            _write(summary_out,final)
            recovery_note=(
                "safe closeout confirmed"
                if recovery["confirmed_closed"]
                else "safe closeout failed: "+str(recovery.get("error") or "unknown")
            )
            raise RuntimeError(
                "replanned physical action executed but fresh sensor capture failed; "
                +recovery_note+": "+str(exc)
            ) from exc

        next_origin=build_replanned_physical_step_origin(
            previous_physical_origin_receipt=physical_payload,
            authorization=authorization,
            command_ack=command_ack,
            expected_request_id=str(command_request_id),
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
            "command_request_id":str(command_request_id),
            "command_ack":command_ack,
            "command_ack_sha256":command_ack.get("command_ack_sha256"),
            "sensor_snapshot":snapshot,
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
        finalized_lease=finalize_physical_origin_execution(
            lease_path=lease_claim["lease_path"],
            status="ADVANCED",
            finalized_at=max(float(clock_fn()),now+1e-6),
            next_origin_receipt_sha256=next_origin[
                "physical_origin_receipt_sha256"
            ],
            step_summary_sha256=final["replanned_physical_step_sha256"],
        )
        final={
            **final,
            "execution_lease_status":"ADVANCED",
            "execution_lease_final_sha256":finalized_lease["lease_sha256"],
        }
        _write(summary_out,final)
        return final

    except Exception as exc:
        try:
            lease_state=verify_physical_origin_execution_lease(
                lease_path=lease_claim["lease_path"],
                expected_origin_receipt_sha256=handoff[
                    "physical_origin_receipt_sha256"
                ],
            )
            if lease_state["status"]=="IN_FLIGHT":
                finalize_physical_origin_execution(
                    lease_path=lease_claim["lease_path"],
                    status="RECOVERY_REQUIRED",
                    finalized_at=max(float(clock_fn()),now+1e-6),
                    step_summary_sha256=(
                        json.loads(Path(summary_out).read_text(encoding="utf-8")).get(
                            "replanned_physical_step_sha256"
                        )
                        if Path(summary_out).exists()
                        else None
                    ),
                    recovery={
                        "error":str(exc),
                        "requires_new_physical_origin":True,
                    },
                )
        except Exception as lease_exc:
            raise RuntimeError(
                "physical execution failed and lease finalization also failed: "
                f"execution={exc}; lease={lease_exc}"
            ) from exc
        raise


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
        "--max-origin-age-s",
        type=float,
        default=30.0,
        help="Reject physical opening/zone/rain evidence older than this before any write.",
    )
    parser.add_argument(
        "--summary-out",
        default="artifacts/replanned-physical-step.json",
    )
    parser.add_argument(
        "--next-origin-out",
        default="artifacts/physical-next-origin-2.json",
    )
    parser.add_argument(
        "--lease-dir",
        default="artifacts/physical-origin-leases",
        help=(
            "Durable local single-use execution lease directory. "
            "Do not reuse an old physical origin after it has been claimed."
        ),
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
        max_origin_age_s=args.max_origin_age_s,
        summary_out=args.summary_out,
        next_origin_out=args.next_origin_out,
        execute=args.execute,
        lease_dir=args.lease_dir,
    )
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
