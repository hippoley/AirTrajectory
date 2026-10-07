"""Independent verification for one persisted replanned physical cycle."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .physical_origin import verify_physical_origin_receipt
from .physical_replan_handoff import (
    authorize_replanned_physical_action,
    build_replanned_physical_step_origin,
    extract_replanned_physical_action,
)


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _verify_embedded_hash(payload: Mapping[str, Any], field: str, label: str) -> str:
    provided=str(payload.get(field) or "")
    if len(provided)!=64:
        raise RuntimeError(f"{label} is missing SHA-256")
    calculated=_sha256({
        key:value
        for key,value in payload.items()
        if key!=field
    })
    if calculated!=provided:
        raise RuntimeError(f"{label} SHA-256 mismatch")
    return provided


def verify_persisted_physical_cycle(
    *,
    previous_origin_receipt: Mapping[str, Any],
    planner_payload: Mapping[str, Any],
    step_summary: Mapping[str, Any],
    next_origin_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-derive a persisted field transition from all source artifacts."""
    if not isinstance(step_summary,Mapping):
        raise ValueError("step_summary must be an object")
    if step_summary.get("workflow")!="replanned-windowpilot-physical-step-v1":
        raise RuntimeError("unsupported replanned physical step workflow")
    if step_summary.get("mode")!="execute":
        raise RuntimeError("persisted cycle verification requires execute mode")
    if step_summary.get("status")!="PASS":
        raise RuntimeError("persisted physical step summary is not PASS")
    if step_summary.get("motion_performed") is not True:
        raise RuntimeError("persisted physical step does not prove motion")
    if step_summary.get("next_origin_ready") is not True:
        raise RuntimeError("persisted physical step has no next origin")

    summary_sha=_verify_embedded_hash(
        step_summary,
        "replanned_physical_step_sha256",
        "replanned physical step summary",
    )
    previous=verify_physical_origin_receipt(previous_origin_receipt)
    next_verified=verify_physical_origin_receipt(next_origin_receipt)

    opening_id=str(step_summary.get("opening_id") or "")
    zone_id=str(step_summary.get("zone_id") or "")
    if not opening_id or not zone_id:
        raise RuntimeError("persisted physical step missing opening/zone binding")

    handoff=extract_replanned_physical_action(
        planner_payload=planner_payload,
        physical_origin_receipt=previous_origin_receipt,
        opening_id=opening_id,
    )
    embedded_handoff=step_summary.get("handoff")
    if not isinstance(embedded_handoff,Mapping):
        raise RuntimeError("persisted physical step missing complete handoff evidence")
    if dict(embedded_handoff)!=handoff:
        raise RuntimeError("persisted handoff does not match independently reconstructed handoff")
    if step_summary.get("replanned_action_handoff_sha256")!=handoff[
        "replanned_action_handoff_sha256"
    ]:
        raise RuntimeError("persisted handoff SHA does not match reconstructed handoff")

    authorization=authorize_replanned_physical_action(
        handoff,
        max_delta_pct=float(step_summary["max_delta_pct"]),
    )
    embedded_authorization=step_summary.get("authorization")
    if not isinstance(embedded_authorization,Mapping):
        raise RuntimeError(
            "persisted physical step missing complete authorization evidence"
        )
    if dict(embedded_authorization)!=authorization:
        raise RuntimeError(
            "persisted authorization does not match independently reconstructed authorization"
        )
    if (
        step_summary.get("replanned_action_authorization_sha256")
        !=authorization["replanned_action_authorization_sha256"]
    ):
        raise RuntimeError(
            "persisted authorization SHA does not match reconstructed authorization"
        )

    command_ack=step_summary.get("command_ack")
    command_request_id=str(step_summary.get("command_request_id") or "")
    feedback=step_summary.get("actuator_feedback")
    snapshot=step_summary.get("sensor_snapshot")
    if not isinstance(command_ack,Mapping):
        raise RuntimeError("persisted physical step missing complete command ACK")
    if not command_request_id:
        raise RuntimeError("persisted physical step missing command request identity")
    if not isinstance(feedback,Mapping):
        raise RuntimeError("persisted physical step missing actuator feedback")
    if not isinstance(snapshot,Mapping):
        raise RuntimeError("persisted physical step missing complete sensor snapshot")

    readiness_identity=str(
        step_summary.get("readiness_hardware_identity_sha256") or ""
    )
    origin_identity=str(
        step_summary.get("origin_hardware_identity_sha256") or ""
    )
    expected_origin_identity=str(
        previous["opening_hardware_identities"].get(opening_id) or ""
    )
    if not expected_origin_identity:
        raise RuntimeError(
            "previous physical origin lacks hardware identity for executed opening"
        )
    if origin_identity!=expected_origin_identity:
        raise RuntimeError(
            "persisted origin hardware identity does not match previous physical origin"
        )
    if readiness_identity!=origin_identity:
        raise RuntimeError(
            "persisted readiness hardware identity does not match origin identity"
        )
    if command_ack.get("hardware_identity_sha256")!=readiness_identity:
        raise RuntimeError(
            "persisted command ACK hardware identity does not match readiness identity"
        )
    if step_summary.get("command_ack_sha256")!=command_ack.get("command_ack_sha256"):
        raise RuntimeError("persisted command ACK SHA field mismatch")
    if step_summary.get("sensor_snapshot_sha256")!=snapshot.get("snapshot_sha256"):
        raise RuntimeError("persisted sensor snapshot SHA field mismatch")

    max_age=float(step_summary.get("max_origin_age_s") or 0)
    checked_at=float(step_summary.get("origin_freshness_checked_at") or 0)
    if max_age<=0 or checked_at<=0:
        raise RuntimeError("persisted physical step missing freshness gate evidence")
    opening_ts=previous["opening_observed_at"].get(opening_id)
    zone_ts=previous["zone_observed_at"].get(zone_id)
    rain_ts=previous.get("rain_observed_at")
    if opening_ts is None or zone_ts is None or rain_ts is None:
        raise RuntimeError(
            "previous physical origin lacks timestamps required for freshness verification"
        )
    reconstructed_ages={
        "opening":checked_at-float(opening_ts),
        "zone":checked_at-float(zone_ts),
        "rain":checked_at-float(rain_ts),
    }
    persisted_ages=step_summary.get("origin_evidence_age_s")
    if not isinstance(persisted_ages,Mapping):
        raise RuntimeError("persisted physical step missing origin evidence ages")
    normalized_persisted={
        str(key):float(value)
        for key,value in persisted_ages.items()
    }
    if normalized_persisted!=dict(sorted(reconstructed_ages.items())):
        raise RuntimeError(
            "persisted physical-origin evidence ages do not match source timestamps"
        )
    future=[key for key,age in reconstructed_ages.items() if age < -1.0]
    if future:
        raise RuntimeError(
            "persisted physical-origin freshness check accepted future observations"
        )
    stale=[key for key,age in reconstructed_ages.items() if age>max_age]
    if stale:
        raise RuntimeError(
            "persisted physical-origin freshness check exceeded max age"
        )

    reconstructed_next=build_replanned_physical_step_origin(
        previous_physical_origin_receipt=previous_origin_receipt,
        authorization=authorization,
        command_ack=command_ack,
        expected_request_id=command_request_id,
        feedback=feedback,
        sensor_snapshot=snapshot,
        zone_id=zone_id,
    )
    if reconstructed_next!=dict(next_origin_receipt):
        raise RuntimeError(
            "persisted next physical origin does not match independently reconstructed origin"
        )
    if (
        step_summary.get("next_physical_origin_sha256")
        !=next_verified["origin_sha256"]
    ):
        raise RuntimeError("step summary next-origin state SHA mismatch")
    if (
        step_summary.get("next_physical_origin_receipt_sha256")
        !=next_verified["receipt_sha256"]
    ):
        raise RuntimeError("step summary next-origin receipt SHA mismatch")

    payload={
        "schema_version":"0.1",
        "verification":"persisted-replanned-physical-cycle-v1",
        "status":"PASS",
        "field_transition_contract_verified":True,
        "previous_origin_sha256":previous["origin_sha256"],
        "previous_origin_receipt_sha256":previous["receipt_sha256"],
        "planner_receipt_sha256":handoff["planner_receipt_sha256"],
        "planner_step_sha256":handoff["planner_step_sha256"],
        "handoff_sha256":handoff["replanned_action_handoff_sha256"],
        "authorization_sha256":authorization[
            "replanned_action_authorization_sha256"
        ],
        "command_request_id":command_request_id,
        "command_id":str(command_ack["command_id"]),
        "command_ack_sha256":str(command_ack["command_ack_sha256"]),
        "sensor_snapshot_sha256":str(snapshot["snapshot_sha256"]),
        "step_summary_sha256":summary_sha,
        "next_origin_sha256":next_verified["origin_sha256"],
        "next_origin_receipt_sha256":next_verified["receipt_sha256"],
        "opening_id":opening_id,
        "zone_id":zone_id,
        "authorized_target_pct":float(authorization["authorized_target_pct"]),
        "origin_hardware_identity_sha256":origin_identity,
        "origin_freshness_checked_at":checked_at,
        "max_origin_age_s":max_age,
        "origin_evidence_age_s":dict(sorted(reconstructed_ages.items())),
        "measured_position_pct":float(feedback["measured_position_pct"]),
        "intervention":authorization.get("intervention"),
        "evidence_boundary":(
            "independent persisted-artifact verification of one software/field "
            "transition contract; authenticity still depends on the upstream "
            "WindowPilot hardware and sensor evidence sources"
        ),
    }
    return {
        **payload,
        "physical_cycle_verification_sha256":_sha256(payload),
    }
