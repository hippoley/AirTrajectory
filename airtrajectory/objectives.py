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
        "co2_excess": 1.0,
        "pm25_excess": 1.0,
        "temperature_discomfort": 1.0,
        "humidity_discomfort": 1.0,
        "actuator_motion": 0.1,
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

    vector={
        "co2_excess":_excess(future_co2,objective.co2_reference_ppm),
        "pm25_excess":_excess(future_pm25,objective.pm25_reference_ug_m3),
        "temperature_discomfort":(
            objective.temperature_band_c.distance(future_temp)
            if future_temp is not None else None
        ),
        "humidity_discomfort":(
            objective.humidity_band_pct.distance(future_rh)
            if future_rh is not None else None
        ),
        "actuator_motion":abs(float(actuator_motion_pct)),
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
        "outcome_vector":vector,
        "deltas":deltas,
        "available_objectives":sorted(scored),
        "unavailable_objectives":sorted(k for k,v in vector.items() if v is None),
        "score":sum(scored.values()),
        "score_direction":"lower-is-better",
        "claim_boundary":(
            "score ranks only available declared objectives; unavailable "
            "environmental fields are not imputed"
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
