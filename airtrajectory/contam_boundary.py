"""Weather/wind and contaminant contracts for CONTAM writer manifests.

These contracts make ambient forcing explicit and auditable before PRJ
serialization. They do not claim to reproduce a full weather file or contaminant
schedule; they define the minimum stable inputs the writer must consume.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def validate_boundary_profile(profile: dict[str, Any]) -> None:
    if not isinstance(profile, dict):
        raise ValueError("boundary profile must be an object")
    if profile.get("schema_version") != "0.1":
        raise ValueError("unsupported boundary profile schema_version")
    if not str(profile.get("profile_id") or ""):
        raise ValueError("boundary profile_id is required")

    weather = profile.get("weather")
    if not isinstance(weather, dict):
        raise ValueError("weather profile is required")
    wind_speed = float(weather.get("wind_speed_m_s"))
    wind_direction = float(weather.get("wind_direction_deg"))
    outdoor_temp = float(weather.get("outdoor_temperature_c"))
    pressure = float(weather.get("barometric_pressure_pa"))
    if wind_speed < 0:
        raise ValueError("wind_speed_m_s must be non-negative")
    if not 0 <= wind_direction < 360:
        raise ValueError("wind_direction_deg must be in [0,360)")
    if not -100 <= outdoor_temp <= 100:
        raise ValueError("outdoor_temperature_c is outside supported range")
    if not 30000 <= pressure <= 120000:
        raise ValueError("barometric_pressure_pa is outside supported range")

    contaminants = profile.get("contaminants")
    if not isinstance(contaminants, list) or not contaminants:
        raise ValueError("at least one contaminant definition is required")
    seen = set()
    for contaminant in contaminants:
        if not isinstance(contaminant, dict):
            raise ValueError("contaminant definition must be an object")
        key = str(contaminant.get("key") or "")
        if not key:
            raise ValueError("contaminant key is required")
        if key in seen:
            raise ValueError(f"duplicate contaminant key {key}")
        seen.add(key)
        if contaminant.get("unit") != "ppm":
            raise ValueError(
                f"contaminant {key} currently requires unit=ppm"
            )
        outdoor = float(contaminant.get("outdoor_concentration"))
        if outdoor < 0:
            raise ValueError(
                f"contaminant {key} outdoor concentration must be non-negative"
            )
        initial = contaminant.get("initial_zone_concentration")
        if not isinstance(initial, dict) or not initial:
            raise ValueError(
                f"contaminant {key} initial_zone_concentration is required"
            )
        for zone_key, value in initial.items():
            if float(value) < 0:
                raise ValueError(
                    f"contaminant {key} zone {zone_key} concentration must be non-negative"
                )


def bind_boundary_profile(
    bound_manifest: dict[str, Any],
    profile: dict[str, Any],
    *,
    require_engineering_validated: bool = False,
) -> dict[str, Any]:
    """Attach explicit ambient/weather and contaminant inputs."""

    if bound_manifest.get("compiler") != "contam-bound-manifest":
        raise ValueError("payload is not an airflow-bound CONTAM manifest")
    validate_boundary_profile(profile)
    if require_engineering_validated and profile.get("engineering_validated") is not True:
        raise ValueError("engineering-validated boundary profile is required")

    zone_keys = {item["key"] for item in bound_manifest.get("zones") or []}
    contaminants = []
    for contaminant in profile["contaminants"]:
        initial = {
            str(key): float(value)
            for key, value in contaminant["initial_zone_concentration"].items()
        }
        unknown = set(initial) - zone_keys
        missing = zone_keys - set(initial)
        if unknown:
            raise ValueError(
                "contaminant initial concentrations reference unknown zones: "
                + ",".join(sorted(unknown))
            )
        if missing:
            raise ValueError(
                "contaminant initial concentrations missing zones: "
                + ",".join(sorted(missing))
            )
        contaminants.append(
            {
                "key": str(contaminant["key"]),
                "name": str(contaminant.get("name") or contaminant["key"]),
                "unit": "ppm",
                "outdoor_concentration": float(
                    contaminant["outdoor_concentration"]
                ),
                "initial_zone_concentration": initial,
                "contam_contaminant_number": None,
            }
        )

    contaminant_numbers = {
        key: index
        for index, key in enumerate(
            sorted(item["key"] for item in contaminants),
            start=1,
        )
    }
    contaminants = [
        {
            **item,
            "contam_contaminant_number": contaminant_numbers[item["key"]],
        }
        for item in contaminants
    ]

    weather = {
        "wind_speed_m_s": float(profile["weather"]["wind_speed_m_s"]),
        "wind_direction_deg": float(profile["weather"]["wind_direction_deg"]),
        "outdoor_temperature_c": float(
            profile["weather"]["outdoor_temperature_c"]
        ),
        "barometric_pressure_pa": float(
            profile["weather"]["barometric_pressure_pa"]
        ),
        "wind_pressure_model": str(
            profile["weather"].get("wind_pressure_model")
            or "facade-azimuth-placeholder"
        ),
    }

    payload = {
        "profile_id": profile["profile_id"],
        "profile_sha256": _sha256(profile),
        "weather": weather,
        "contaminants": sorted(
            contaminants,
            key=lambda item: item["key"],
        ),
        "contaminant_numbers": contaminant_numbers,
    }

    writer_contract = dict(bound_manifest.get("writer_contract") or {})
    writer_contract["weather/wind_profile"] = "implemented"
    writer_contract["contaminant_definition"] = "implemented"
    writer_contract["prj_serialization"] = "reserved"
    writer_contract["ready"] = False

    return {
        **bound_manifest,
        "compiler": "contam-forced-manifest",
        "status": "READY_FOR_PRJ_SERIALIZATION",
        "boundary_profile": {
            "profile_id": profile["profile_id"],
            "profile_sha256": payload["profile_sha256"],
            "evidence_level": profile.get("evidence_level"),
            "engineering_validated": profile.get("engineering_validated") is True,
            "source": profile.get("source"),
        },
        "weather": weather,
        "contaminants": contaminants,
        "contaminant_numbers": contaminant_numbers,
        "boundary_binding_sha256": _sha256(payload),
        "writer_contract": writer_contract,
    }
