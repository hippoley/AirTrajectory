"""Multi-environment consequence comparison for candidate futures."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .objective import ObjectiveContract


def _series(candidate: Mapping[str, Any], field: str) -> Mapping[str, Sequence[float]]:
    series = (candidate.get("series_by_metric") or {}).get(field)
    if not isinstance(series, Mapping) or not series:
        raise ValueError(f"candidate {candidate.get('label')} lacks {field} series")
    lengths = {len(values) for values in series.values()}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) <= 0:
        raise ValueError(f"candidate {candidate.get('label')} has invalid {field} series")
    return series


def _mean_excess(series: Mapping[str, Sequence[float]], threshold: float) -> float:
    values = [float(value) for zone_values in series.values() for value in zone_values]
    return sum(max(0.0, value - threshold) for value in values) / len(values)


def _max_value(series: Mapping[str, Sequence[float]]) -> float:
    return max(float(value) for values in series.values() for value in values)


def _band_discomfort(
    series: Mapping[str, Sequence[float]],
    minimum: float,
    maximum: float,
) -> float:
    values = [float(value) for zone_values in series.values() for value in zone_values]
    return sum(
        max(0.0, minimum - value, value - maximum)
        for value in values
    ) / len(values)


def _movement(candidate: Mapping[str, Any], origin_openings: Mapping[str, float]) -> float:
    seen: set[str] = set()
    total = 0.0
    for action in candidate.get("actions") or []:
        opening_id = str(action["opening_id"])
        if opening_id not in origin_openings:
            raise ValueError(f"candidate references unknown opening {opening_id}")
        if opening_id in seen:
            raise ValueError(f"candidate repeats opening {opening_id}")
        seen.add(opening_id)
        total += abs(float(action["target_pct"]) - float(origin_openings[opening_id]))
    return total


def evaluate_candidate(
    candidate: Mapping[str, Any],
    *,
    objective: ObjectiveContract,
    origin_openings: Mapping[str, float],
) -> dict[str, Any]:
    label = str(candidate.get("label") or "")
    if not label:
        raise ValueError("candidate label is required")

    metrics: dict[str, float] = {}
    hard_violations: list[str] = []

    for field, goal in objective.pollutants.items():
        values = _series(candidate, field)
        short = "co2" if field == "co2_ppm" else "pm25" if field == "pm25_ug_m3" else field
        metrics[f"{short}_excess"] = round(_mean_excess(values, goal.target_max), 6)
        metrics[f"{short}_peak"] = round(_max_value(values), 6)
        if goal.hard_max is not None and _max_value(values) > goal.hard_max:
            hard_violations.append(
                f"{field}:peak>{goal.hard_max:g}"
            )

    for field, band in objective.comfort.items():
        values = _series(candidate, field)
        short = "temperature" if field == "temperature_c" else "humidity"
        metrics[f"{short}_discomfort"] = round(
            _band_discomfort(values, band.minimum, band.maximum),
            6,
        )
        peak_low = min(float(value) for rows in values.values() for value in rows)
        peak_high = max(float(value) for rows in values.values() for value in rows)
        if band.hard_minimum is not None and peak_low < band.hard_minimum:
            hard_violations.append(
                f"{field}:min<{band.hard_minimum:g}"
            )
        if band.hard_maximum is not None and peak_high > band.hard_maximum:
            hard_violations.append(
                f"{field}:max>{band.hard_maximum:g}"
            )

    movement = _movement(candidate, origin_openings)
    metrics["movement"] = round(movement, 6)

    duration_min = float(candidate.get("duration_min") or 0.0)
    if duration_min < 0:
        raise ValueError("candidate duration_min cannot be negative")
    metrics["duration_min"] = duration_min
    if (
        objective.max_intervention_min is not None
        and duration_min > objective.max_intervention_min
    ):
        hard_violations.append(
            f"duration_min>{objective.max_intervention_min:g}"
        )

    rain = bool(candidate.get("rain", False))
    if objective.rain_hard_constraint and rain and movement > 0:
        hard_violations.append("rain:no-window-motion")

    return {
        "label": label,
        "feasible": not hard_violations,
        "hard_violations": hard_violations,
        "metrics": metrics,
        "provenance": candidate.get("provenance") or {},
    }


def compare_candidate_futures(
    candidates: Sequence[Mapping[str, Any]],
    *,
    objective: ObjectiveContract,
    origin_openings: Mapping[str, float],
) -> dict[str, Any]:
    if len(candidates) < 2:
        raise ValueError("comparison requires at least two candidates")

    rows = [
        evaluate_candidate(
            candidate,
            objective=objective,
            origin_openings=origin_openings,
        )
        for candidate in candidates
    ]

    metric_key_by_priority = {
        "co2_excess": "co2_excess",
        "pm25_excess": "pm25_excess",
        "temperature_discomfort": "temperature_discomfort",
        "humidity_discomfort": "humidity_discomfort",
        "movement": "movement",
    }

    feasible = [row for row in rows if row["feasible"]]
    recommendation_basis: list[str] = []
    recommended: list[str] = []
    if feasible:
        working = feasible
        for priority in objective.priorities:
            metric_key = metric_key_by_priority[priority]
            if not all(metric_key in row["metrics"] for row in working):
                continue
            best = min(float(row["metrics"][metric_key]) for row in working)
            working = [
                row
                for row in working
                if abs(float(row["metrics"][metric_key]) - best) <= 1e-9
            ]
            recommendation_basis.append(metric_key)
            if len(working) == 1:
                break
        recommended = sorted(row["label"] for row in working)

    return {
        "schema_version": "0.1",
        "comparison": "airtrajectory-multi-environment-consequences-v0.1",
        "objective": objective.as_dict(),
        "ranking_policy": "hard-constraints-then-lexicographic-priorities",
        "recommendation_basis": recommendation_basis,
        "recommended": recommended,
        "results": sorted(rows, key=lambda row: row["label"]),
        "evidence_boundary": (
            "compares supplied predicted consequence series; this module does "
            "not claim to generate PM2.5/thermal/humidity physics itself"
        ),
    }
