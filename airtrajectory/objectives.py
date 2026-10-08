"""Inspectable multi-environment objective and outcome evaluation.

This module is intentionally physics-neutral. It compares already-produced
candidate futures; it does not invent pollutant dynamics.

The vector is the source of truth. `score` is optional ranking convenience and
must never replace the per-metric outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Mapping


@dataclass(frozen=True)
class ComfortBand:
    minimum: float
    maximum: float

    def __post_init__(self) -> None:
        if not isfinite(self.minimum) or not isfinite(self.maximum):
            raise ValueError("comfort band must be finite")
        if self.minimum > self.maximum:
            raise ValueError("comfort band minimum cannot exceed maximum")

    def distance(self, value: float) -> float:
        if value < self.minimum:
            return self.minimum - value
        if value > self.maximum:
            return value - self.maximum
        return 0.0


@dataclass(frozen=True)
class MultiEnvironmentObjective:
    co2_reference_ppm: float = 1000.0
    pm25_reference_ug_m3: float = 15.0
    temperature_band_c: ComfortBand = ComfortBand(20.0, 26.0)
    humidity_band_pct: ComfortBand = ComfortBand(35.0, 65.0)
    weights: Mapping[str, float] = field(default_factory=lambda: {
        "co2_excess_ratio": 1.0,
        "pm25_excess_ratio": 1.0,
        "temperature_discomfort_ratio": 1.0,
        "humidity_discomfort_ratio": 1.0,
        "actuator_motion_ratio": 0.1,
        "safety_violation": 1000.0,
    })

    def __post_init__(self) -> None:
        if self.co2_reference_ppm <= 0:
            raise ValueError("co2_reference_ppm must be positive")
        if self.pm25_reference_ug_m3 < 0:
            raise ValueError("pm25_reference_ug_m3 cannot be negative")
        if any(float(v) < 0 or not isfinite(float(v)) for v in self.weights.values()):
            raise ValueError("objective weights must be finite and non-negative")


def _mean_available(values: Mapping[str, float] | None) -> float | None:
    if not values:
        return None
    rows=[float(v) for v in values.values() if v is not None]
    if not rows:
        return None
    return sum(rows)/len(rows)


def _excess(value: float | None, reference: float) -> float | None:
    if value is None:
        return None
    return max(0.0,float(value)-reference)


def evaluate_candidate_outcome(
    *,
    label: str,
    origin: Mapping[str, Any],
    future: Mapping[str, Any],
    objective: MultiEnvironmentObjective,
    actuator_motion_pct: float=0.0,
    safety_violation: bool=False,
    candidate_kind: str="strategy",
) -> dict[str, Any]:
    """Return an inspectable multi-objective outcome vector.

    Expected state keys are optional and may be unavailable:
    `co2_ppm`, `pm25_ug_m3` are zone->value mappings;
    `temperature_c`, `relative_humidity_pct` may be zone->value mappings.

    Missing fields remain unavailable and are never scored as zero.
    """
    origin_co2=_mean_available(origin.get("co2_ppm"))
    future_co2=_mean_available(future.get("co2_ppm"))
    origin_pm25=_mean_available(origin.get("pm25_ug_m3"))
    future_pm25=_mean_available(future.get("pm25_ug_m3"))
    future_temp=_mean_available(future.get("temperature_c"))
    future_rh=_mean_available(future.get("relative_humidity_pct"))

    co2_excess=_excess(future_co2,objective.co2_reference_ppm)
    pm25_excess=_excess(future_pm25,objective.pm25_reference_ug_m3)
    temp_discomfort=(
        objective.temperature_band_c.distance(future_temp)
        if future_temp is not None else None
    )
    humidity_discomfort=(
        objective.humidity_band_pct.distance(future_rh)
        if future_rh is not None else None
    )
    temperature_scale=max(
        1.0,
        objective.temperature_band_c.maximum-objective.temperature_band_c.minimum,
    )
    humidity_scale=max(
        1.0,
        objective.humidity_band_pct.maximum-objective.humidity_band_pct.minimum,
    )

    physical_vector={
        "co2_excess_ppm":co2_excess,
        "pm25_excess_ug_m3":pm25_excess,
        "temperature_discomfort_c":temp_discomfort,
        "humidity_discomfort_pct":humidity_discomfort,
        "actuator_motion_pct":abs(float(actuator_motion_pct)),
        "safety_violation":1.0 if safety_violation else 0.0,
    }
    vector={
        "co2_excess_ratio":(
            co2_excess/objective.co2_reference_ppm
            if co2_excess is not None else None
        ),
        "pm25_excess_ratio":(
            pm25_excess/max(1.0,objective.pm25_reference_ug_m3)
            if pm25_excess is not None else None
        ),
        "temperature_discomfort_ratio":(
            temp_discomfort/temperature_scale
            if temp_discomfort is not None else None
        ),
        "humidity_discomfort_ratio":(
            humidity_discomfort/humidity_scale
            if humidity_discomfort is not None else None
        ),
        "actuator_motion_ratio":abs(float(actuator_motion_pct))/100.0,
        "safety_violation":1.0 if safety_violation else 0.0,
    }

    deltas={
        "mean_co2_ppm":(
            future_co2-origin_co2
            if origin_co2 is not None and future_co2 is not None else None
        ),
        "mean_pm25_ug_m3":(
            future_pm25-origin_pm25
            if origin_pm25 is not None and future_pm25 is not None else None
        ),
    }

    scored={}
    for key,value in vector.items():
        if value is None:
            continue
        scored[key]=float(value)*float(objective.weights.get(key,0.0))
    return {
        "label":label,
        "candidate_kind":candidate_kind,
        "physical_outcome_vector":physical_vector,
        "normalized_penalty_vector":vector,
        "deltas":deltas,
        "available_objectives":sorted(scored),
        "unavailable_objectives":sorted(k for k,v in vector.items() if v is None),
        "score":sum(scored.values()),
        "score_direction":"lower-is-better",
        "claim_boundary":(
            "score ranks only dimensionless normalized penalties for available "
            "declared objectives; physical units remain separately visible and "
            "unavailable environmental fields are not imputed"
        ),
    }


def hold_candidate(origin: Mapping[str, Any], objective: MultiEnvironmentObjective) -> dict[str, Any]:
    return evaluate_candidate_outcome(
        label="HOLD",
        origin=origin,
        future=origin,
        objective=objective,
        actuator_motion_pct=0.0,
        safety_violation=False,
        candidate_kind="hold",
    )


def rank_candidate_outcomes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        raise ValueError("at least one candidate outcome is required")
    return sorted(rows,key=lambda row:(float(row["score"]),str(row["label"])))


def _opening_motion_from_states(
    origin: Mapping[str, Any],
    future: Mapping[str, Any],
) -> float:
    before=origin.get("opening_pct") or {}
    after=future.get("opening_pct") or {}
    if not isinstance(before,Mapping) or not isinstance(after,Mapping):
        return 0.0
    shared=set(before)&set(after)
    return sum(abs(float(after[key])-float(before[key])) for key in shared)


def evaluate_observation_branch(
    *,
    label: str,
    observations: list[Mapping[str, Any]],
    objective: MultiEnvironmentObjective,
    origin: Mapping[str, Any] | None=None,
    safety_violation: bool=False,
    candidate_kind: str="strategy",
) -> dict[str, Any]:
    """Project an existing simulator/controller branch into the objective contract.

    This adapter consumes backend observations as-is. It never synthesizes
    PM2.5, temperature, humidity, TVOC or HCHO when a backend does not emit them.
    """
    if not observations:
        raise ValueError("candidate branch requires at least one observation")
    start=dict(origin or observations[0])
    future=dict(observations[-1])
    motion=_opening_motion_from_states(start,future)
    return evaluate_candidate_outcome(
        label=label,
        origin=start,
        future=future,
        objective=objective,
        actuator_motion_pct=motion,
        safety_violation=safety_violation,
        candidate_kind=candidate_kind,
    )
