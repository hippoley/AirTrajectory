"""Transport-neutral conformance record adapter for physical field cycles.

This module is intentionally downstream of AirTrajectory's native evidence.
It converts already-persisted cycle/step/verification receipts into a compact
semantic record that can be serialized separately from JUnit/XML reporting.

The record is exploratory and non-normative. It is not a GEISA artifact.
"""
from __future__ import annotations

import re
from typing import Any, Mapping


_HEX64=re.compile(r"^[0-9a-fA-F]{64}$")
_RESULT_VALUES={"PASS","FAIL","BLOCKED","UNCERTAIN"}
_PHASE_VALUES={"PRECHECK","EXECUTE","OBSERVE","VERIFY","RECOVERY"}


def _as_mapping(value, label: str) -> Mapping[str, Any]:
    if not isinstance(value,Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _result_from_cycle_status(status: str) -> str:
    normalized=str(status or "").strip().upper()
    if normalized=="PASS":
        return "PASS"
    if "UNCERTAIN" in normalized or "RECOVERY_REQUIRED" in normalized:
        return "UNCERTAIN"
    if normalized.startswith("BLOCKED_") or normalized.startswith("SAFE_CLOSED_"):
        return "BLOCKED"
    if normalized in {"FAIL","FAILED"}:
        return "FAIL"
    return "BLOCKED"


def _phase(
    phase: str,
    result: str,
    *,
    reason_code=None,
    detail=None,
    evidence_refs=None,
) -> dict[str,Any]:
    return {
        "phase":phase,
        "result":result,
        "reason_code":reason_code,
        "detail":detail,
        "evidence_refs":[
            str(item)
            for item in (evidence_refs or [])
            if item
        ],
    }


def build_field_execution_record(
    *,
    cycle_summary: Mapping[str,Any],
    step_summary: Mapping[str,Any] | None=None,
    verification_receipt: Mapping[str,Any] | None=None,
    test_case_id: str="airtrajectory.replanned_physical_cycle",
    spec_clause_refs=(),
    artifact_refs=(),
) -> dict[str,Any]:
    """Build one transport-neutral semantic field execution record."""
    cycle=_as_mapping(cycle_summary,"cycle_summary")
    step={} if step_summary is None else dict(
        _as_mapping(step_summary,"step_summary")
    )
    verification={} if verification_receipt is None else dict(
        _as_mapping(verification_receipt,"verification_receipt")
    )

    workflow=str(cycle.get("workflow") or "")
    if workflow!="verified-replanned-physical-cycle-v1":
        raise RuntimeError("unsupported verified physical-cycle workflow")

    execution_id=str(cycle.get("verified_physical_cycle_sha256") or "")
    if len(execution_id)!=64 or not _HEX64.match(execution_id):
        raise RuntimeError("cycle summary lacks stable execution SHA-256")

    status=str(cycle.get("status") or "")
    result=_result_from_cycle_status(status)
    motion_performed=bool(cycle.get("motion_performed"))
    cycle_verified=bool(cycle.get("cycle_verified"))

    if result=="PASS" and not cycle_verified:
        raise RuntimeError("PASS cycle cannot be exported as unverified")
    if cycle_verified and result!="PASS":
        raise RuntimeError("verified cycle must export as PASS")

    opening_id=str(
        cycle.get("opening_id")
        or step.get("opening_id")
        or verification.get("opening_id")
        or ""
    )
    zone_id=str(
        cycle.get("zone_id")
        or step.get("zone_id")
        or verification.get("zone_id")
        or ""
    )
    if not opening_id or not zone_id:
        raise RuntimeError("field execution record requires opening and zone")

    target_identity=str(
        verification.get("origin_hardware_identity_sha256")
        or step.get("readiness_hardware_identity_sha256")
        or step.get("origin_hardware_identity_sha256")
        or ""
    )
    if not _HEX64.match(target_identity):
        raise RuntimeError(
            "field execution record requires stable target hardware identity"
        )

    scope_id=(
        verification.get("command_idempotency_scope_id")
        or cycle.get("command_idempotency_scope_id")
        or step.get("command_idempotency_scope_id")
    )

    request_id=(
        verification.get("command_request_id")
        or cycle.get("command_request_id")
        or step.get("command_request_id")
    )
    command_id=(
        verification.get("command_id")
        or (step.get("command_ack") or {}).get("command_id")
    )
    command_ack_sha=(
        verification.get("command_ack_sha256")
        or cycle.get("command_ack_sha256")
        or step.get("command_ack_sha256")
    )

    authorized_target=(
        verification.get("authorized_target_pct")
        if verification
        else step.get("authorized_target_pct")
    )

    measured_position=(
        verification.get("measured_position_pct")
        if verification
        else (step.get("actuator_feedback") or {}).get(
            "measured_position_pct"
        )
    )
    sensor_snapshot_sha=(
        verification.get("sensor_snapshot_sha256")
        or cycle.get("sensor_snapshot_sha256")
        or step.get("sensor_snapshot_sha256")
    )
    snapshot=step.get("sensor_snapshot") or {}

    reason_code=None if result=="PASS" else status or "BLOCKED"
    detail=(
        cycle.get("verification_error")
        or cycle.get("step_error")
        or cycle.get("evidence_boundary")
    )

    phases=[]
    phases.append(
        _phase(
            "PRECHECK",
            "PASS" if step.get("physical_write_ready") is True or motion_performed else (
                "BLOCKED" if result!="PASS" else "PASS"
            ),
            evidence_refs=[
                step.get("physical_origin_receipt_sha256"),
                step.get("replanned_action_authorization_sha256"),
            ],
        )
    )

    execute_result="PASS" if motion_performed else (
        "UNCERTAIN" if result=="UNCERTAIN" else "BLOCKED"
    )
    phases.append(
        _phase(
            "EXECUTE",
            execute_result,
            reason_code=reason_code if not motion_performed else None,
            evidence_refs=[
                request_id,
                command_ack_sha,
                step.get("execution_lease_claim_sha256"),
            ],
        )
    )

    observe_pass=bool(
        measured_position is not None
        and (
            sensor_snapshot_sha
            or cycle_verified
        )
    )
    phases.append(
        _phase(
            "OBSERVE",
            "PASS" if observe_pass else (
                "UNCERTAIN" if result=="UNCERTAIN" else "BLOCKED"
            ),
            evidence_refs=[
                sensor_snapshot_sha,
                step.get("next_physical_origin_receipt_sha256"),
            ],
        )
    )

    phases.append(
        _phase(
            "VERIFY",
            "PASS" if cycle_verified else (
                "UNCERTAIN" if result=="UNCERTAIN" else "BLOCKED"
            ),
            reason_code=reason_code if not cycle_verified else None,
            detail=cycle.get("verification_error"),
            evidence_refs=[
                cycle.get("physical_cycle_verification_sha256"),
                verification.get("physical_cycle_verification_sha256"),
            ],
        )
    )

    recovery_evidence=step.get("safe_closeout")
    if recovery_evidence or result=="UNCERTAIN":
        recovery_result=(
            "PASS"
            if isinstance(recovery_evidence,Mapping)
            and recovery_evidence.get("confirmed_closed") is True
            else "UNCERTAIN"
        )
        phases.append(
            _phase(
                "RECOVERY",
                recovery_result,
                reason_code=reason_code,
                detail=(
                    recovery_evidence.get("error")
                    if isinstance(recovery_evidence,Mapping)
                    else None
                ),
            )
        )

    refs=[
        str(item)
        for item in artifact_refs
        if item
    ]
    for item in (
        cycle.get("previous_origin_receipt"),
        cycle.get("planner_receipt"),
        cycle.get("step_summary"),
        cycle.get("next_origin"),
        cycle.get("verification_receipt"),
    ):
        if item and str(item) not in refs:
            refs.append(str(item))

    record={
        "schema_version":"0.1",
        "record_type":"field-execution-record-v0.1",
        "execution_id":execution_id,
        "parent_execution_id":(
            str(step.get("replanned_physical_step_sha256"))
            if step.get("replanned_physical_step_sha256")
            else None
        ),
        "test_case_id":str(test_case_id),
        "spec_clause_refs":sorted({
            str(item)
            for item in spec_clause_refs
            if item
        }),
        "result":result,
        "reason_code":reason_code,
        "detail":None if detail is None else str(detail),
        "motion_performed":motion_performed,
        "cycle_verified":cycle_verified,
        "started_at":(
            float(step["origin_freshness_checked_at"])
            if step.get("origin_freshness_checked_at") is not None
            else None
        ),
        "completed_at":(
            float((step.get("actuator_feedback") or {})["timestamp"])
            if (step.get("actuator_feedback") or {}).get("timestamp")
            is not None else None
        ),
        "target":{
            "target_identity":target_identity,
            "opening_id":opening_id,
            "zone_id":zone_id,
            "idempotency_scope_id":(
                None if scope_id is None else str(scope_id)
            ),
        },
        "request":(
            {
                "request_id":str(request_id),
                "command_id":None if command_id is None else str(command_id),
                "command_ack_sha256":(
                    None if command_ack_sha is None else str(command_ack_sha)
                ),
                "authorized_target_pct":(
                    None if authorized_target is None
                    else float(authorized_target)
                ),
            }
            if request_id
            else None
        ),
        "observation":{
            "measured_position_pct":(
                None if measured_position is None
                else float(measured_position)
            ),
            "sensor_snapshot_sha256":(
                None if sensor_snapshot_sha is None
                else str(sensor_snapshot_sha)
            ),
            "fresh_after_action":(
                bool(snapshot.get("fresh_after_action"))
                if snapshot.get("fresh_after_action") is not None
                else (True if cycle_verified else None)
            ),
        },
        "phases":phases,
        "artifact_refs":refs,
        "evidence_boundary":(
            "transport-neutral semantic projection of persisted AirTrajectory "
            "field evidence; this record does not add authenticity beyond the "
            "source physical-control and sensor evidence"
        ),
    }
    validate_field_execution_record(record)
    return record


def validate_field_execution_record(record: Mapping[str,Any]) -> None:
    """Small dependency-free semantic validation for generated records."""
    payload=_as_mapping(record,"record")
    if payload.get("schema_version")!="0.1":
        raise RuntimeError("unsupported field execution record schema_version")
    if payload.get("record_type")!="field-execution-record-v0.1":
        raise RuntimeError("unsupported field execution record type")
    if payload.get("result") not in _RESULT_VALUES:
        raise RuntimeError("invalid field execution result")
    if not _HEX64.match(str(payload.get("execution_id") or "")):
        raise RuntimeError("invalid field execution_id")
    target=_as_mapping(payload.get("target"),"target")
    if not _HEX64.match(str(target.get("target_identity") or "")):
        raise RuntimeError("invalid field target identity")
    phases=payload.get("phases")
    if not isinstance(phases,list) or not phases:
        raise RuntimeError("field execution record requires phases")
    for phase in phases:
        row=_as_mapping(phase,"phase")
        if row.get("phase") not in _PHASE_VALUES:
            raise RuntimeError("invalid field execution phase")
        if row.get("result") not in _RESULT_VALUES:
            raise RuntimeError("invalid field execution phase result")
    if payload.get("result")=="PASS":
        if payload.get("cycle_verified") is not True:
            raise RuntimeError("PASS field execution must be cycle_verified")
        if payload.get("motion_performed") is not True:
            raise RuntimeError("PASS field execution must prove motion")
    if payload.get("cycle_verified") is True and payload.get("result")!="PASS":
        raise RuntimeError("cycle_verified record must be PASS")
