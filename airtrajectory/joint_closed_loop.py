"""Closed-loop joint planning contracts.

This module deliberately separates the control-loop mechanics from CONTAM state
continuation. A planner may only claim real receding-horizon CONTAM evidence
when its evaluator can prove that each new origin is actually injected into, or
continued by, the underlying physics engine.

Until that capability exists, real-ContamX callers must fail closed instead of
silently reusing the PRJ initial contaminant state.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Callable, Mapping, Sequence


class RecedingHorizonCapabilityError(RuntimeError):
    """Raised when a backend cannot truthfully continue from the observed state."""


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _float_mapping(value: Mapping[str, Any], *, name: str) -> dict[str, float]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"{name} must be a non-empty mapping")
    return {str(key): float(raw) for key, raw in value.items()}


@dataclass(frozen=True)
class ClosedLoopOrigin:
    co2_ppm: Mapping[str, float]
    opening_pct: Mapping[str, float]
    scalar_values: Mapping[str, float] | None = None

    def normalized(self) -> dict[str, dict[str, float]]:
        co2 = _float_mapping(self.co2_ppm, name="co2_ppm")
        openings = _float_mapping(self.opening_pct, name="opening_pct")
        if any(value < 0 or value > 100 for value in openings.values()):
            raise ValueError("opening_pct values must be within [0,100]")
        scalars = {
            str(key): float(value)
            for key, value in (self.scalar_values or {}).items()
        }
        return {
            "co2_ppm": dict(sorted(co2.items())),
            "opening_pct": dict(sorted(openings.items())),
            "scalar_values": dict(sorted(scalars.items())),
        }


@dataclass(frozen=True)
class BackendContinuationCapability:
    backend: str
    physics_fidelity: str
    state_reinjection_verified: bool
    continuation_mode: str
    evidence_boundary: str

    def require_receding_horizon(self) -> None:
        if not self.state_reinjection_verified:
            raise RecedingHorizonCapabilityError(
                f"{self.backend} cannot claim receding-horizon {self.physics_fidelity} "
                f"from continuation mode {self.continuation_mode!r}: "
                f"{self.evidence_boundary}"
            )


def contam_receding_horizon_capability(profile) -> BackendContinuationCapability:
    """Describe the truthful continuation capability of the current CONTAM fork path.

    The present ContamX adapter can continue a live CONTAMEnvironment by stepping
    the same session, but the fork path cannot create an arbitrary new branch from
    a solved CO2 snapshot. initial_co2_ppm is an observation contract and PRJ
    provenance check; it is not verified runtime state injection.
    """
    mode = str(getattr(profile, "origin_state_mode", "declared-only"))
    has_prj_anchor = bool(getattr(profile, "prj_initial_co2_ppm", {}))
    reseed_verified = bool(
        getattr(profile, "prj_reseed_continuation_verified", False)
    )
    if reseed_verified:
        return BackendContinuationCapability(
            backend="contamxpy",
            physics_fidelity="CONTAM",
            state_reinjection_verified=True,
            continuation_mode="prj-section15-reseed-verified",
            evidence_boundary=(
                "verified contaminant-state continuation under identical static "
                "boundaries and controls; native restart/time continuity not established"
            ),
        )
    boundary = (
        "fork origins are anchored to the PRJ initial contaminant state; "
        "arbitrary solved CO2 reinjection/branch continuation is not verified"
        if has_prj_anchor
        else
        "runtime contaminant-state reinjection/branch continuation is not verified"
    )
    return BackendContinuationCapability(
        backend="contamxpy",
        physics_fidelity="CONTAM",
        state_reinjection_verified=False,
        continuation_mode=mode,
        evidence_boundary=boundary,
    )


def normalize_action_vector(actions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(actions, Sequence) or isinstance(actions, (str, bytes)) or not actions:
        raise ValueError("actions must be a non-empty sequence")
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in actions:
        if not isinstance(raw, Mapping):
            raise ValueError("each action must be an object")
        opening_id = raw.get("opening_id")
        actuator_id = raw.get("actuator_id")
        if (opening_id is None) == (actuator_id is None):
            raise ValueError(
                "action must specify exactly one of opening_id or actuator_id"
            )
        if opening_id is not None:
            key = ("opening", str(opening_id))
            if key in seen:
                raise ValueError(f"duplicate action for opening {opening_id}")
            seen.add(key)
            target = float(raw["target_pct"])
            if target < 0 or target > 100:
                raise ValueError("opening target_pct must be within [0,100]")
            out.append(
                {
                    "kind": "opening",
                    "opening_id": str(opening_id),
                    "target_pct": target,
                }
            )
            continue
        key = ("scalar", str(actuator_id))
        if key in seen:
            raise ValueError(f"duplicate action for actuator {actuator_id}")
        seen.add(key)
        out.append(
            {
                "kind": "scalar",
                "actuator_id": str(actuator_id),
                "target_value": float(raw["target_value"]),
            }
        )
    return sorted(
        out,
        key=lambda row: (
            row["kind"],
            row.get("opening_id") or row.get("actuator_id"),
        ),
    )


def _origin_from_observation(observation: Mapping[str, Any]) -> ClosedLoopOrigin:
    if not isinstance(observation, Mapping):
        raise ValueError("executor observation must be an object")
    return ClosedLoopOrigin(
        co2_ppm=observation.get("co2_ppm") or {},
        opening_pct=observation.get("opening_pct") or {},
        scalar_values=observation.get("scalar_values") or {},
    )


def run_receding_horizon_joint(
    *,
    initial_origin: ClosedLoopOrigin,
    control_steps: int,
    prediction_horizon_steps: int,
    candidate_provider: Callable[[dict[str, Any], int], Sequence[Mapping[str, Any]]],
    evaluator: Callable[[dict[str, Any], Sequence[Mapping[str, Any]], int, int], Mapping[str, Any]],
    executor: Callable[[dict[str, Any], Sequence[Mapping[str, Any]], int], Mapping[str, Any]],
    capability: BackendContinuationCapability,
) -> dict[str, Any]:
    """Run a truthful step-by-step receding-horizon control loop.

    evaluator evaluates all candidates from the current origin and returns
    selected_label, selected_actions, objective_score, and optional evidence.
    executor applies only the selected first action vector and returns the
    observation that becomes the next origin.

    The backend capability is checked before any second planning step. This is
    what prevents the current real-CONTAM fork path from being mislabeled as
    closed-loop MPC while state reinjection is still unverified.
    """
    if control_steps <= 0:
        raise ValueError("control_steps must be positive")
    if prediction_horizon_steps <= 0:
        raise ValueError("prediction_horizon_steps must be positive")

    current = initial_origin.normalized()
    initial_sha = _sha256(current)
    steps: list[dict[str, Any]] = []

    for step_index in range(control_steps):
        if step_index > 0:
            capability.require_receding_horizon()

        candidates = candidate_provider(current, step_index)
        if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
            raise ValueError("candidate_provider must return a sequence")
        if not candidates:
            raise ValueError("candidate_provider returned no candidates")

        evaluation = dict(
            evaluator(
                current,
                candidates,
                prediction_horizon_steps,
                step_index,
            )
        )
        label = str(evaluation.get("selected_label") or "")
        if not label:
            raise ValueError("evaluator must return selected_label")
        selected_actions = normalize_action_vector(
            evaluation.get("selected_actions") or []
        )
        objective = float(evaluation["objective_score"])

        observation = dict(executor(current, selected_actions, step_index))
        next_origin = _origin_from_observation(observation).normalized()

        step_payload = {
            "step_index": step_index,
            "origin": current,
            "origin_sha256": _sha256(current),
            "candidate_count": len(candidates),
            "selected_label": label,
            "selected_actions": selected_actions,
            "objective_score": objective,
            "prediction_horizon_steps": prediction_horizon_steps,
            "evaluation_evidence": dict(evaluation.get("evidence") or {}),
            "observation": observation,
            "next_origin": next_origin,
            "next_origin_sha256": _sha256(next_origin),
        }
        steps.append(
            {
                **step_payload,
                "step_sha256": _sha256(step_payload),
            }
        )
        current = next_origin

    payload = {
        "schema_version": "0.1",
        "controller": "receding-horizon-joint-v1",
        "control_steps": control_steps,
        "prediction_horizon_steps": prediction_horizon_steps,
        "initial_origin_sha256": initial_sha,
        "final_origin_sha256": _sha256(current),
        "backend_capability": {
            "backend": capability.backend,
            "physics_fidelity": capability.physics_fidelity,
            "state_reinjection_verified": capability.state_reinjection_verified,
            "continuation_mode": capability.continuation_mode,
            "evidence_boundary": capability.evidence_boundary,
        },
        "steps": steps,
        "closed_loop_replanning_executed": control_steps > 1,
    }
    return {
        **payload,
        "receipt_sha256": _sha256(payload),
    }
