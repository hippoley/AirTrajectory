"""Fail-closed comparison of *supplied* same-origin multi-environment futures.

This module ranks outcomes; it never generates physical forecasts. A fixture
or a claimed backend result is NOT evidence of a verified solver run.
"""
from __future__ import annotations

import hashlib
import json
from math import isfinite
from typing import Any, Mapping, Sequence

from .objective import ObjectiveContract


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite number") from exc
    if not isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    return number


def _fingerprint(origin: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(
            origin, sort_keys=True, ensure_ascii=False, allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("origin must be a finite JSON-compatible state") from exc
    return hashlib.sha256(encoded).hexdigest()


def _validated_origin(origin: Any, origin_openings: Mapping[str, float]) -> str:
    if not isinstance(origin, Mapping):
        raise ValueError("candidate requires an explicit origin state")
    if not isinstance(origin.get("opening_pct"), Mapping):
        raise ValueError("origin opening_pct mapping is required")
    if set(origin["opening_pct"]) != set(origin_openings):
        raise ValueError("origin opening coverage differs from supplied origin")
    kinds = origin.get("opening_kind")
    if not isinstance(kinds, Mapping) or set(kinds) != set(origin_openings):
        raise ValueError("origin requires opening_kind for every controlled opening")
    if any(kind not in {"window", "door", "vent"} for kind in kinds.values()):
        raise ValueError("origin has unsupported opening_kind")
    for opening, pct in origin_openings.items():
        if not 0 <= _finite(pct, f"origin opening {opening}") <= 100:
            raise ValueError("origin opening percentage outside [0,100]")
        if _finite(origin["opening_pct"][opening], f"origin opening {opening}") != float(pct):
            raise ValueError("candidate opening origin mismatch")
    if not isinstance(origin.get("rain"), bool):
        raise ValueError("origin requires observed or declared boolean rain")
    return _fingerprint(origin)


def _grid(candidate: Mapping[str, Any]) -> tuple[float, ...]:
    values = candidate.get("time_grid_min")
    if not isinstance(values, (list, tuple)) or len(values) < 2:
        raise ValueError("candidate requires a common time_grid_min with >=2 points")
    grid = tuple(_finite(x, "time_grid_min") for x in values)
    if grid[0] != 0.0 or any(b <= a for a, b in zip(grid, grid[1:])):
        raise ValueError("time_grid_min must start at 0 and strictly increase")
    return grid


def _series(
    candidate: Mapping[str, Any], field: str,
    grid: tuple[float, ...], origin: Mapping[str, Any],
) -> Mapping[str, Sequence[float]]:
    series = candidate.get("series_by_metric", {}).get(field)
    initial = origin.get(field)
    if not isinstance(series, Mapping) or not series:
        raise ValueError(f"candidate {candidate.get('label')} lacks {field} series")
    if not isinstance(initial, Mapping) or set(series) != set(initial):
        raise ValueError(f"candidate {candidate.get('label')} has inconsistent {field} zones")
    for zone, values in series.items():
        if not isinstance(values, (list, tuple)) or len(values) != len(grid):
            raise ValueError(f"{field}: series must match the common time grid")
        floats = [_finite(v, f"{field}:{zone}") for v in values]
        if floats[0] != _finite(initial[zone], f"origin {field}:{zone}"):
            raise ValueError(f"{field}: candidate series does not start at origin")
        if field == "relative_humidity_pct" and any(not 0 <= v <= 100 for v in floats):
            raise ValueError("relative humidity outside [0,100]")
        if field in {"co2_ppm", "pm25_ug_m3", "tvoc_ug_m3", "hcho_mg_m3"} and any(
            v < 0 for v in floats
        ):
            raise ValueError(f"{field} concentration cannot be negative")
    return series


def _values(series: Mapping[str, Sequence[float]]) -> list[float]:
    return [float(value) for zone_values in series.values() for value in zone_values]


def _mean_excess(series: Mapping[str, Sequence[float]], threshold: float) -> float:
    values = _values(series)
    return sum(max(0.0, value - threshold) for value in values) / len(values)


def _band_discomfort(
    series: Mapping[str, Sequence[float]], minimum: float, maximum: float,
) -> float:
    values = _values(series)
    return sum(max(0.0, minimum - value, value - maximum) for value in values) / len(values)


def _movement(
    candidate: Mapping[str, Any], origin_openings: Mapping[str, float],
    opening_kinds: Mapping[str, str],
) -> tuple[float, float]:
    actions = candidate.get("actions")
    if not isinstance(actions, list):
        raise ValueError("candidate actions list is required")
    seen: set[str] = set()
    total = increase = 0.0
    for action in actions:
        if not isinstance(action, Mapping) or "opening_id" not in action:
            raise ValueError("invalid opening action")
        opening_id = str(action["opening_id"])
        if opening_id not in origin_openings:
            raise ValueError(f"candidate references unknown opening {opening_id}")
        if opening_id in seen:
            raise ValueError(f"candidate repeats opening {opening_id}")
        seen.add(opening_id)
        target = _finite(action.get("target_pct"), f"{opening_id} target_pct")
        if not 0 <= target <= 100:
            raise ValueError("target_pct outside [0,100]")
        delta = target - float(origin_openings[opening_id])
        total += abs(delta)
        if opening_kinds[opening_id] == "window":
            increase += max(0.0, delta)
    return total, increase


def _validate_candidate(
    candidate: Mapping[str, Any],
    objective: ObjectiveContract,
    origin_openings: Mapping[str, float],
) -> dict[str, Any]:
    label = str(candidate.get("label") or "")
    if not label:
        raise ValueError("candidate label is required")
    origin = candidate.get("origin")
    origin_sha = _validated_origin(origin, origin_openings)
    grid = _grid(candidate)
    if candidate.get("rain") is not origin["rain"] or not isinstance(candidate.get("rain"), bool):
        raise ValueError("candidate rain must equal the declared common origin")
    provenance = candidate.get("provenance")
    if not isinstance(provenance, Mapping) or not provenance.get("kind"):
        raise ValueError("candidate provenance.kind is required")
    if provenance.get("engineering_truth") is True and provenance.get("kind") == "fixture":
        raise ValueError("illustrative fixture cannot claim engineering truth")

    metrics: dict[str, float] = {}
    hard_violations: list[str] = []
    zone_coverage: set[str] | None = None
    for field, goal in objective.pollutants.items():
        series = _series(candidate, field, grid, origin)
        zones = set(series)
        if zone_coverage is not None and zones != zone_coverage:
            raise ValueError("candidate metrics have different zone coverage")
        zone_coverage = zones
        values = _values(series)
        short = {
            "co2_ppm": "co2",
            "pm25_ug_m3": "pm25",
            "tvoc_ug_m3": "tvoc",
            "hcho_mg_m3": "hcho",
        }[field]
        metrics[f"{short}_excess"] = round(_mean_excess(series, goal.target_max), 6)
        metrics[f"{short}_peak"] = round(max(values), 6)
        if goal.hard_max is not None and max(values) > goal.hard_max:
            hard_violations.append(f"{field}:peak>{goal.hard_max:g}")
    for field, band in objective.comfort.items():
        series = _series(candidate, field, grid, origin)
        zones = set(series)
        if zone_coverage is not None and zones != zone_coverage:
            raise ValueError("candidate metrics have different zone coverage")
        zone_coverage = zones
        values = _values(series)
        short = "temperature" if field == "temperature_c" else "humidity"
        metrics[f"{short}_discomfort"] = round(
            _band_discomfort(series, band.minimum, band.maximum), 6
        )
        if band.hard_minimum is not None and min(values) < band.hard_minimum:
            hard_violations.append(f"{field}:min<{band.hard_minimum:g}")
        if band.hard_maximum is not None and max(values) > band.hard_maximum:
            hard_violations.append(f"{field}:max>{band.hard_maximum:g}")

    movement, _opening_increase = _movement(
        candidate, origin_openings, origin["opening_kind"]
    )
    metrics["movement"] = round(movement, 6)
    if "duration_min" not in candidate:
        raise ValueError("candidate intervention duration_min is required")
    duration_min = _finite(candidate["duration_min"], "duration_min")
    if not 0 <= duration_min <= grid[-1]:
        raise ValueError("duration_min must be within the comparison horizon")
    metrics["duration_min"] = duration_min
    if (
        objective.max_intervention_min is not None
        and duration_min > objective.max_intervention_min
    ):
        hard_violations.append(f"duration_min>{objective.max_intervention_min:g}")
    # Conservative wet-weather envelope: every exterior window must end
    # closed. Merely refusing further opening is unsafe if one starts open.
    # Interior doors and vents are not silently treated as exterior windows.
    if objective.rain_hard_constraint and origin["rain"]:
        targets = dict(origin_openings)
        targets.update({
            str(action["opening_id"]): float(action["target_pct"])
            for action in candidate["actions"]
        })
        if any(
            origin["opening_kind"][opening_id] == "window" and target > 0
            for opening_id, target in targets.items()
        ):
            hard_violations.append("rain:exterior-window-must-close")
    if label == "HOLD":
        if movement != 0 or duration_min != 0:
            raise ValueError("HOLD must not change openings or intervene")
    return {
        "label": label,
        "feasible": not hard_violations,
        "hard_violations": hard_violations,
        "metrics": metrics,
        "origin_sha256": origin_sha,
        "time_grid_min": list(grid),
        "zone_ids": sorted(zone_coverage or []),
        "provenance": dict(provenance),
    }


def evaluate_candidate(
    candidate: Mapping[str, Any], *,
    objective: ObjectiveContract,
    origin_openings: Mapping[str, float],
) -> dict[str, Any]:
    """Inspect a single candidate; never authorize a physical action."""
    return _validate_candidate(candidate, objective, origin_openings)


def compare_candidate_futures(
    candidates: Sequence[Mapping[str, Any]], *,
    objective: ObjectiveContract,
    origin_openings: Mapping[str, float],
) -> dict[str, Any]:
    """Compare same-origin and same-horizon consequences with no silent imputation."""
    if len(candidates) < 2:
        raise ValueError("comparison requires HOLD and at least one alternative")
    labels = [str(c.get("label") or "") for c in candidates]
    if not all(labels) or len(set(labels)) != len(labels) or "HOLD" not in labels:
        raise ValueError("candidate labels must be unique and include simulated HOLD")
    rows = [_validate_candidate(c, objective, origin_openings) for c in candidates]
    if len({row["origin_sha256"] for row in rows}) != 1:
        raise ValueError("candidate futures do not share the same origin")
    if len({tuple(row["time_grid_min"]) for row in rows}) != 1:
        raise ValueError("candidate futures do not share the same time grid")
    if len({tuple(row["zone_ids"]) for row in rows}) != 1:
        raise ValueError("candidate futures do not share the same zone coverage")
    provenance_set = {
        (row["provenance"].get("kind"), row["provenance"].get("backend"))
        for row in rows
    }
    if len(provenance_set) != 1:
        raise ValueError("candidate futures have incomparable evidence provenance")

    feasible = [row for row in rows if row["feasible"]]
    recommendation_basis: list[str] = []
    recommended: list[str] = []
    if feasible:
        working = feasible
        for priority in objective.priorities:
            if not all(priority in row["metrics"] for row in working):
                raise ValueError(f"undeclared or missing priority metric: {priority}")
            best = min(row["metrics"][priority] for row in working)
            working = [
                row for row in working
                if abs(row["metrics"][priority] - best) <= 1e-9
            ]
            recommendation_basis.append(priority)
            if len(working) == 1:
                break
        recommended = sorted(row["label"] for row in working)

    return {
        "schema_version": "0.2",
        "comparison": "airtrajectory-multi-environment-consequences-v0.2",
        "objective": objective.as_dict(),
        "status": "EXPLORATORY_COMPARISON" if feasible else "NO_FEASIBLE_CANDIDATE",
        "origin_sha256": rows[0]["origin_sha256"],
        "time_grid_min": rows[0]["time_grid_min"],
        "ranking_policy": "hard-constraints-then-lexicographic-priorities",
        "recommendation_basis": recommendation_basis,
        "recommended": recommended,
        "execution_authorized": False,
        "results": sorted(rows, key=lambda row: row["label"]),
        "evidence_boundary": (
            "declared same-origin predicted series, not independent physics "
            "verification or authorization for physical window actuation"
        ),
    }
