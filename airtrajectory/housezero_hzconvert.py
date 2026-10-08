"""Adapter for slitvinov/hzconvert canonical HouseZero rows.

This module is deliberately data-file agnostic: it consumes one mapping-like
row from hzconvert's wide data.csv and projects only fields whose semantics are
explicit in that public canonical header vocabulary.

It never promotes missing values into measurements and keeps window positions
outside EnvironmentalState because they are physical opening observations.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Iterable

from .environmental_state import (
    EnvironmentalState,
    EnvironmentalValue,
    OutdoorEnvironmentalState,
    ZoneEnvironmentalState,
)


def _missing(value: Any) -> bool:
    if value is None or value == "":
        return True
    try:
        return not math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _float_or_none(value: Any) -> float | None:
    if _missing(value):
        return None
    return float(value)


def _fahrenheit_to_c(value: float) -> float:
    return (float(value) - 32.0) * 5.0 / 9.0


def _measured_or_unavailable(
    value: Any,
    *,
    observed_at: str,
    source_id: str,
    transform=None,
) -> EnvironmentalValue:
    parsed = _float_or_none(value)
    if parsed is None:
        return EnvironmentalValue(None, "unavailable")
    if transform is not None:
        parsed = transform(parsed)
    return EnvironmentalValue(
        parsed,
        "measured",
        observed_at=observed_at,
        confidence=1.0,
        source_id=source_id,
    )


def _rain_value(
    value: Any,
    *,
    observed_at: str,
    source_id: str,
) -> EnvironmentalValue:
    if _missing(value):
        return EnvironmentalValue(None, "unavailable")
    if isinstance(value, bool):
        parsed = value
    elif isinstance(value, str):
        token = value.strip().lower()
        if token in {"true", "yes", "rain", "1"}:
            parsed = True
        elif token in {"false", "no", "dry", "0"}:
            parsed = False
        else:
            parsed = bool(float(token))
    else:
        parsed = bool(float(value))
    return EnvironmentalValue(
        parsed,
        "measured",
        observed_at=observed_at,
        confidence=1.0,
        source_id=source_id,
    )


def discover_hzconvert_zone_ids(columns: Iterable[str]) -> list[str]:
    """Return zone IDs that expose at least one AirTrajectory state signal."""

    ids = set()
    suffixes = {"/co2", "/air_temperature", "/humidity"}
    for column in columns:
        if not column.startswith("zone/"):
            continue
        if not any(column.endswith(suffix) for suffix in suffixes):
            continue
        parts = column.split("/")
        if len(parts) >= 3 and parts[1]:
            ids.add(parts[1])
    return sorted(ids)


def adapt_hzconvert_row(
    row: Mapping[str, Any],
    *,
    topology_id: str,
    timestamp_field: str = "timestamp",
    zone_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Project one hzconvert row into AirTrajectory's portable contracts.

    Returns an observation bundle with:
    - Environmental State v0.1-compatible payload;
    - measured window-opening percentages keyed by hzconvert canonical header;
    - explicit source/provenance boundary.
    """

    observed_at = str(row.get(timestamp_field) or "")
    if not observed_at:
        raise ValueError("hzconvert row requires a timestamp")

    zones = (
        list(zone_ids)
        if zone_ids is not None
        else discover_hzconvert_zone_ids(row.keys())
    )
    if not zones:
        raise ValueError("hzconvert row exposes no zone environment signals")

    zone_states = {}
    for zone_id in zones:
        prefix = f"zone/{zone_id}/"
        zone_states[zone_id] = ZoneEnvironmentalState(
            zone_id,
            {
                "co2_ppm": _measured_or_unavailable(
                    row.get(prefix + "co2"),
                    observed_at=observed_at,
                    source_id=prefix + "co2",
                ),
                "temperature_c": _measured_or_unavailable(
                    row.get(prefix + "air_temperature"),
                    observed_at=observed_at,
                    source_id=prefix + "air_temperature",
                    transform=_fahrenheit_to_c,
                ),
                "relative_humidity_pct": _measured_or_unavailable(
                    row.get(prefix + "humidity"),
                    observed_at=observed_at,
                    source_id=prefix + "humidity",
                ),
            },
        )

    outdoor = OutdoorEnvironmentalState(
        values={
            "temperature_c": _measured_or_unavailable(
                row.get("outdoor/weather/air_temperature"),
                observed_at=observed_at,
                source_id="outdoor/weather/air_temperature",
                transform=_fahrenheit_to_c,
            ),
            "relative_humidity_pct": _measured_or_unavailable(
                row.get("outdoor/weather/humidity"),
                observed_at=observed_at,
                source_id="outdoor/weather/humidity",
            ),
            "wind_speed_m_s": _measured_or_unavailable(
                row.get("outdoor/weather/wind_speed"),
                observed_at=observed_at,
                source_id="outdoor/weather/wind_speed",
            ),
            "wind_direction_deg": _measured_or_unavailable(
                row.get("outdoor/weather/wind_direction"),
                observed_at=observed_at,
                source_id="outdoor/weather/wind_direction",
            ),
            "rain": _rain_value(
                row.get("outdoor/weather/rain"),
                observed_at=observed_at,
                source_id="outdoor/weather/rain",
            ),
        }
    )

    state = EnvironmentalState(
        topology_id=topology_id,
        zones=zone_states,
        outdoor=outdoor,
    )

    openings = {}
    for key, raw in row.items():
        if "/window_opening/" not in key or not key.startswith("zone/"):
            continue
        value = _float_or_none(raw)
        openings[key] = {
            "position_pct": value,
            "evidence": "measured" if value is not None else "unavailable",
            "observed_at": observed_at if value is not None else None,
            "source_id": key if value is not None else None,
        }

    return {
        "schema_version": "0.1",
        "adapter": "housezero-hzconvert-row-v0.1",
        "source_project": "slitvinov/hzconvert",
        "source_semantics": "hzconvert canonical data.csv headers",
        "observed_at": observed_at,
        "environmental_state": state.as_dict(),
        "opening_observations": {
            key: openings[key] for key in sorted(openings)
        },
        "evidence_boundary": (
            "adapts public hzconvert canonical columns only; no missing value "
            "is promoted to measured evidence and no HouseZero topology is invented"
        ),
    }
