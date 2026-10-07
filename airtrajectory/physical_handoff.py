"""Planner -> bounded physical first-contact handoff contracts.

This module deliberately does not turn a simulation target into unrestricted
hardware authority. It binds a closed-loop selected action to the existing
WindowPilot tau0 safety envelope and emits an auditable reconciliation receipt.
"""
from __future__ import annotations

import hashlib
import json
import uuid
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



def _verify_command_ack(
    ack: Mapping[str, Any],
    *,
    expected_target: float,
    expected_scope_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(ack, Mapping):
        raise RuntimeError("physical handoff missing command acknowledgement")
    provided = str(ack.get("command_ack_sha256") or "")
    payload = {
        key: value
        for key, value in ack.items()
        if key != "command_ack_sha256"
    }
    if provided != _sha256(payload):
        raise RuntimeError("physical command acknowledgement SHA-256 mismatch")
    contract=str(ack.get("receipt") or "")
    if contract not in {
        "windowpilot-command-ack-v1",
        "windowpilot-command-ack-v2",
    }:
        raise RuntimeError("physical command acknowledgement contract is unsupported")
    if contract=="windowpilot-command-ack-v2":
        try:
            uuid.UUID(str(ack.get("request_id") or ""))
            uuid.UUID(str(ack.get("command_id") or ""))
            ack_scope_raw=ack.get("idempotency_scope_id")
            ack_scope=(
                None
                if ack_scope_raw is None
                else str(uuid.UUID(str(ack_scope_raw)))
            )
        except (ValueError,TypeError,AttributeError) as exc:
            raise RuntimeError(
                "physical command acknowledgement v2 identity/scope is invalid"
            ) from exc
        if expected_scope_id is not None:
            try:
                expected_scope=str(uuid.UUID(str(expected_scope_id)))
            except (ValueError,TypeError,AttributeError) as exc:
                raise RuntimeError(
                    "physical command expected idempotency scope is invalid"
                ) from exc
            if ack_scope!=expected_scope:
                raise RuntimeError(
                    "physical command acknowledgement idempotency scope mismatch"
                )
    if ack.get("accepted") is not True:
        raise RuntimeError("physical command was not acknowledged as accepted")
    if ack.get("simulated") is not False:
        raise RuntimeError("physical command acknowledgement is marked simulated")
    if ack.get("physical_write_ready") is not True:
        raise RuntimeError("physical command acknowledgement lacks write authorization")
    if ack.get("write_contract_ready") is not True:
        raise RuntimeError("physical command acknowledgement lacks write contract")
    if ack.get("motion_semantics_ready") is not True:
        raise RuntimeError("physical command acknowledgement lacks motion semantics")
    if ack.get("evidence_kind") != "physical-command-accepted":
        raise RuntimeError("physical command acknowledgement evidence kind is invalid")
    if str(ack.get("action") or "") != "open":
        raise RuntimeError("physical first-contact acknowledgement action must be open")
    target = ack.get("target_pct")
    if target is None or abs(float(target) - float(expected_target)) > 1e-9:
        raise RuntimeError("physical command acknowledgement target mismatch")
    identity = str(ack.get("hardware_identity_sha256") or "")
    if len(identity) != 64 or any(
        ch not in "0123456789abcdef" for ch in identity.lower()
    ):
        raise RuntimeError("physical command acknowledgement hardware identity is invalid")
    return dict(ack)


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
    if authorized < 2.0:
        raise RuntimeError(
            "authorized first-contact target is below the 2% minimum Reality Delta"
        )
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
    closeout: Mapping[str, Any] | None = None,
    terminal_snapshot: Mapping[str, Any] | None = None,
    expected_command_scope_id: str | None = None,
) -> dict[str, Any]:
    feedback_rows = trajectory_step.get("actuator_feedback")
    if not isinstance(feedback_rows, list) or len(feedback_rows) != 1:
        raise ValueError("physical trajectory step must have exactly one actuator feedback")
    feedback = feedback_rows[0]
    measured = feedback.get("measured_position_pct")
    if measured is None:
        raise RuntimeError("physical handoff requires measured actuator position")
    measured = float(measured)
    action_feedback_ts = float(feedback.get("timestamp") or 0)
    if action_feedback_ts <= 0:
        raise RuntimeError("physical handoff actuator feedback timestamp is invalid")

    closeout_position = None
    closeout_ts = None
    if closeout is not None:
        closeout_feedback = closeout.get("feedback")
        if not isinstance(closeout_feedback, Mapping):
            raise ValueError("physical handoff closeout feedback is missing")
        closeout_position = closeout_feedback.get("measured_position_pct")
        closeout_ts = closeout_feedback.get("timestamp")
        if closeout_position is None or closeout_ts is None:
            raise ValueError("physical handoff closeout lacks measured position/timestamp")
        closeout_position = float(closeout_position)
        closeout_ts = float(closeout_ts)
        if closeout_ts <= action_feedback_ts:
            raise RuntimeError("physical closeout must be newer than action feedback")
        if closeout.get("confirmed_closed") is not True:
            raise RuntimeError("physical closeout is not confirmed closed")

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

    terminal_co2 = None
    terminal_co2_ts = None
    terminal_rain = None
    terminal_rain_ts = None
    terminal_snapshot_sha = None
    if terminal_snapshot is not None:
        if terminal_snapshot.get("fresh_after_closeout") is not True:
            raise RuntimeError("terminal physical sensor snapshot is not fresh after closeout")
        terminal_co2 = float(terminal_snapshot["co2_ppm"])
        terminal_co2_ts = float(terminal_snapshot["co2_timestamp"])
        terminal_rain = bool(terminal_snapshot["rain"])
        terminal_rain_ts = float(terminal_snapshot["rain_timestamp"])
        terminal_snapshot_sha = str(terminal_snapshot.get("snapshot_sha256") or "")
        if closeout_ts is None:
            raise RuntimeError("terminal sensor snapshot requires closeout evidence")
        if terminal_co2_ts <= closeout_ts or terminal_rain_ts <= closeout_ts:
            raise RuntimeError("terminal sensors must be newer than closeout feedback")

    authorized = float(authorization["authorized_target_pct"])

    step_info = trajectory_step.get("info") or {}
    command_acks = (
        step_info.get("command_acks")
        if isinstance(step_info, Mapping)
        else None
    )
    if not isinstance(command_acks, list) or len(command_acks) != 1:
        raise RuntimeError(
            "physical handoff requires exactly one verified command acknowledgement"
        )
    command_ack = _verify_command_ack(
        command_acks[0],
        expected_target=authorized,
        expected_scope_id=expected_command_scope_id,
    )

    position_error = measured - authorized
    payload = {
        "schema_version": "0.1",
        "reconcile": "sim-to-physical-first-contact-v1",
        "opening_id": str(planner_handoff["opening_id"]),
        "selected_label": str(planner_handoff.get("selected_label") or ""),
        "planned_target_pct": float(planner_handoff["planned_target_pct"]),
        "authorized_target_pct": authorized,
        "action_feedback_position_pct": measured,
        "action_feedback_timestamp": action_feedback_ts,
        "measured_minus_authorized_pct": round(position_error, 6),
        "post_closeout_position_pct": closeout_position,
        "post_closeout_timestamp": closeout_ts,
        "terminal_position_pct": closeout_position,
        "terminal_position_source": (
            "safe-closeout-measured-feedback"
            if closeout_position is not None
            else "unavailable-until-safe-closeout"
        ),
        "next_origin_position_verified": closeout_position is not None,
        "terminal_co2_ppm": terminal_co2,
        "terminal_co2_timestamp": terminal_co2_ts,
        "terminal_rain": terminal_rain,
        "terminal_rain_timestamp": terminal_rain_ts,
        "terminal_snapshot_sha256": terminal_snapshot_sha,
        "next_origin_sensor_verified": terminal_snapshot is not None,
        "physical_next_origin_ready": (
            closeout_position is not None and terminal_snapshot is not None
        ),
        "planner_action_fully_executed": (
            bool(authorization.get("planner_action_fully_authorized"))
            and abs(position_error) <= 1.0
        ),
        "physical_intervention": authorization.get("intervention"),
        "command_ack_sha256": command_ack["command_ack_sha256"],
        "command_hardware_identity_sha256": command_ack["hardware_identity_sha256"],
        "command_idempotency_scope_id": (
            command_ack.get("idempotency_scope_id")
        ),
        "command_write_gate_verified": True,
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
