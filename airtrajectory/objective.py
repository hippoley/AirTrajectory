"""User-facing objective semantics for AirTrajectory.

The contract is deliberately independent of the policy, physics backend and
language model used to obtain it.  It preserves hard constraints and ordered
priorities instead of collapsing every trade-off into one reward scalar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Mapping


_ALLOWED_POLLUTANTS = {"co2_ppm", "pm25_ug_m3", "tvoc_ug_m3", "hcho_mg_m3"}
_ALLOWED_PRIORITIES = {
    "co2_excess",
    "pm25_excess",
    "temperature_discomfort",
    "humidity_discomfort",
    "movement",
}


@dataclass(frozen=True)
class PollutantGoal:
    field: str
    target_max: float
    hard_max: float | None = None

    def __post_init__(self) -> None:
        if self.field not in _ALLOWED_POLLUTANTS:
            raise ValueError(f"unsupported pollutant objective: {self.field}")
        if not isfinite(self.target_max) or self.target_max < 0:
            raise ValueError("pollutant target_max must be finite and non-negative")
        if self.hard_max is not None and (
            not isfinite(self.hard_max) or self.hard_max < self.target_max
        ):
            raise ValueError("pollutant hard_max must be finite and not below target_max")

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "target_max": float(self.target_max),
            "hard_max": None if self.hard_max is None else float(self.hard_max),
        }


@dataclass(frozen=True)
class ComfortBand:
    field: str
    minimum: float
    maximum: float
    preferred: float | None = None
    hard_minimum: float | None = None
    hard_maximum: float | None = None

    def __post_init__(self) -> None:
        if self.field not in {"temperature_c", "relative_humidity_pct"}:
            raise ValueError(f"unsupported comfort field: {self.field}")
        if not all(isfinite(value) for value in (
            self.minimum, self.maximum, *(
                value for value in (self.preferred, self.hard_minimum, self.hard_maximum)
                if value is not None
            )
        )):
            raise ValueError("comfort values must be finite")
        if self.minimum > self.maximum:
            raise ValueError("comfort minimum cannot exceed maximum")
        if self.preferred is not None and not self.minimum <= self.preferred <= self.maximum:
            raise ValueError("preferred comfort value must be inside the soft band")
        if self.hard_minimum is not None and self.hard_minimum > self.minimum:
            raise ValueError("hard_minimum must not be stricter than the soft minimum")
        if self.hard_maximum is not None and self.hard_maximum < self.maximum:
            raise ValueError("hard_maximum must not be stricter than the soft maximum")

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "minimum": float(self.minimum),
            "maximum": float(self.maximum),
            "preferred": None if self.preferred is None else float(self.preferred),
            "hard_minimum": (
                None if self.hard_minimum is None else float(self.hard_minimum)
            ),
            "hard_maximum": (
                None if self.hard_maximum is None else float(self.hard_maximum)
            ),
        }


@dataclass(frozen=True)
class ObjectiveContract:
    objective_id: str
    pollutants: Mapping[str, PollutantGoal] = field(default_factory=dict)
    comfort: Mapping[str, ComfortBand] = field(default_factory=dict)
    priorities: tuple[str, ...] = ()
    rain_hard_constraint: bool = True
    max_intervention_min: float | None = None
    minimize_movement: bool = True
    source_text: str | None = None
    schema_version: str = "0.1"

    def __post_init__(self) -> None:
        if not self.objective_id:
            raise ValueError("objective_id is required")
        if any(key != goal.field for key, goal in self.pollutants.items()):
            raise ValueError("pollutant mapping keys must match goal.field")
        if any(key != band.field for key, band in self.comfort.items()):
            raise ValueError("comfort mapping keys must match band.field")
        unknown = set(self.priorities) - _ALLOWED_PRIORITIES
        if unknown:
            raise ValueError(f"unsupported objective priorities: {sorted(unknown)}")
        if len(set(self.priorities)) != len(self.priorities):
            raise ValueError("objective priorities must be unique")
        if self.max_intervention_min is not None and (
            not isfinite(self.max_intervention_min) or self.max_intervention_min <= 0
        ):
            raise ValueError("max_intervention_min must be finite and positive")
        allowed_by_contract = {"movement"}
        if "co2_ppm" in self.pollutants:
            allowed_by_contract.add("co2_excess")
        if "pm25_ug_m3" in self.pollutants:
            allowed_by_contract.add("pm25_excess")
        if "temperature_c" in self.comfort:
            allowed_by_contract.add("temperature_discomfort")
        if "relative_humidity_pct" in self.comfort:
            allowed_by_contract.add("humidity_discomfort")
        missing = set(self.priorities) - allowed_by_contract
        if missing:
            raise ValueError(f"priority has no declared objective metric: {sorted(missing)}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "objective_id": self.objective_id,
            "pollutants": {
                key: self.pollutants[key].as_dict()
                for key in sorted(self.pollutants)
            },
            "comfort": {
                key: self.comfort[key].as_dict()
                for key in sorted(self.comfort)
            },
            "priorities": list(self.priorities),
            "rain_hard_constraint": self.rain_hard_constraint,
            "max_intervention_min": self.max_intervention_min,
            "minimize_movement": self.minimize_movement,
            "source_text": self.source_text,
            "decision_semantics": "hard-constraints-then-lexicographic-priorities",
        }


_PRESETS: dict[str, dict[str, Any]] = {
    "bedroom_stuffy": {
        "aliases": {
            "卧室空气太闷。",
            "卧室空气太闷",
            "the bedroom feels stuffy",
        },
        "pollutants": {
            "co2_ppm": PollutantGoal("co2_ppm", target_max=1000.0),
        },
        "comfort": {
            "temperature_c": ComfortBand(
                "temperature_c", 20.0, 26.0, preferred=23.0, hard_minimum=18.0
            ),
            "relative_humidity_pct": ComfortBand(
                "relative_humidity_pct", 40.0, 65.0
            ),
        },
        "priorities": ("co2_excess", "temperature_discomfort", "movement"),
        "max_intervention_min": 20.0,
    },
    "co2_vs_outdoor_pm25": {
        "aliases": {
            "今天外面 PM2.5 很高，尽量改善 CO₂，但别大量吸进室外污染。",
            "今天外面PM2.5很高，尽量改善CO₂，但别大量吸进室外污染。",
            "improve co2 without pulling in too much outdoor pm2.5",
        },
        "pollutants": {
            "co2_ppm": PollutantGoal("co2_ppm", target_max=1000.0),
            "pm25_ug_m3": PollutantGoal(
                "pm25_ug_m3", target_max=25.0, hard_max=35.0
            ),
        },
        "comfort": {
            "temperature_c": ComfortBand(
                "temperature_c", 20.0, 26.0, preferred=23.0, hard_minimum=18.0
            ),
            "relative_humidity_pct": ComfortBand(
                "relative_humidity_pct", 40.0, 65.0
            ),
        },
        "priorities": (
            "co2_excess",
            "pm25_excess",
            "temperature_discomfort",
            "movement",
        ),
        "max_intervention_min": 10.0,
    },
    "night_fresh_not_cold": {
        "aliases": {
            "晚上保持空气好一点，但不要太冷。",
            "晚上保持空气好一点，但不要太冷",
            "keep the air fresh tonight without making it too cold",
        },
        "pollutants": {
            "co2_ppm": PollutantGoal("co2_ppm", target_max=900.0),
        },
        "comfort": {
            "temperature_c": ComfortBand(
                "temperature_c", 20.0, 24.0, preferred=22.0, hard_minimum=19.0
            ),
            "relative_humidity_pct": ComfortBand(
                "relative_humidity_pct", 40.0, 65.0
            ),
        },
        "priorities": (
            "temperature_discomfort",
            "co2_excess",
            "movement",
        ),
        "max_intervention_min": 15.0,
    },
}


def objective_from_preset(
    preset_id: str,
    *,
    source_text: str | None = None,
) -> ObjectiveContract:
    spec = _PRESETS.get(preset_id)
    if spec is None:
        raise ValueError(f"unknown objective preset: {preset_id}")
    return ObjectiveContract(
        objective_id=preset_id,
        pollutants=spec["pollutants"],
        comfort=spec["comfort"],
        priorities=spec["priorities"],
        rain_hard_constraint=True,
        max_intervention_min=spec["max_intervention_min"],
        minimize_movement=True,
        source_text=source_text,
    )


def compile_user_goal(text: str) -> ObjectiveContract:
    """Compile a deliberately small deterministic product vocabulary.

    This is not an NLU claim.  An LLM/Rasa/other parser may later produce the
    same Objective Contract.  Exact preset examples keep the product semantics
    inspectable and testable today.
    """

    normalized = " ".join(str(text).strip().split()).lower()
    if not normalized:
        raise ValueError("user goal text is required")
    for preset_id, spec in _PRESETS.items():
        aliases = {" ".join(alias.strip().split()).lower() for alias in spec["aliases"]}
        if normalized in aliases:
            return objective_from_preset(preset_id, source_text=text)
    raise ValueError(
        "goal is outside the deterministic v0.1 preset vocabulary; "
        "do not invent objective weights"
    )
