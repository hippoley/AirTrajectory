"""Explicit PRJ serialization profile for concrete CONTAM stored fields.

This layer fills concrete Section 10/14/15 fields only from an explicit profile.
It does not infer engineering values from topology or UI geometry. Note that zone `initial_pressure_pa` maps directly to CONTAM zone P0; it is not the project barometric pressure.

Covered:
- Section 10 airflow element stored coefficients
- Section 14 zone level/height/initial thermodynamic state
- Section 15 contaminant molecular weight + ppmv -> mass-fraction conversion
- Section 2 species definitions
- Section 3 level records

Section 1 project controls and Section 16 path records remain later gates.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any


M_AIR_G_MOL = 28.96546
CONTAM_STD_AIR_DENSITY_KG_M3 = 1.20410
CONTAM_STD_AIR_SQRT_DENSITY = 1.097315
CONTAM_STD_AIR_VISCOSITY_PA_S = 1.81625e-5
CONTAM_MIN_TRANSITION_DP_PA = 1.0e-10


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def ppmv_to_mass_fraction(ppmv: float, molecular_weight_g_mol: float) -> float:
    value = float(ppmv)
    mw = float(molecular_weight_g_mol)
    if value < 0:
        raise ValueError("ppmv must be non-negative")
    if mw <= 0:
        raise ValueError("molecular_weight_g_mol must be positive")
    return value * (mw / M_AIR_G_MOL) / 1_000_000.0



def derive_nist_orifice_storage(
    *,
    flow_area_m2: float,
    discharge_coefficient: float,
    flow_exponent: float,
    transition_reynolds_number: float,
) -> dict[str, float]:
    """Derive CONTAM PL_ORFC stored coefficients using NIST's 3.0→3.1 upgrader equations."""
    area = float(flow_area_m2)
    coef = float(discharge_coefficient)
    expt = float(flow_exponent)
    reynolds = float(transition_reynolds_number)
    if area <= 0:
        raise ValueError("flow_area_m2 must be positive")
    if coef <= 0:
        raise ValueError("discharge_coefficient must be positive")
    if not 0 < expt <= 1:
        raise ValueError("flow_exponent must be in (0,1]")
    if reynolds <= 0:
        raise ValueError("transition_reynolds_number must be positive")

    diameter = math.sqrt((4.0 / math.pi) * area)
    turbulent = coef * area * math.sqrt(2.0)

    transition_mass_flow = (
        CONTAM_STD_AIR_VISCOSITY_PA_S
        * reynolds
        * area
        / diameter
    )
    transition_dp = (
        transition_mass_flow
        / (turbulent * CONTAM_STD_AIR_SQRT_DENSITY)
    ) ** (1.0 / expt)
    transition_dp = max(transition_dp, CONTAM_MIN_TRANSITION_DP_PA)
    laminar = (
        CONTAM_STD_AIR_VISCOSITY_PA_S
        * transition_mass_flow
        / (CONTAM_STD_AIR_DENSITY_KG_M3 * transition_dp)
    )
    return {
        "hydraulic_diameter_m": diameter,
        "laminar_flow_coefficient": laminar,
        "turbulent_flow_coefficient": turbulent,
        "transition_reynolds_number": reynolds,
    }


