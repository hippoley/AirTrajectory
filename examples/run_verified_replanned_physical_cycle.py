"""Run one replanned physical field transition and verify it as one unit.

Default mode is read-only. Real motion requires --execute. When execute mode
moves hardware successfully, this wrapper immediately re-verifies the persisted
previous-origin/planner/step/next-origin artifacts before it can emit PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from airtrajectory.drivers import WindowPilotHTTPDriver
from airtrajectory.physical_cycle_verify import verify_persisted_physical_cycle

from run_replanned_physical_step import run_replanned_physical_step


def _sha256(payload) -> str:
    raw=json.dumps(
        payload,
        sort_keys=True,
        separators=(",",":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path, payload):
    target=Path(path)
    target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_suffix(target.suffix+".tmp")
    temp.write_text(
        json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    temp.replace(target)


def run_verified_replanned_physical_cycle(
    *,
    driver,
    previous_origin_receipt,
    planner_receipt,
    opening_id,
    zone_id,
    max_delta_pct,
    step_summary_out,
    next_origin_out,
    verification_out,
    cycle_summary_out,
    execute=False,
    max_origin_age_s=30.0,
    lease_dir=None,
):
    step=run_replanned_physical_step(
        driver=driver,
        physical_origin_receipt=previous_origin_receipt,
        planner_receipt=planner_receipt,
        opening_id=opening_id,
        zone_id=zone_id,
        max_delta_pct=max_delta_pct,
        max_origin_age_s=max_origin_age_s,
        summary_out=step_summary_out,
        next_origin_out=next_origin_out,
        execute=execute,
        lease_dir=lease_dir,
    )

    base={
        "schema_version":"0.1",
        "workflow":"verified-replanned-physical-cycle-v1",
        "mode":"execute" if execute else "read-only",
        "previous_origin_receipt":str(previous_origin_receipt),
        "planner_receipt":str(planner_receipt),
        "step_summary":str(step_summary_out),
        "next_origin":str(next_origin_out),
        "verification_receipt":str(verification_out),
        "opening_id":str(opening_id),
        "zone_id":str(zone_id),
        "max_delta_pct":float(max_delta_pct),
        "replanned_physical_step_sha256":step.get(
            "replanned_physical_step_sha256"
        ),
    }

    if not execute:
        payload={
            **base,
            "status":"READY_FOR_EXPLICIT_EXECUTION",
            "motion_performed":False,
            "cycle_verified":False,
            "next_action":"rerun with --execute after reviewing the bounded authorization",
            "evidence_boundary":(
                "read-only authorization/readiness preview; no physical field "
                "transition has been executed"
            ),
        }
        final={**payload,"verified_physical_cycle_sha256":_sha256(payload)}
        _write(cycle_summary_out,final)
        return final

    if step.get("status")!="PASS" or step.get("motion_performed") is not True:
        raise RuntimeError(
            "executed replanned physical step did not produce a PASS motion receipt"
        )
    if step.get("next_origin_ready") is not True:
        raise RuntimeError(
            "executed replanned physical step did not produce a next physical origin"
        )

    try:
        verification=verify_persisted_physical_cycle(
            previous_origin_receipt=_load(previous_origin_receipt),
            planner_payload=_load(planner_receipt),
            step_summary=_load(step_summary_out),
            next_origin_receipt=_load(next_origin_out),
        )
        if verification.get("status")!="PASS":
            raise RuntimeError(
                "persisted physical-cycle verifier did not return PASS"
            )
        _write(verification_out,verification)
    except Exception as exc:
        payload={
            **base,
            "status":"BLOCKED_VERIFICATION_FAILED",
            "motion_performed":True,
            "cycle_verified":False,
            "next_origin_ready":bool(step.get("next_origin_ready")),
            "next_physical_origin_receipt_sha256":step.get(
                "next_physical_origin_receipt_sha256"
            ),
            "verification_error":str(exc),
            "evidence_boundary":(
                "the bounded physical action executed and persisted a candidate "
                "next origin, but independent persisted-cycle verification failed; "
                "do not treat this transition as verified"
            ),
        }
        final={**payload,"verified_physical_cycle_sha256":_sha256(payload)}
        _write(cycle_summary_out,final)
        raise RuntimeError(
            "physical action executed but persisted-cycle verification failed: "
            +str(exc)
        ) from exc

    payload={
        **base,
        "status":"PASS",
        "motion_performed":True,
        "cycle_verified":True,
        "field_transition_contract_verified":bool(
            verification.get("field_transition_contract_verified")
        ),
        "physical_cycle_verification_sha256":verification.get(
            "physical_cycle_verification_sha256"
        ),
        "previous_origin_receipt_sha256":verification.get(
            "previous_origin_receipt_sha256"
        ),
        "planner_receipt_sha256":verification.get("planner_receipt_sha256"),
        "planner_step_sha256":verification.get("planner_step_sha256"),
        "command_request_id":verification.get("command_request_id"),
        "command_idempotency_scope_id":verification.get(
            "command_idempotency_scope_id"
        ),
        "command_ack_sha256":verification.get("command_ack_sha256"),
        "sensor_snapshot_sha256":verification.get("sensor_snapshot_sha256"),
        "next_origin_receipt_sha256":verification.get(
            "next_origin_receipt_sha256"
        ),
        "evidence_boundary":(
            "one bounded physical field transition plus independent persisted-"
            "artifact verification; this is not a multi-cycle field campaign "
            "or whole-home field validation"
        ),
    }
    final={**payload,"verified_physical_cycle_sha256":_sha256(payload)}
    _write(cycle_summary_out,final)
    return final


def main(argv=None):
    parser=argparse.ArgumentParser(
        description=(
            "Run one bounded replanned WindowPilot field transition and "
            "independently verify its persisted evidence. Defaults to read-only."
        )
    )
    parser.add_argument("--windowpilot",default="http://127.0.0.1:8001")
    parser.add_argument("--previous-origin",required=True)
    parser.add_argument("--planner-receipt",required=True)
    parser.add_argument("--opening-id",required=True)
    parser.add_argument("--zone-id",required=True)
    parser.add_argument("--max-delta-pct",type=float,required=True)
    parser.add_argument("--max-origin-age-s",type=float,default=30.0)
    parser.add_argument(
        "--lease-dir",
        default="artifacts/physical-origin-leases",
    )
    parser.add_argument(
        "--step-summary-out",
        default="artifacts/replanned-physical-step.json",
    )
    parser.add_argument(
        "--next-origin-out",
        default="artifacts/physical-next-origin-2.json",
    )
    parser.add_argument(
        "--verification-out",
        default="artifacts/replanned-physical-cycle-verification.json",
    )
    parser.add_argument(
        "--cycle-summary-out",
        default="artifacts/verified-replanned-physical-cycle.json",
    )
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args(argv)

    result=run_verified_replanned_physical_cycle(
        driver=WindowPilotHTTPDriver(args.windowpilot),
        previous_origin_receipt=args.previous_origin,
        planner_receipt=args.planner_receipt,
        opening_id=args.opening_id,
        zone_id=args.zone_id,
        max_delta_pct=args.max_delta_pct,
        max_origin_age_s=args.max_origin_age_s,
        step_summary_out=args.step_summary_out,
        next_origin_out=args.next_origin_out,
        verification_out=args.verification_out,
        cycle_summary_out=args.cycle_summary_out,
        execute=args.execute,
        lease_dir=args.lease_dir,
    )
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
