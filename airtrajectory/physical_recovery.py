"""Recover a fresh physical origin after a consumed field cycle failed."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
from typing import Any, Mapping

from .physical_origin import verify_physical_origin_receipt
from .physical_origin_lease import verify_physical_origin_execution_lease


def _sha256(payload: Any) -> str:
    raw=json.dumps(
        payload,
        sort_keys=True,
        separators=(",",":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _feedback_row(feedback: Any) -> dict[str, Any]:
    if is_dataclass(feedback):
        return asdict(feedback)
    if isinstance(feedback,Mapping):
        return dict(feedback)
    raise RuntimeError("recovery position feedback is invalid")


def build_recovery_physical_origin(
    *,
    previous_origin_receipt: Mapping[str, Any],
    recovery_lease: Mapping[str, Any],
    hardware_identity_sha256: str,
    position_feedback: Any,
    sensor_snapshot: Mapping[str, Any],
    closeout_command_ack: Mapping[str, Any] | None = None,
    position_tolerance_pct: float = 1.0,
) -> dict[str, Any]:
    previous=verify_physical_origin_receipt(previous_origin_receipt)
    if not isinstance(recovery_lease,Mapping):
        raise RuntimeError("physical recovery lease is invalid")
    if recovery_lease.get("status")!="RECOVERY_REQUIRED":
        raise RuntimeError("physical recovery requires RECOVERY_REQUIRED lease")
    if (
        recovery_lease.get("physical_origin_receipt_sha256")
        !=previous["receipt_sha256"]
    ):
        raise RuntimeError("physical recovery lease/origin receipt mismatch")
    if recovery_lease.get("physical_origin_sha256")!=previous["origin_sha256"]:
        raise RuntimeError("physical recovery lease/origin state mismatch")

    opening_id=str(recovery_lease.get("opening_id") or "")
    zone_id=str(recovery_lease.get("zone_id") or "")
    if opening_id not in previous["origin"]["opening_pct"]:
        raise RuntimeError("recovery opening is missing from previous origin")
    if zone_id not in previous["origin"]["co2_ppm"]:
        raise RuntimeError("recovery zone is missing from previous origin")

    identity=str(hardware_identity_sha256 or "")
    expected_identity=str(
        previous["opening_hardware_identities"].get(opening_id) or ""
    )
    if not expected_identity:
        raise RuntimeError(
            "previous physical origin lacks hardware identity for recovery opening"
        )
    if identity!=expected_identity:
        raise RuntimeError(
            "recovery hardware identity does not match previous physical origin"
        )

    feedback=_feedback_row(position_feedback)
    measured=feedback.get("measured_position_pct")
    if measured is None:
        measured=feedback.get("position_pct")
    if measured is None:
        raise RuntimeError("recovery position feedback is not measured")
    if feedback.get("measured") is False:
        raise RuntimeError("recovery position feedback is explicitly unmeasured")
    position=float(measured)
    position_ts=float(feedback.get("timestamp") or 0)
    tolerance=float(position_tolerance_pct)
    if not 0<tolerance<=1.0:
        raise ValueError("position_tolerance_pct must be within (0,1]")
    if position_ts<=0:
        raise RuntimeError("recovery position feedback timestamp is invalid")
    if not 0<=position<=100:
        raise RuntimeError("recovery position feedback is outside [0,100]")
    if position>tolerance:
        raise RuntimeError(
            "recovery position is not safely closed within tolerance"
        )

    if not isinstance(sensor_snapshot,Mapping):
        raise RuntimeError("physical recovery sensor snapshot is invalid")
    if sensor_snapshot.get("fresh_after_action") is not True:
        raise RuntimeError("physical recovery sensors are not fresh after position")
    provided_snapshot_sha=str(sensor_snapshot.get("snapshot_sha256") or "")
    snapshot_payload={
        key:value
        for key,value in sensor_snapshot.items()
        if key!="snapshot_sha256"
    }
    if provided_snapshot_sha!=_sha256(snapshot_payload):
        raise RuntimeError("physical recovery sensor snapshot SHA-256 mismatch")
    co2_ts=float(sensor_snapshot.get("co2_timestamp") or 0)
    rain_ts=float(sensor_snapshot.get("rain_timestamp") or 0)
    if co2_ts<=position_ts or rain_ts<=position_ts:
        raise RuntimeError(
            "physical recovery sensors are not newer than recovery position"
        )
    co2=float(sensor_snapshot["co2_ppm"])
    if co2<0:
        raise RuntimeError("physical recovery CO2 must be non-negative")
    rain=bool(sensor_snapshot["rain"])

    closeout_ack_sha=None
    closeout_request_id=None
    closeout_command_id=None
    if closeout_command_ack is not None:
        if not isinstance(closeout_command_ack,Mapping):
            raise RuntimeError("physical recovery closeout acknowledgement is invalid")
        ack_payload={
            key:value
            for key,value in closeout_command_ack.items()
            if key!="command_ack_sha256"
        }
        closeout_ack_sha=str(
            closeout_command_ack.get("command_ack_sha256") or ""
        )
        if closeout_ack_sha!=_sha256(ack_payload):
            raise RuntimeError(
                "physical recovery closeout acknowledgement SHA-256 mismatch"
            )
        if closeout_command_ack.get("receipt")!="windowpilot-command-ack-v2":
            raise RuntimeError(
                "physical recovery closeout requires WindowPilot ACK v2"
            )
        if closeout_command_ack.get("accepted") is not True:
            raise RuntimeError("physical recovery closeout was not accepted")
        if closeout_command_ack.get("simulated") is not False:
            raise RuntimeError("physical recovery closeout acknowledgement is simulated")
        if closeout_command_ack.get("action")!="close":
            raise RuntimeError("physical recovery acknowledgement is not close")
        if float(closeout_command_ack.get("target_pct") or 0)!=0.0:
            raise RuntimeError("physical recovery closeout target is not 0%")
        if closeout_command_ack.get("hardware_identity_sha256")!=identity:
            raise RuntimeError("physical recovery closeout hardware identity mismatch")
        closeout_request_id=str(closeout_command_ack.get("request_id") or "")
        closeout_command_id=str(closeout_command_ack.get("command_id") or "")
        if not closeout_request_id or not closeout_command_id:
            raise RuntimeError(
                "physical recovery closeout lacks request/command identity"
            )

    origin={
        "co2_ppm":dict(previous["origin"]["co2_ppm"]),
        "opening_pct":dict(previous["origin"]["opening_pct"]),
        "scalar_values":dict(previous["origin"]["scalar_values"]),
    }
    origin["co2_ppm"][zone_id]=co2
    origin["opening_pct"][opening_id]=position
    origin["scalar_values"]["rain"]=1.0 if rain else 0.0
    normalized={
        "co2_ppm":dict(sorted((k,float(v)) for k,v in origin["co2_ppm"].items())),
        "opening_pct":dict(
            sorted((k,float(v)) for k,v in origin["opening_pct"].items())
        ),
        "scalar_values":dict(
            sorted((k,float(v)) for k,v in origin["scalar_values"].items())
        ),
    }
    measured_zones=[zone_id]
    measured_openings=[opening_id]
    inherited_zones=sorted(set(normalized["co2_ppm"])-{zone_id})
    inherited_openings=sorted(set(normalized["opening_pct"])-{opening_id})

    payload={
        "schema_version":"0.1",
        "source":"windowpilot-recovery-observation-v1",
        "zone_id":zone_id,
        "opening_id":opening_id,
        "origin":normalized,
        "parent_physical_origin_sha256":previous["origin_sha256"],
        "parent_physical_origin_receipt_sha256":previous["receipt_sha256"],
        "recovery_lease_sha256":str(recovery_lease["lease_sha256"]),
        "sensor_snapshot_sha256":provided_snapshot_sha,
        "recovery_position_pct":position,
        "recovery_position_timestamp":position_ts,
        "closeout_command_ack_sha256":closeout_ack_sha,
        "closeout_request_id":closeout_request_id,
        "closeout_command_id":closeout_command_id,
        "opening_hardware_identities":{opening_id:identity},
        "opening_observed_at":{opening_id:position_ts},
        "zone_observed_at":{zone_id:co2_ts},
        "rain_observed_at":rain_ts,
        "measured_zones":measured_zones,
        "measured_openings":measured_openings,
        "inherited_zones":inherited_zones,
        "inherited_openings":inherited_openings,
        "whole_home_physically_measured":(
            not inherited_zones and not inherited_openings
        ),
        "evidence_boundary":(
            "recovery origin re-establishes one opening/zone from live measured "
            "closed position plus fresh CO2/rain after a consumed failed cycle; "
            "all other state is inherited and prior cumulative coverage is reset"
        ),
    }
    return {
        **payload,
        "origin_sha256":_sha256(normalized),
        "physical_origin_receipt_sha256":_sha256(payload),
    }