def validate_prj_profile(profile: dict[str, Any]) -> None:
    if not isinstance(profile, dict):
        raise ValueError("PRJ serialization profile must be an object")
    if profile.get("schema_version") != "0.1":
        raise ValueError("unsupported PRJ serialization profile schema_version")
    if not str(profile.get("profile_id") or ""):
        raise ValueError("PRJ serialization profile_id is required")

    zone_defaults = profile.get("zone_defaults")
    if not isinstance(zone_defaults, dict):
        raise ValueError("zone_defaults are required")
    if int(zone_defaults.get("level_number")) < 1:
        raise ValueError("zone level_number must be >=1")
    if float(zone_defaults.get("relative_height_m")) < 0:
        raise ValueError("zone relative_height_m must be non-negative")
    if float(zone_defaults.get("initial_temperature_k")) <= 0:
        raise ValueError("zone initial_temperature_k must be positive")
    if float(zone_defaults.get("initial_pressure_pa")) < 0:
        raise ValueError("zone initial_pressure_pa (CONTAM zone P0) must be non-negative")

    element_rules = profile.get("airflow_element_storage")
    if not isinstance(element_rules, dict) or not element_rules:
        raise ValueError("airflow_element_storage rules are required")
    for kind, rule in element_rules.items():
        mode = str(rule.get("mode") or "explicit")
        if mode == "nist-orifice-derived":
            if float(rule.get("transition_reynolds_number")) <= 0:
                raise ValueError(
                    f"airflow storage rule {kind} transition_reynolds_number must be positive"
                )
            continue
        if mode != "explicit":
            raise ValueError(f"airflow storage rule {kind} has unsupported mode")
        if float(rule.get("hydraulic_diameter_m")) <= 0:
            raise ValueError(
                f"airflow storage rule {kind} hydraulic_diameter_m must be positive"
            )
        if float(rule.get("laminar_flow_coefficient")) < 0:
            raise ValueError(
                f"airflow storage rule {kind} laminar_flow_coefficient must be non-negative"
            )
        if float(rule.get("turbulent_flow_coefficient")) < 0:
            raise ValueError(
                f"airflow storage rule {kind} turbulent_flow_coefficient must be non-negative"
            )
        if float(rule.get("transition_reynolds_number")) <= 0:
            raise ValueError(
                f"airflow storage rule {kind} transition_reynolds_number must be positive"
            )

    species = profile.get("species")
    if not isinstance(species, dict) or not species:
        raise ValueError("species definitions are required")
    for key, spec in species.items():
        if float(spec.get("molecular_weight_g_mol")) <= 0:
            raise ValueError(f"species {key} molecular_weight_g_mol must be positive")
        if spec.get("conversion") != "ppmv-to-mass-fraction-mw-ratio":
            raise ValueError(f"species {key} has unsupported conversion policy")

    project_controls = profile.get("project_controls")
    if not isinstance(project_controls, dict) or not project_controls:
        raise ValueError("project_controls are required")
    mode = str(project_controls.get("mode") or "")
    if mode not in {"steady", "transient"}:
        raise ValueError("project_controls mode must be steady or transient")
    if int(project_controls.get("time_step_s", 0)) <= 0:
        raise ValueError("project_controls time_step_s must be positive")
    for field in ("start", "stop"):
        value = str(project_controls.get(field) or "")
        parts = value.split(":")
        if len(parts) != 3:
            raise ValueError(f"project_controls {field} must be HH:MM:SS")
        try:
            hh, mm, ss = [int(part) for part in parts]
        except ValueError as exc:
            raise ValueError(f"project_controls {field} must be HH:MM:SS") from exc
        if not (0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59):
            raise ValueError(f"project_controls {field} must be HH:MM:SS")

    path_records = profile.get("path_records")
    if not isinstance(path_records, dict) or not path_records:
        raise ValueError("path_records are required")
    required_path_fields = (
        "prj_flags", "filter_number", "wind_profile_number", "ahs_number",
        "schedule_number", "level_number", "x_m", "y_m",
        "relative_height_m", "element_multiplier",
        "constant_wind_pressure_pa", "wind_speed_modifier",
    )
    for path_key, record in path_records.items():
        if not isinstance(record, dict):
            raise ValueError(f"path record {path_key} must be an object")
        missing = [field for field in required_path_fields if field not in record]
        if missing:
            raise ValueError(
                f"path record {path_key} missing fields: " + ",".join(missing)
            )


