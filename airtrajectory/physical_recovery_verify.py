"""Independent verification for persisted physical recovery artifacts."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .physical_origin import verify_physical_origin_receipt


def _sha256(payload: Any) -> str:
    raw=json.dumps(
        payload,
        sort_keys=True,
        separators=(",",":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _verify_hash(payload: Mapping[str, Any], field: str, label: str) -> str:
    provided=str(payload.get(field) or "")
    calculated=_sha256({
        key:value for key,value in payload.items() if key!=field
    })
    if provided!=calculated:
        raise RuntimeError(f"{label} SHA-256 mismatch")
    return provided


def verify_persisted_physical_recovery(
    *,
    previous_origin_receipt: Mapping[str, Any],
    recovered_lease: Mapping[str, Any],
    recovery_summary: Mapping[str, Any],
    recovery_origin_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    previous=verify_physical_origin_receipt(previous_origin_receipt)
    recovered=verify_physical_origin_receipt(recovery_origin_receipt)
    if recovered["source"]!="windowpilot-recovery-observation-v1":
        raise RuntimeError("persisted recovery origin has wrong source")

    if not isinstance(recovered_lease,Mapping):
        raise RuntimeError("persisted recovered lease is invalid")
    lease_sha=_verify_hash(
        recovered_lease,
        "lease_sha256",
        "persisted recovered execution lease",
    )
    if recovered_lease.get("lease")!="physical-origin-execution-lease-v1":
        raise RuntimeError("persisted recovery lease contract is unsupported")
    if recovered_lease.get("status")!="RECOVERED":
        raise RuntimeError("persisted recovery lease is not RECOVERED")
    pre_recovery_lease_sha=str(
        recovered_lease.get("recovery_required_lease_sha256") or ""
    )
    if len(pre_recovery_lease_sha)!=64:
        raise RuntimeError("persisted recovery lease lacks pre-recovery SHA")

    summary_sha=_verify_hash(
        recovery_summary,
        "recovery_summary_sha256",
        "persisted physical recovery summary",
    )
    if recovery_summary.get("status")!="PASS":
        raise RuntimeError("persisted physical recovery summary is not PASS")
    if recovery_summary.get("workflow")!="recover-physical-origin-v1":
        raise RuntimeError("persisted physical recovery workflow is unsupported")

    if recovered_lease.get("physical_origin_receipt_sha256")!=previous["receipt_sha256"]:
        raise RuntimeError("persisted recovery lease parent receipt mismatch")
    if recovered_lease.get("physical_origin_sha256")!=previous["origin_sha256"]:
        raise RuntimeError("persisted recovery lease parent state mismatch")
    if recovered_lease.get("recovery_origin_receipt_sha256")!=recovered["receipt_sha256"]:
        raise RuntimeError("persisted recovery lease next receipt mismatch")
    if recovered_lease.get("recovery_origin_sha256")!=recovered["origin_sha256"]:
        raise RuntimeError("persisted recovery lease next state mismatch")
    if recovered_lease.get("recovery_summary_sha256")!=summary_sha:
        raise RuntimeError("persisted recovery lease summary hash mismatch")

    raw_origin=recovery_origin_receipt
    if raw_origin.get("parent_physical_origin_receipt_sha256")!=previous["receipt_sha256"]:
        raise RuntimeError("recovery origin parent receipt mismatch")
    if raw_origin.get("parent_physical_origin_sha256")!=previous["origin_sha256"]:
        raise RuntimeError("recovery origin parent state mismatch")
    if raw_origin.get("recovery_lease_sha256")!=pre_recovery_lease_sha:
        raise RuntimeError("recovery origin does not bind pre-recovery lease")

    if recovery_summary.get("physical_origin_receipt_sha256")!=previous["receipt_sha256"]:
        raise RuntimeError("recovery summary parent receipt mismatch")
    if recovery_summary.get("execution_lease_sha256")!=pre_recovery_lease_sha:
        raise RuntimeError("recovery summary does not bind pre-recovery lease")
    if recovery_summary.get("recovery_origin_receipt_sha256")!=recovered["receipt_sha256"]:
        raise RuntimeError("recovery summary next receipt mismatch")
    if recovery_summary.get("recovery_origin_sha256")!=recovered["origin_sha256"]:
        raise RuntimeError("recovery summary next state mismatch")

    opening_id=str(recovered_lease.get("opening_id") or "")
    zone_id=str(recovered_lease.get("zone_id") or "")
    if raw_origin.get("opening_id")!=opening_id:
        raise RuntimeError("recovery origin opening mismatch")
    if raw_origin.get("zone_id")!=zone_id:
        raise RuntimeError("recovery origin zone mismatch")
    if recovery_summary.get("opening_id")!=opening_id:
        raise RuntimeError("recovery summary opening mismatch")
    if recovery_summary.get("zone_id")!=zone_id:
        raise RuntimeError("recovery summary zone mismatch")

    position=recovery_summary.get("position_feedback")
    if not isinstance(position,Mapping):
        raise RuntimeError("recovery summary lacks position feedback")
    position_pct=position.get("measured_position_pct")
    if position_pct is None:
        position_pct=position.get("position_pct")
    position_ts=float(position.get("timestamp") or 0)
    if position_pct is None or position_ts<=0:
        raise RuntimeError("recovery summary position feedback is invalid")
    if abs(float(position_pct)-float(raw_origin["recovery_position_pct"]))>1e-9:
        raise RuntimeError("recovery summary/origin position mismatch")
    if position_ts!=float(raw_origin["recovery_position_timestamp"]):
        raise RuntimeError("recovery summary/origin position timestamp mismatch")

    snapshot=recovery_summary.get("sensor_snapshot")
    if not isinstance(snapshot,Mapping):
        raise RuntimeError("recovery summary lacks sensor snapshot")
    snapshot_sha=_verify_hash(
        snapshot,
        "snapshot_sha256",
        "persisted recovery sensor snapshot",
    )
    if snapshot_sha!=raw_origin.get("sensor_snapshot_sha256"):
        raise RuntimeError("recovery summary/origin sensor snapshot mismatch")
    if float(snapshot.get("co2_timestamp") or 0)<=position_ts:
        raise RuntimeError("recovery CO2 is not newer than recovered position")
    if float(snapshot.get("rain_timestamp") or 0)<=position_ts:
        raise RuntimeError("recovery rain is not newer than recovered position")

    motion=bool(recovery_summary.get("motion_performed"))
    ack=recovery_summary.get("closeout_command_ack")
    if motion:
        if not isinstance(ack,Mapping):
            raise RuntimeError("motion recovery lacks closeout acknowledgement")
        ack_sha=_verify_hash(
            ack,
            "command_ack_sha256",
            "persisted recovery closeout acknowledgement",
        )
        if ack_sha!=raw_origin.get("closeout_command_ack_sha256"):
            raise RuntimeError("recovery closeout acknowledgement hash mismatch")
        if ack.get("receipt")!="windowpilot-command-ack-v2":
            raise RuntimeError("recovery closeout acknowledgement is not ACK v2")
        if ack.get("action")!="close":
            raise RuntimeError("recovery closeout acknowledgement is not close")
        if ack.get("request_id")!=raw_origin.get("closeout_request_id"):
            raise RuntimeError("recovery closeout request_id mismatch")
        if ack.get("command_id")!=raw_origin.get("closeout_command_id"):
            raise RuntimeError("recovery closeout command_id mismatch")
    else:
        if ack is not None:
            raise RuntimeError(
                "zero-motion recovery unexpectedly contains closeout acknowledgement"
            )
        if raw_origin.get("closeout_command_ack_sha256") is not None:
            raise RuntimeError(
                "zero-motion recovery origin unexpectedly claims closeout command"
            )

    payload={
        "schema_version":"0.1",
        "verification":"physical-recovery-verification-v1",
        "status":"PASS",
        "previous_origin_receipt_sha256":previous["receipt_sha256"],
        "pre_recovery_lease_sha256":pre_recovery_lease_sha,
        "recovered_lease_sha256":lease_sha,
        "recovery_summary_sha256":summary_sha,
        "recovery_origin_receipt_sha256":recovered["receipt_sha256"],
        "recovery_origin_sha256":recovered["origin_sha256"],
        "opening_id":opening_id,
        "zone_id":zone_id,
        "motion_performed":motion,
        "evidence_boundary":(
            "independent persisted-artifact verification of a recovery transition; "
            "does not establish live field execution beyond the supplied artifacts"
        ),
    }
    return {
        **payload,
        "physical_recovery_verification_sha256":_sha256(payload),
    }
