"""Authoritative physical-effect reconciliation.

Resolve a previously unresolved logical effect only from fresh measured
post-action evidence. Transport ACKs, retries, and cached state are explicitly
insufficient.
"""
from __future__ import annotations

from typing import Any, Mapping


def reconcile_physical_effect(
    *,
    logical_effect_id: str,
    intended_target_pct: float,
    observation: Mapping[str, Any] | None,
    tolerance_pct: float = 1.0,
) -> dict[str, Any]:
    logical_effect_id = str(logical_effect_id or "").strip()
    if not logical_effect_id:
        raise ValueError("logical_effect_id must not be empty")

    target = float(intended_target_pct)
    tolerance = float(tolerance_pct)
    if not 0 <= target <= 100:
        raise ValueError("intended_target_pct must be in [0,100]")
    if tolerance < 0:
        raise ValueError("tolerance_pct must be non-negative")

    if observation is None:
        return {
            "logical_effect_id": logical_effect_id,
            "status": "UNRESOLVED",
            "reason": "NO_AUTHORITATIVE_OBSERVATION",
            "observed_position_pct": None,
            "fresh": False,
            "measured": False,
        }

    measured = observation.get("measured") is True
    fresh = observation.get("fresh_after_action") is True
    value = observation.get("measured_position_pct")
    source = str(observation.get("source") or "").strip()

    if not measured:
        return {
            "logical_effect_id": logical_effect_id,
            "status": "UNRESOLVED",
            "reason": "OBSERVATION_NOT_MEASURED",
            "observed_position_pct": None if value is None else float(value),
            "fresh": fresh,
            "measured": False,
        }
    if not fresh:
        return {
            "logical_effect_id": logical_effect_id,
            "status": "UNRESOLVED",
            "reason": "OBSERVATION_NOT_FRESH",
            "observed_position_pct": None if value is None else float(value),
            "fresh": False,
            "measured": True,
        }
    if value is None:
        return {
            "logical_effect_id": logical_effect_id,
            "status": "UNRESOLVED",
            "reason": "MEASURED_VALUE_MISSING",
            "observed_position_pct": None,
            "fresh": True,
            "measured": True,
        }
    if not source:
        return {
            "logical_effect_id": logical_effect_id,
            "status": "UNRESOLVED",
            "reason": "MEASUREMENT_SOURCE_MISSING",
            "observed_position_pct": float(value),
            "fresh": True,
            "measured": True,
        }

    observed = float(value)
    delta = observed - target
    status = "CONFIRMED" if abs(delta) <= tolerance else "CONTRADICTED"
    return {
        "logical_effect_id": logical_effect_id,
        "status": status,
        "reason": "WITHIN_TOLERANCE" if status == "CONFIRMED" else "OUTSIDE_TOLERANCE",
        "observed_position_pct": observed,
        "intended_target_pct": target,
        "delta_pct": delta,
        "tolerance_pct": tolerance,
        "fresh": True,
        "measured": True,
        "source": source,
        "evidence_boundary": (
            "effect outcome resolved from fresh measured post-action evidence; "
            "transport acknowledgement alone is insufficient"
        ),
    }