def bind_prj_serialization_profile(
    manifest: dict[str, Any],
    profile: dict[str, Any],
    *,
    require_engineering_validated: bool = False,
) -> dict[str, Any]:
    if manifest.get("compiler") != "contam-forced-manifest":
        raise ValueError("payload is not a forced CONTAM manifest")
    validate_prj_profile(profile)
    if require_engineering_validated and profile.get("engineering_validated") is not True:
        raise ValueError("engineering-validated PRJ serialization profile is required")

    zone_defaults = profile["zone_defaults"]
    zone_overrides = profile.get("zone_overrides") or {}
    known_zones = {zone["key"] for zone in manifest.get("zones") or []}
    unknown_zone_overrides = set(zone_overrides) - known_zones
    if unknown_zone_overrides:
        raise ValueError(
            "PRJ profile zone overrides reference unknown zones: "
            + ",".join(sorted(unknown_zone_overrides))
        )

    zones = []
    for zone in manifest.get("zones") or []:
        cfg = {**zone_defaults, **(zone_overrides.get(zone["key"]) or {})}
        zones.append(
            {
                **zone,
                "level_number": int(cfg["level_number"]),
                "relative_height_m": float(cfg["relative_height_m"]),
                "initial_temperature_k": float(cfg["initial_temperature_k"]),
                "initial_pressure_pa": float(cfg["initial_pressure_pa"]),
            }
        )

    storage_rules = profile["airflow_element_storage"]
    path_kind = {
        path["layout_opening_id"]: path["kind"]
        for path in manifest.get("flow_paths") or []
    }
    airflow_elements = []
    for element in manifest.get("airflow_elements") or []:
        kind = path_kind.get(element["layout_opening_id"])
        rule = storage_rules.get(kind)
        if rule is None:
            raise ValueError(
                f"PRJ profile has no airflow storage rule for opening kind {kind}"
            )
        mode = str(rule.get("mode") or "explicit")
        if mode == "nist-orifice-derived":
            storage = derive_nist_orifice_storage(
                flow_area_m2=element["flow_area_m2"],
                discharge_coefficient=element["discharge_coefficient"],
                flow_exponent=element["flow_exponent"],
                transition_reynolds_number=rule["transition_reynolds_number"],
            )
        else:
            storage = {
                "hydraulic_diameter_m": float(rule["hydraulic_diameter_m"]),
                "laminar_flow_coefficient": float(
                    rule["laminar_flow_coefficient"]
                ),
                "turbulent_flow_coefficient": float(
                    rule["turbulent_flow_coefficient"]
                ),
                "transition_reynolds_number": float(
                    rule["transition_reynolds_number"]
                ),
            }
        airflow_elements.append({**element, **storage})

    species_profile = profile["species"]
    contaminants = []
    species_definitions = []
    for contaminant in manifest.get("contaminants") or []:
        key = contaminant["key"]
        spec = species_profile.get(key)
        if spec is None:
            raise ValueError(f"PRJ profile has no species definition for {key}")
        mw = float(spec["molecular_weight_g_mol"])
        conversion = str(spec["conversion"])
        initial_ppm = contaminant["initial_zone_concentration"]
        initial_mass_fraction = {
            zone_key: ppmv_to_mass_fraction(ppm, mw)
            for zone_key, ppm in initial_ppm.items()
        }
        outdoor_mass_fraction = ppmv_to_mass_fraction(
            contaminant["outdoor_concentration"],
            mw,
        )
        contaminants.append(
            {
                **contaminant,
                "molecular_weight_g_mol": mw,
                "mass_fraction_conversion": conversion,
                "outdoor_mass_fraction": outdoor_mass_fraction,
                "initial_zone_mass_fraction": initial_mass_fraction,
            }
        )
        species_definitions.append(
            {
                "key": key,
                "name": contaminant["name"],
                "contam_contaminant_number": contaminant[
                    "contam_contaminant_number"
                ],
                "molecular_weight_g_mol": mw,
                "conversion": conversion,
                "outdoor_mass_fraction": outdoor_mass_fraction,
            }
        )

    path_records = profile["path_records"]
    known_paths = {path["key"] for path in manifest.get("flow_paths") or []}
    unknown_path_records = set(path_records) - known_paths
    missing_path_records = known_paths - set(path_records)
    if unknown_path_records:
        raise ValueError(
            "PRJ profile path records reference unknown paths: "
            + ",".join(sorted(unknown_path_records))
        )
    if missing_path_records:
        raise ValueError(
            "PRJ profile path records missing paths: "
            + ",".join(sorted(missing_path_records))
        )

    flow_paths = []
    for path in manifest.get("flow_paths") or []:
        record = path_records[path["key"]]
        flow_paths.append(
            {
                **path,
                "prj_flags": int(record["prj_flags"]),
                "filter_number": int(record["filter_number"]),
                "wind_profile_number": int(record["wind_profile_number"]),
                "ahs_number": int(record["ahs_number"]),
                "schedule_number": int(record["schedule_number"]),
                "level_number": int(record["level_number"]),
                "x_m": float(record["x_m"]),
                "y_m": float(record["y_m"]),
                "relative_height_m": float(record["relative_height_m"]),
                "element_multiplier": float(record["element_multiplier"]),
                "constant_wind_pressure_pa": float(record["constant_wind_pressure_pa"]),
                "wind_speed_modifier": float(record["wind_speed_modifier"]),
            }
        )

    level_numbers = sorted({zone["level_number"] for zone in zones})
    level_records = [
        {
            "level_number": level,
            "name": str(
                (profile.get("levels") or {}).get(str(level), {}).get("name")
                or f"Level {level}"
            ),
            "reference_height_m": float(
                (profile.get("levels") or {}).get(str(level), {}).get(
                    "reference_height_m",
                    0.0,
                )
            ),
        }
        for level in level_numbers
    ]

    profile_sha = _sha256(profile)
    binding_payload = {
        "profile_sha256": profile_sha,
        "zones": sorted(zones, key=lambda item: item["key"]),
        "airflow_elements": sorted(
            airflow_elements,
            key=lambda item: item["key"],
        ),
        "flow_paths": sorted(flow_paths, key=lambda item: item["key"]),
        "project_controls": profile["project_controls"],
        "species_definitions": sorted(
            species_definitions,
            key=lambda item: item["key"],
        ),
        "level_records": level_records,
    }

    return {
        **manifest,
        "compiler": "contam-prj-profiled-manifest",
        "status": "READY_FOR_PRJ_SERIALIZATION_AUDIT",
        "prj_serialization_profile": {
            "profile_id": profile["profile_id"],
            "profile_sha256": profile_sha,
            "evidence_level": profile.get("evidence_level"),
            "engineering_validated": profile.get("engineering_validated") is True,
            "source": profile.get("source"),
            "evidence_receipts": list(profile.get("evidence_receipts") or []),
        },
        "zones": zones,
        "airflow_elements": airflow_elements,
        "flow_paths": flow_paths,
        "contaminants": contaminants,
        "species_definitions": species_definitions,
        "level_records": level_records,
        "project_controls": dict(profile["project_controls"]),
        "prj_profile_binding_sha256": _sha256(binding_payload),
    }
