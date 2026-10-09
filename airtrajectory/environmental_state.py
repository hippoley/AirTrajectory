"""Canonical multi-environment state contract for AirTrajectory.

This contract is deliberately policy- and physics-neutral.  Every value keeps
its evidence class so estimates/simulations can be used without being relabeled
as measurements.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from math import isfinite


EVIDENCE_CLASSES = {"measured", "estimated", "simulated", "stale", "unavailable"}

INDOOR_FIELDS = {
    "co2_ppm",
    "pm25_ug_m3",
    "temperature_c",
    "relative_humidity_pct",
    "tvoc_ug_m3",
    "hcho_mg_m3",
    "occupancy_count",
}
OUTDOOR_FIELDS = {
    "pm25_ug_m3",
    "temperature_c",
    "relative_humidity_pct",
    "wind_speed_m_s",
    "wind_direction_deg",
    "rain",
    "pressure_pa",
}


@dataclass(frozen=True)
class EnvironmentalValue:
    value: float | bool | None
    evidence: str
    observed_at: str | None = None
    confidence: float | None = None
    source_id: str | None = None

    def __post_init__(self) -> None:
        if self.evidence not in EVIDENCE_CLASSES:
            raise ValueError(f"unsupported evidence class: {self.evidence}")
        if self.evidence == "unavailable" and self.value is not None:
            raise ValueError("unavailable values must be null")
        if self.evidence == "measured" and self.value is None:
            raise ValueError("measured values cannot be null")
        if isinstance(self.value, (int, float)) and not isinstance(self.value, bool):
            if not isfinite(self.value) or self.value < 0:
                raise ValueError("environmental measurement must be finite and nonnegative")
        if self.confidence is not None and not isfinite(self.confidence):
            raise ValueError("confidence must be finite")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0,1]")

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "evidence": self.evidence,
            "observed_at": self.observed_at,
            "confidence": self.confidence,
            "source_id": self.source_id,
        }


@dataclass(frozen=True)
class ZoneEnvironmentalState:
    zone_id: str
    values: Mapping[str, EnvironmentalValue] = field(default_factory=dict)
    source_terms: Mapping[str, EnvironmentalValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        unknown = set(self.values) - INDOOR_FIELDS
        if unknown:
            raise ValueError(f"unsupported indoor fields: {sorted(unknown)}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "values": {
                key: self.values[key].as_dict()
                for key in sorted(self.values)
            },
            "source_terms": {
                key: self.source_terms[key].as_dict()
                for key in sorted(self.source_terms)
            },
        }


@dataclass(frozen=True)
class OutdoorEnvironmentalState:
    boundary_id: str = "OUTSIDE"
    values: Mapping[str, EnvironmentalValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        unknown = set(self.values) - OUTDOOR_FIELDS
        if unknown:
            raise ValueError(f"unsupported outdoor fields: {sorted(unknown)}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "boundary_id": self.boundary_id,
            "values": {
                key: self.values[key].as_dict()
                for key in sorted(self.values)
            },
        }


@dataclass(frozen=True)
class EnvironmentalState:
    topology_id: str
    zones: Mapping[str, ZoneEnvironmentalState]
    outdoor: OutdoorEnvironmentalState
    schema_version: str = "0.1"

    def __post_init__(self) -> None:
        if not self.topology_id:
            raise ValueError("topology_id is required")
        if not self.zones:
            raise ValueError("environmental state requires at least one zone")
        if any(key != zone.zone_id for key, zone in self.zones.items()):
            raise ValueError("zone mapping keys must match zone_id")

    def require_topology(self, topology) -> None:
        expected = set(topology.zones)
        actual = set(self.zones)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise ValueError(
                f"environmental state topology mismatch: missing={missing} extra={extra}"
            )

    def measured_fraction(self) -> float:
        values = [
            value
            for zone in self.zones.values()
            for value in zone.values.values()
        ] + list(self.outdoor.values.values())
        available = [v for v in values if v.evidence != "unavailable"]
        if not available:
            return 0.0
        return sum(v.evidence == "measured" for v in available) / len(available)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "topology_id": self.topology_id,
            "zones": {
                key: self.zones[key].as_dict()
                for key in sorted(self.zones)
            },
            "outdoor": self.outdoor.as_dict(),
            "quality": {
                "measured_fraction": self.measured_fraction(),
            },
        }
