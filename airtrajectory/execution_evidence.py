"""Project FieldExecutionRecord v0.1 into a domain-neutral evidence envelope."""
from __future__ import annotations

from typing import Any, Mapping


_RESULTS={"PASS","FAIL","BLOCKED","UNCERTAIN"}


def _as_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def build_execution_evidence_envelope(
    field_record: Mapping[str, Any],
) -> dict[str, Any]:
    """Build ExecutionEvidenceEnvelope v0.1 from FieldExecutionRecord v0.1."""
    record=_as_mapping(field_record,"field_record")
    if record.get("record_type")!="field-execution-record-v0.1":
        raise RuntimeError("unsupported field execution record type")
    result=str(record.get("result") or "")
    if result not in _RESULTS:
        raise RuntimeError("invalid field execution result")

    target=_as_mapping(record.get("target"),"target")
    request=record.get("request")
    request_obj={} if request is None else dict(_as_mapping(request,"request"))
    observation=_as_mapping(record.get("observation"),"observation")

    observations=[]
    if observation.get("measured_position_pct") is not None:
        observations.append({
            "kind":"physical.position_pct",
            "observed_at":record.get("completed_at"),
            "value":observation.get("measured_position_pct"),
            "evidence_ref":None,
        })
    if observation.get("sensor_snapshot_sha256"):
        observations.append({
            "kind":"physical.sensor_snapshot",
            "observed_at":record.get("completed_at"),
            "value":{
                "sha256":observation["sensor_snapshot_sha256"],
                "fresh_after_action":observation.get("fresh_after_action"),
            },
            "evidence_ref":observation["sensor_snapshot_sha256"],
        })

    recovery_phase=None
    verify_phase=None
    for phase in record.get("phases") or []:
        row=_as_mapping(phase,"phase")
        if row.get("phase")=="RECOVERY":
            recovery_phase=row
        elif row.get("phase")=="VERIFY":
            verify_phase=row

    recovery_required=result=="UNCERTAIN" or recovery_phase is not None
    if not recovery_required:
        recovery={
            "required":False,
            "performed":False,
            "status":"NOT_REQUIRED",
            "evidence_refs":[],
        }
    else:
        recovery_status=(
            str(recovery_phase.get("result"))
            if recovery_phase is not None else "UNCERTAIN"
        )
        recovery={
            "required":True,
            "performed":recovery_phase is not None,
            "status":recovery_status,
            "evidence_refs":[
                str(item)
                for item in (
                    recovery_phase.get("evidence_refs") if recovery_phase else []
                )
                if item
            ],
        }

    cycle_verified=bool(record.get("cycle_verified"))
    verification={
        "performed":verify_phase is not None,
        "status":(
            "PASS" if cycle_verified
            else (
                str(verify_phase.get("result"))
                if verify_phase is not None else "NOT_PERFORMED"
            )
        ),
        "verifier":"airtrajectory.persisted-physical-cycle-v1",
        "evidence_refs":[
            str(item)
            for item in (
                verify_phase.get("evidence_refs") if verify_phase else []
            )
            if item
        ],
    }

    envelope={
        "schema_version":"0.1",
        "record_type":"execution-evidence-envelope-v0.1",
        "execution_id":str(record["execution_id"]),
        "parent_execution_id":record.get("parent_execution_id"),
        "subject":{
            "kind":"conformance-execution",
            "identity":str(record.get("test_case_id") or "unknown"),
            "version":"field-execution-record-v0.1",
        },
        "target":{
            "kind":"physical-control-target",
            "identity":str(target["target_identity"]),
            "scope":target.get("idempotency_scope_id"),
        },
        "operation":{
            "kind":"physical-control-transition",
            "request_id":request_obj.get("request_id"),
            "ack_id":request_obj.get("command_id"),
            "mutation_expected":request is not None,
            "parameters":{
                "authorized_target_pct":request_obj.get("authorized_target_pct")
            },
        },
        "harness_status":"COMPLETED",
        "result":result,
        "reason_code":record.get("reason_code"),
        "observations":observations,
        "recovery":recovery,
        "verification":verification,
        "provenance":{
            "source_record_type":"field-execution-record-v0.1",
        },
        "artifact_refs":[str(item) for item in record.get("artifact_refs") or []],
        "evidence_boundary":(
            "domain-neutral projection of FieldExecutionRecord v0.1; "
            "domain-specific semantics remain in extensions and source artifacts"
        ),
        "extensions":{
            "physical":{
                "opening_id":target.get("opening_id"),
                "zone_id":target.get("zone_id"),
                "motion_performed":bool(record.get("motion_performed")),
                "mutation_observed":bool(record.get("motion_performed")),
                "fresh_after_action":observation.get("fresh_after_action"),
            }
        },
    }
    validate_execution_evidence_envelope(envelope)
    return envelope


def validate_execution_evidence_envelope(envelope: Mapping[str, Any]) -> None:
    payload=_as_mapping(envelope,"envelope")
    if payload.get("schema_version")!="0.1":
        raise RuntimeError("unsupported envelope schema_version")
    if payload.get("record_type")!="execution-evidence-envelope-v0.1":
        raise RuntimeError("unsupported envelope record type")
    harness_status=payload.get("harness_status")
    if harness_status not in {"COMPLETED","ERROR","INTERRUPTED"}:
        raise RuntimeError("invalid harness_status")
    result=payload.get("result")
    if result not in _RESULTS:
        raise RuntimeError("invalid envelope result")

    for name in ("subject","target","operation","recovery","verification"):
        _as_mapping(payload.get(name),name)

    verification=_as_mapping(payload["verification"],"verification")
    recovery=_as_mapping(payload["recovery"],"recovery")

    if result=="PASS":
        if harness_status!="COMPLETED":
            raise RuntimeError("PASS envelope requires completed harness")
        if verification.get("performed") is not True:
            raise RuntimeError("PASS envelope requires verification")
        if verification.get("status")!="PASS":
            raise RuntimeError("PASS envelope requires verifier PASS")
    if result=="UNCERTAIN" and recovery.get("required") is not True:
        raise RuntimeError("UNCERTAIN envelope requires recovery")
