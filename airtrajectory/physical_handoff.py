"""Planner -> bounded physical first-contact handoff contracts.

This module deliberately does not turn a simulation target into unrestricted
hardware authority. It binds a closed-loop selected action to the existing
WindowPilot tau0 safety envelope and emits an auditable reconciliation receipt.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def extract_closed_loop_opening_action(
    closed_loop_payload: Mapping[str, Any],
    *,
    step_index: int,
    opening_id: str,
) -> dict[str, Any]:
    if not isinstance(closed_loop_payload, Mapping):
        raise ValueError("closed-loop payload must be an object")
    receipt = closed_loop_payload.get("receipt")
    if not isinstance(receipt, Mapping):
        raise ValueError("closed-loop payload missing receipt")
    steps = receipt.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("closed-loop receipt contains no steps")
    if step_index < 0 or step_index >= len(steps):
        raise ValueError("closed-loop step_index out of range")
    step = steps[step_index]
    actions = step.get("selected_actions")
    if not isinstance(actions, list):
        raise ValueError("closed-loop step missing selected_actions")
    matches = [
        action
        for action in actions
        if isinstance(action, Mapping)
        and action.get("kind") == "opening"
        and str(action.get("opening_id") or "") == str(opening_id)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"closed-loop step must contain exactly one opening action for {opening_id}"
        )
    action = matches[0]
    target = float(action["target_pct"])
    if target < 0 or target > 100:
        raise ValueError("closed-loop opening target_pct outside [0,100]")
    payload = {
        "schema_version": "0.1",
        "source": "real-contam-closed-loop-receipt",
        "closed_loop_receipt_sha256": str(receipt.get("receipt_sha256") or ""),
        "step_index": int(step_index),
        "step_sha256": str(step.get("step_sha256") or ""),
        "selected_label": str(step.get("selected_label") or ""),
        "opening_id": str(opening_id),
        "planned_target_pct": target,
        "predicted_observation": dict(step.get("observation") or {}),
    }
    return {
        **payload,
        "planner_handoff_sha256": _sha256(payload),
    }


def authorize_tau0_from_planner(
    planner_handoff: Mapping[str, Any],
    *,
    acceptance_policy: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(planner_handoff, Mapping):
        raise ValueError("planner_handoff must be an object")
    if not isinstance(acceptance_policy, Mapping):
        raise ValueError("acceptance_policy must be an object")
    planned = float(planner_handoff["planned_target_pct"])
    if planned <= 0:
        raise RuntimeError(
            "planner action does not request positive opening; no tau0 Reality Delta authorized"
        )
    requested = float(acceptance_policy["requested_excursion_pct"])
    max_first = float(acceptance_policy["max_first_excursion_pct"])
    if not 0 < requested <= 5:
        raise RuntimeError("commissioning requested excursion must be within (0,5]")
    if not 0 < max_first <= 5:
        raise RuntimeError("commissioning max first excursion must be within (0,5]")

    authorized = min(planned, requested, max_first, 5.0)
    intervention = (
        None
        if abs(authorized - planned) <= 1e-9
        else "FIRST_CONTACT_BOUNDED_TO_COMMISSIONED_EXCURSION"
    )
    payload = {
        "schema_version": "0.1",
        "authorization": "windowpilot-first-contact-v1",
        "opening_id": str(planner_handoff["opening_id"]),
        "planned_target_pct": planned,
        "authorized_target_pct": authorized,
        "max_physical_first_contact_pct": 5.0,
        "commissioned_requested_excursion_pct": requested,
        "commissioned_max_first_excursion_pct": max_first,
        "intervention": intervention,
        "planner_handoff_sha256": str(
            planner_handoff.get("planner_handoff_sha256") or ""
        ),
        "planner_action_fully_authorized": intervention is None,
    }
    return {
        **payload,
        "physical_authorization_sha256": _sha256(payload),
    }


def build_physical_handoff_reconcile(
    *,
    planner_handoff: Mapping[str, Any],
    authorization: Mapping[str, Any],
    trajectory_step: Mapping[str, Any],
    zone_id: str | None = None,
) -> dict[str, Any]:
    feedback_rows = trajectory_step.get("actuator_feedback")
    if not isinstance(feedback_rows, list) or len(feedback_rows) != 1:
        raise ValueError("physical trajectory step must have exactly one actuator feedback")
    feedback = feedback_rows[0]
    measured = feedback.get("measured_position_pct")
    if measured is None:
        raise RuntimeError("physical handoff requires measured actuator position")
    measured = float(measured)

    pre = trajectory_step.get("observation") or {}
    post = trajectory_step.get("next_observation") or {}
    pre_co2 = pre.get("co2_ppm")
    post_co2 = post.get("co2_ppm")
    predicted = planner_handoff.get("predicted_observation") or {}
    predicted_co2 = None
    if zone_id is not None:
        by_zone = predicted.get("co2_ppm")
        if isinstance(by_zone, Mapping) and zone_id in by_zone:
            predicted_co2 = float(by_zone[zone_id])

    authorized = float(authorization["authorized_target_pct"])
    position_error = measured - authorized
    payload = {
        "schema_version": "0.1",
        "reconcile": "sim-to-physical-first-contact-v1",
        "opening_id": str(planner_handoff["opening_id"]),
        "selected_label": str(planner_handoff.get("selected_label") or ""),
        "planned_target_pct": float(planner_handoff["planned_target_pct"]),
        "authorized_target_pct": authorized,
        "measured_position_pct": measured,
        "measured_minus_authorized_pct": round(position_error, 6),
        "planner_action_fully_executed": (
            bool(authorization.get("planner_action_fully_authorized"))
            and abs(position_error) <= 1.0
        ),
        "physical_intervention": authorization.get("intervention"),
        "pre_action_co2_ppm": (
            None if pre_co2 is None else float(pre_co2)
        ),
        "post_action_co2_ppm": (
            None if post_co2 is None else float(post_co2)
        ),
        "measured_co2_delta_ppm": (
            None
            if pre_co2 is None or post_co2 is None
            else round(float(post_co2) - float(pre_co2), 6)
        ),
        "predicted_zone_id": zone_id,
        "predicted_zone_co2_ppm": predicted_co2,
        "measured_minus_predicted_zone_co2_ppm": (
            None
            if predicted_co2 is None or post_co2 is None
            else round(float(post_co2) - predicted_co2, 6)
        ),
        "planner_handoff_sha256": str(
            planner_handoff.get("planner_handoff_sha256") or ""
        ),
        "physical_authorization_sha256": str(
            authorization.get("physical_authorization_sha256") or ""
        ),
        "evidence_boundary": (
            "bounded first-contact physical handoff; planner target may be safety-limited "
            "and therefore is not claimed as full closed-loop field execution"
        ),
    }
    return {
        **payload,
        "physical_reconcile_sha256": _sha256(payload),
    }
