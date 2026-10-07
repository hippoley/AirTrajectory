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
    steps=receipt.get("steps")
    if not isinstance(steps,list) or len(steps)!=1:
        raise RuntimeError(
            "physical-origin replan handoff requires exactly one planning step"
        )
    step=steps[0]
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
    current=float(verified_origin["origin"]["opening_pct"][target_opening])
    payload={
        "schema_version":"0.1",
        "handoff":"physical-origin-replan-action-v1",
        "opening_id":target_opening,
        "current_measured_pct":current,
        "planned_target_pct":target,
        "planned_delta_pct":target-current,
        "selected_label":str(step.get("selected_label") or ""),
        "objective_score":float(step.get("objective_score")),
        "physical_origin_sha256":verified_origin["origin_sha256"],
        "physical_origin_receipt_sha256":verified_origin["receipt_sha256"],
        "planner_receipt_sha256":str(receipt.get("receipt_sha256") or ""),
        "planner_step_sha256":str(step.get("step_sha256") or ""),
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
    delta=planned-current
    bounded_delta=max(-max_delta,min(max_delta,delta))
    authorized=max(0.0,min(100.0,current+bounded_delta))

    result={
        "schema_version":"0.1",
        "authorization":"bounded-replanned-physical-action-v1",
        "opening_id":str(handoff["opening_id"]),
        "current_measured_pct":current,
        "planned_target_pct":planned,
        "planned_delta_pct":delta,
        "max_delta_pct":max_delta,
        "authorized_target_pct":authorized,
        "authorized_delta_pct":authorized-current,
        "planner_action_fully_authorized":abs(authorized-planned)<=1e-9,
        "intervention":(
            None
            if abs(authorized-planned)<=1e-9
            else "REPLANNED_ACTION_BOUNDED_BY_FIELD_RAMP_LIMIT"
        ),
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
