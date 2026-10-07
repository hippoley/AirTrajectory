"""Bind a real-ContamX replan to the next bounded physical action."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .physical_origin import verify_physical_origin_receipt


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _verify_embedded_sha(payload: Mapping[str, Any], field: str, label: str) -> str:
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


def extract_replanned_physical_action(
    *,
    planner_payload: Mapping[str, Any],
    physical_origin_receipt: Mapping[str, Any],
    opening_id: str,
) -> dict[str, Any]:
    """Extract one exact opening action from a physical-origin ContamX replan."""
    if not isinstance(planner_payload, Mapping):
        raise ValueError("planner_payload must be an object")
    verified_origin=verify_physical_origin_receipt(physical_origin_receipt)

    if planner_payload.get("marker")!="REAL_CONTAM_REPLAN_FROM_PHYSICAL_ORIGIN":
        raise RuntimeError(
            "planner payload is not a real-ContamX replan from physical origin"
        )
    if planner_payload.get("physical_origin_consumed") is not True:
        raise RuntimeError("planner payload did not consume a physical origin")

    planner_origin=planner_payload.get("physical_origin_evidence") or {}
    if not isinstance(planner_origin,Mapping):
        raise RuntimeError("planner payload missing physical-origin evidence")
    if planner_origin.get("origin_sha256")!=verified_origin["origin_sha256"]:
        raise RuntimeError("planner physical-origin state hash mismatch")
    if planner_origin.get("receipt_sha256")!=verified_origin["receipt_sha256"]:
        raise RuntimeError("planner physical-origin receipt hash mismatch")

    receipt=planner_payload.get("receipt")
    if not isinstance(receipt,Mapping):
        raise RuntimeError("planner payload missing closed-loop receipt")
    receipt_sha=_verify_embedded_sha(
        receipt,
        "receipt_sha256",
        "planner closed-loop receipt",
    )
    if planner_payload.get("physics_fidelity")!="CONTAM":
        raise RuntimeError("physical replan handoff requires CONTAM planner fidelity")
    steps=receipt.get("steps")
    if not isinstance(steps,list) or len(steps)!=1:
        raise RuntimeError(
            "physical-origin replan handoff requires exactly one planning step"
        )
    step=steps[0]
    step_sha=_verify_embedded_sha(
        step,
        "step_sha256",
        "planner closed-loop step",
    )
    if step.get("origin_sha256")!=verified_origin["origin_sha256"]:
        raise RuntimeError("planner step origin does not match physical origin")
    if receipt.get("initial_origin_sha256")!=verified_origin["origin_sha256"]:
        raise RuntimeError("planner initial origin does not match physical origin")

    target_opening=str(opening_id or "")
    actions=[
        action
        for action in (step.get("selected_actions") or [])
        if isinstance(action,Mapping)
        and action.get("kind")=="opening"
        and str(action.get("opening_id") or "")==target_opening
    ]
    if len(actions)!=1:
        raise RuntimeError(
            f"expected exactly one replanned opening action for {target_opening}"
        )

    action=actions[0]
    target=float(action["target_pct"])
    if not 0<=target<=100:
        raise RuntimeError("replanned opening target is outside [0,100]")
    current=float(verified_origin["origin"]["opening_pct"][target_opening])
    scalars=verified_origin["origin"].get("scalar_values") or {}
    if "rain" not in scalars:
        raise RuntimeError("physical origin lacks measured rain state")
    rain_value=float(scalars["rain"])
    if rain_value not in (0.0,1.0):
        raise RuntimeError("physical origin rain state must be binary")
    payload={
        "schema_version":"0.1",
        "handoff":"physical-origin-replan-action-v1",
        "opening_id":target_opening,
        "current_measured_pct":current,
        "planned_target_pct":target,
        "planned_delta_pct":target-current,
        "current_rain":bool(rain_value),
        "selected_label":str(step.get("selected_label") or ""),
        "objective_score":float(step.get("objective_score")),
        "physical_origin_sha256":verified_origin["origin_sha256"],
        "physical_origin_receipt_sha256":verified_origin["receipt_sha256"],
        "planner_receipt_sha256":receipt_sha,
        "planner_step_sha256":step_sha,
        "planner_physics_fidelity":str(planner_payload.get("physics_fidelity") or ""),
        "planner_evidence_boundary":str(
            planner_payload.get("evidence_boundary") or ""
        ),
    }
    return {
        **payload,
        "replanned_action_handoff_sha256":_sha256(payload),
    }


def authorize_replanned_physical_action(
    handoff: Mapping[str, Any],
    *,
    max_delta_pct: float,
) -> dict[str, Any]:
    """Bound the next field command around the measured physical origin.

    This deliberately does not assume that a successful first-contact probe
    authorizes a full-range planner jump.
    """
    if not isinstance(handoff,Mapping):
        raise ValueError("handoff must be an object")
    provided=str(handoff.get("replanned_action_handoff_sha256") or "")
    payload={
        key:value
        for key,value in handoff.items()
        if key!="replanned_action_handoff_sha256"
    }
    if provided!=_sha256(payload):
        raise RuntimeError("replanned action handoff SHA-256 mismatch")

    max_delta=float(max_delta_pct)
    if not 0 < max_delta <= 100:
        raise ValueError("max_delta_pct must be within (0,100]")

    current=float(handoff["current_measured_pct"])
    planned=float(handoff["planned_target_pct"])
    rain=handoff.get("current_rain")
    if rain is None:
        raise RuntimeError("replanned action handoff lacks rain safety state")
    delta=planned-current
    if bool(rain) and planned>0:
        authorized=0.0
        intervention="RAIN_SAFE_CLOSE"
    else:
        bounded_delta=max(-max_delta,min(max_delta,delta))
        authorized=max(0.0,min(100.0,current+bounded_delta))
        intervention=(
            None
            if abs(authorized-planned)<=1e-9
            else "REPLANNED_ACTION_BOUNDED_BY_FIELD_RAMP_LIMIT"
        )

    result={
        "schema_version":"0.1",
        "authorization":"bounded-replanned-physical-action-v1",
        "opening_id":str(handoff["opening_id"]),
        "current_measured_pct":current,
        "planned_target_pct":planned,
        "planned_delta_pct":delta,
        "current_rain":bool(rain),
        "max_delta_pct":max_delta,
        "authorized_target_pct":authorized,
        "authorized_delta_pct":authorized-current,
        "planner_action_fully_authorized":abs(authorized-planned)<=1e-9,
        "intervention":intervention,
        "replanned_action_handoff_sha256":provided,
        "physical_origin_sha256":str(handoff["physical_origin_sha256"]),
        "physical_origin_receipt_sha256":str(
            handoff["physical_origin_receipt_sha256"]
        ),
        "planner_receipt_sha256":str(handoff["planner_receipt_sha256"]),
        "planner_step_sha256":str(handoff["planner_step_sha256"]),
        "evidence_boundary":(
            "authorization bounds only the next physical command around the "
            "measured origin; it does not claim that the command has executed"
        ),
    }
    return {
        **result,
        "replanned_action_authorization_sha256":_sha256(result),
    }


def build_replanned_physical_step_origin(
    *,
    previous_physical_origin_receipt: Mapping[str, Any],
    authorization: Mapping[str, Any],
    command_ack: Mapping[str, Any],
    feedback: Mapping[str, Any],
    sensor_snapshot: Mapping[str, Any],
    zone_id: str,
) -> dict[str, Any]:
    """Build the next controller origin after an executed replanned field step."""
    previous=verify_physical_origin_receipt(previous_physical_origin_receipt)

    auth_hash=str(
        authorization.get("replanned_action_authorization_sha256") or ""
    )
    auth_payload={
        key:value
        for key,value in authorization.items()
        if key!="replanned_action_authorization_sha256"
    }
    if auth_hash!=_sha256(auth_payload):
        raise RuntimeError("replanned action authorization SHA-256 mismatch")
    if authorization.get("physical_origin_sha256")!=previous["origin_sha256"]:
        raise RuntimeError(
            "replanned action authorization does not reference previous physical origin"
        )
    if (
        authorization.get("physical_origin_receipt_sha256")
        !=previous["receipt_sha256"]
    ):
        raise RuntimeError(
            "replanned action authorization receipt lineage mismatch"
        )

    opening_id=str(authorization.get("opening_id") or "")
    if opening_id not in previous["origin"]["opening_pct"]:
        raise RuntimeError("authorized opening is not present in previous origin")
    zone=str(zone_id or "")
    if zone not in previous["origin"]["co2_ppm"]:
        raise RuntimeError("measured zone is not present in previous origin")

    expected_target=float(authorization["authorized_target_pct"])

    if not isinstance(command_ack,Mapping):
        raise RuntimeError("replanned physical step missing command acknowledgement")
    provided_ack_hash=str(command_ack.get("command_ack_sha256") or "")
    ack_payload={
        key:value
        for key,value in command_ack.items()
        if key!="command_ack_sha256"
    }
    if provided_ack_hash!=_sha256(ack_payload):
        raise RuntimeError("replanned physical command acknowledgement SHA-256 mismatch")
    if command_ack.get("accepted") is not True:
        raise RuntimeError("replanned physical command was not accepted")
    if command_ack.get("simulated") is not False:
        raise RuntimeError("replanned physical command acknowledgement is simulated")
    if command_ack.get("physical_write_ready") is not True:
        raise RuntimeError("replanned physical command lacks write authorization")
    if str(command_ack.get("opening_id") or "") not in ("",opening_id):
        raise RuntimeError("replanned physical command opening mismatch")
    ack_target=command_ack.get("target_pct")
    if ack_target is None or abs(float(ack_target)-expected_target)>1e-9:
        raise RuntimeError("replanned physical command target mismatch")

    if not isinstance(feedback,Mapping):
        raise RuntimeError("replanned physical step missing actuator feedback")
    if str(feedback.get("actuator_id") or "")!=opening_id:
        raise RuntimeError("replanned actuator feedback opening mismatch")
    measured=feedback.get("measured_position_pct")
    if measured is None:
        raise RuntimeError("replanned actuator feedback is not measured")
    measured=float(measured)
    feedback_ts=float(feedback.get("timestamp") or 0)
    quality=str(feedback.get("quality") or "").lower()
    if not 0<=measured<=100 or feedback_ts<=0:
        raise RuntimeError("replanned actuator feedback is invalid")
    if "measured" not in quality and "encoder" not in quality:
        raise RuntimeError("replanned actuator feedback quality is not measured")
    position_tolerance=1.0
    if abs(measured-expected_target)>position_tolerance:
        raise RuntimeError(
            "replanned actuator feedback did not reach authorized target "
            f"within {position_tolerance:.1f}%"
        )

    if not isinstance(sensor_snapshot,Mapping):
        raise RuntimeError("replanned physical step missing sensor snapshot")
    if sensor_snapshot.get("fresh_after_action") is not True:
        raise RuntimeError("replanned physical sensor snapshot is not fresh after action")
    snapshot_hash=str(sensor_snapshot.get("snapshot_sha256") or "")
    snapshot_payload={
        key:value
        for key,value in sensor_snapshot.items()
        if key!="snapshot_sha256"
    }
    if snapshot_hash!=_sha256(snapshot_payload):
        raise RuntimeError("replanned physical sensor snapshot SHA-256 mismatch")

    co2_ts=float(sensor_snapshot.get("co2_timestamp") or 0)
    rain_ts=float(sensor_snapshot.get("rain_timestamp") or 0)
    if co2_ts<=feedback_ts or rain_ts<=feedback_ts:
        raise RuntimeError(
            "replanned physical sensor snapshot is not newer than actuator feedback"
        )

    co2=float(sensor_snapshot["co2_ppm"])
    rain=bool(sensor_snapshot["rain"])
    origin={
        "co2_ppm":dict(previous["origin"]["co2_ppm"]),
        "opening_pct":dict(previous["origin"]["opening_pct"]),
        "scalar_values":dict(previous["origin"]["scalar_values"]),
    }
    origin["co2_ppm"][zone]=co2
    origin["opening_pct"][opening_id]=measured
    origin["scalar_values"]["rain"]=1.0 if rain else 0.0
    normalized_origin={
        "co2_ppm":dict(sorted((k,float(v)) for k,v in origin["co2_ppm"].items())),
        "opening_pct":dict(
            sorted((k,float(v)) for k,v in origin["opening_pct"].items())
        ),
        "scalar_values":dict(
            sorted((k,float(v)) for k,v in origin["scalar_values"].items())
        ),
    }

    prior_measured_zones=set(previous["measured_zones"])
    prior_measured_openings=set(previous["measured_openings"])
    prior_measured_zones.add(zone)
    prior_measured_openings.add(opening_id)
    all_zones=set(normalized_origin["co2_ppm"])
    all_openings=set(normalized_origin["opening_pct"])

    payload={
        "schema_version":"0.1",
        "source":"windowpilot-replanned-physical-step-v1",
        "origin":normalized_origin,
        "parent_physical_origin_sha256":previous["origin_sha256"],
        "parent_physical_origin_receipt_sha256":previous["receipt_sha256"],
        "replanned_action_authorization_sha256":auth_hash,
        "command_ack_sha256":provided_ack_hash,
        "sensor_snapshot_sha256":snapshot_hash,
        "opening_id":opening_id,
        "zone_id":zone,
        "measured_position_pct":measured,
        "actuator_feedback_timestamp":feedback_ts,
        "measured_zones":sorted(prior_measured_zones),
        "measured_openings":sorted(prior_measured_openings),
        "inherited_zones":sorted(all_zones-prior_measured_zones),
        "inherited_openings":sorted(all_openings-prior_measured_openings),
        "whole_home_physically_measured":(
            all_zones<=prior_measured_zones
            and all_openings<=prior_measured_openings
        ),
        "evidence_boundary":(
            "origin refreshed from one bounded replanned physical action plus "
            "fresh post-action measured CO2/rain; untouched state remains inherited"
        ),
    }
    return {
        **payload,
        "origin_sha256":_sha256(normalized_origin),
        "physical_origin_receipt_sha256":_sha256(payload),
    }
