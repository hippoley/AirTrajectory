"""Fail-closed authorization-use freshness for physical effects.

An authorization may be cryptographically valid yet no longer apply to the
current world. This gate re-observes the relevant physical state immediately
before effect dispatch and rejects stale or drifted authorization use.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Iterable, Mapping


def _row(value: Any) -> Mapping[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return value
    raise ValueError("pre-execution sensor reading is invalid")


def validate_authorization_use_freshness(
    *,
    authorization: Mapping[str, Any],
    freshness_checked_at: float,
    position_feedback: Mapping[str, Any],
    sensor_readings: Iterable[Any],
    position_tolerance_pct: float = 1.0,
) -> dict[str, Any]:
    """Verify that the world still matches the state the authorization used.

    This is deliberately narrower than re-planning. It only prevents using a
    valid authorization against a different or stale physical state.
    """
    checked_at = float(freshness_checked_at)
    if checked_at <= 0:
        raise ValueError("freshness_checked_at must be positive")

    if not isinstance(authorization, Mapping):
        raise ValueError("authorization must be an object")

    expected_position = float(authorization["current_measured_pct"])
    expected_rain = bool(authorization["current_rain"])

    if not isinstance(position_feedback, Mapping):
        raise RuntimeError("authorization-use gate requires position feedback")
    if position_feedback.get("measured") is not True:
        raise RuntimeError("authorization-use gate requires measured position")
    position_ts = float(position_feedback.get("timestamp") or 0)
    position_pct = position_feedback.get("position_pct")
    if position_pct is None or position_ts <= checked_at:
        raise RuntimeError(
            "authorization-use position evidence is not newer than authorization freshness check"
        )
    position_pct = float(position_pct)
    tolerance = float(position_tolerance_pct)
    if tolerance < 0:
        raise ValueError("position_tolerance_pct must be non-negative")
    if abs(position_pct - expected_position) > tolerance:
        raise RuntimeError(
            "authorization-use position drift: current physical state no longer "
            "matches authorized origin"
        )

    rain_row = None
    for item in sensor_readings:
        row = _row(item)
        if str(row.get("sensor_type") or "").lower() == "rain":
            rain_row = row
            break
    if rain_row is None:
        raise RuntimeError("authorization-use gate requires fresh rain evidence")

    rain_ts = float(rain_row.get("timestamp") or 0)
    if rain_ts <= checked_at:
        raise RuntimeError(
            "authorization-use rain evidence is not newer than authorization freshness check"
        )
    rain_value = rain_row.get("value")
    if rain_value is None:
        raise RuntimeError("authorization-use rain evidence lacks value")
    current_rain = bool(float(rain_value))
    if current_rain != expected_rain:
        raise RuntimeError(
            "authorization-use rain state drift: authorization is no longer valid"
        )

    return {
        "authorization_use_status": "FRESH",
        "freshness_checked_at": checked_at,
        "position_observed_at": position_ts,
        "rain_observed_at": rain_ts,
        "expected_position_pct": expected_position,
        "observed_position_pct": position_pct,
        "expected_rain": expected_rain,
        "observed_rain": current_rain,
        "evidence_boundary": (
            "authorization use was revalidated against fresh measured position "
            "and rain state immediately before effect dispatch"
        ),
    }
