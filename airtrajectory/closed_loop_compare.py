"""Realized closed-loop trajectory scoring and comparison."""
from __future__ import annotations

import hashlib
import json
from statistics import mean
from typing import Any, Mapping, Sequence


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _steps(receipt: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    steps = receipt.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("closed-loop receipt must contain non-empty steps")
    return steps


def score_realized_closed_loop(
    receipt: Mapping[str, Any],
    *,
    iaq_reference_ppm: float,
    high_co2_ppm: float,
    objective_weights: Mapping[str, float],
) -> dict[str, Any]:
    """Score only the states/actions actually executed by a closed-loop receipt."""
    steps = _steps(receipt)
    if iaq_reference_ppm <= 0 or high_co2_ppm <= iaq_reference_ppm:
        raise ValueError("invalid CO2 thresholds")

    required_weights = (
        "mean_excess_1000",
        "max_excess_1200",
        "high_co2_zone_steps",
        "mean_room_imbalance",
        "movement_pct_sum",
    )
    weights = {key: float(objective_weights[key]) for key in required_weights}
    if any(value < 0 for value in weights.values()):
        raise ValueError("objective weights must be non-negative")

    co2_vectors = []
    movement = 0.0
    selected_labels = []
    for step in steps:
        origin = step.get("origin") or {}
        observation = step.get("observation") or {}
        origin_co2 = origin.get("co2_ppm")
        observed_co2 = observation.get("co2_ppm")
        origin_openings = origin.get("opening_pct")
        observed_openings = observation.get("opening_pct")
        if not isinstance(origin_co2, Mapping) or not isinstance(observed_co2, Mapping):
            raise ValueError("closed-loop step must include origin/observed CO2")
        if set(origin_co2) != set(observed_co2) or not observed_co2:
            raise ValueError("closed-loop CO2 zone set changed")
        if not isinstance(origin_openings, Mapping) or not isinstance(observed_openings, Mapping):
            raise ValueError("closed-loop step must include origin/observed openings")
        if set(origin_openings) != set(observed_openings):
            raise ValueError("closed-loop opening set changed")

        co2_vectors.append(
            [float(observed_co2[zone]) for zone in sorted(observed_co2)]
        )
        movement += sum(
            abs(float(observed_openings[key]) - float(origin_openings[key]))
            for key in sorted(observed_openings)
        )
        selected_labels.append(str(step.get("selected_label") or ""))

    all_values = [value for vector in co2_vectors for value in vector]
    mean_excess = mean(max(0.0, value - iaq_reference_ppm) for value in all_values)
    max_excess = max(0.0, max(all_values) - high_co2_ppm)
    high_steps = sum(1 for value in all_values if value > high_co2_ppm)
    imbalance = mean(max(vector) - min(vector) for vector in co2_vectors)

    metrics = {
        "control_steps": len(steps),
        "mean_co2_ppm": round(mean(all_values), 3),
        "max_co2_ppm": round(max(all_values), 3),
        "mean_excess_1000_ppm": round(mean_excess, 3),
        "max_excess_1200_ppm": round(max_excess, 3),
        "high_co2_zone_steps": int(high_steps),
        "mean_room_imbalance_ppm": round(imbalance, 3),
        "movement_pct_sum": round(movement, 3),
        "selected_labels": selected_labels,
    }
    objective = (
        weights["mean_excess_1000"] * mean_excess
        + weights["max_excess_1200"] * max_excess
        + weights["high_co2_zone_steps"] * high_steps
        + weights["mean_room_imbalance"] * imbalance
        + weights["movement_pct_sum"] * movement
    )
    payload = {
        "schema_version": "0.1",
        "scoring": "realized-closed-loop-v1",
        "metrics": metrics,
        "objective_score": round(float(objective), 6),
        "receipt_sha256": str(receipt.get("receipt_sha256") or ""),
    }
    return {
        **payload,
        "score_sha256": _sha256(payload),
    }


def compare_closed_loop_modes(
    *,
    adaptive_receipt: Mapping[str, Any],
    independent_receipt: Mapping[str, Any],
    iaq_reference_ppm: float,
    high_co2_ppm: float,
    objective_weights: Mapping[str, float],
) -> dict[str, Any]:
    adaptive = score_realized_closed_loop(
        adaptive_receipt,
        iaq_reference_ppm=iaq_reference_ppm,
        high_co2_ppm=high_co2_ppm,
        objective_weights=objective_weights,
    )
    independent = score_realized_closed_loop(
        independent_receipt,
        iaq_reference_ppm=iaq_reference_ppm,
        high_co2_ppm=high_co2_ppm,
        objective_weights=objective_weights,
    )
    if adaptive["metrics"]["control_steps"] != independent["metrics"]["control_steps"]:
        raise ValueError("closed-loop modes must have the same control step count")

    delta = round(
        float(independent["objective_score"]) - float(adaptive["objective_score"]),
        6,
    )
    outcome = "WIN" if delta > 1e-9 else "LOSS" if delta < -1e-9 else "TIE"
    payload = {
        "schema_version": "0.1",
        "comparison": "adaptive-vs-independent-realized-closed-loop-v1",
        "outcome": outcome,
        "objective_improvement": delta,
        "adaptive": adaptive,
        "independent": independent,
        "evidence_boundary": (
            "realized real-ContamX simulation trajectory; no field actuation, "
            "measured-room feedback, or native restart-clock continuity"
        ),
    }
    return {
        **payload,
        "comparison_sha256": _sha256(payload),
    }
