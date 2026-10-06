"""CONTAM PRJ serialization readiness audit.

This module maps a forced CONTAM manifest onto the concrete fields required by
the NIST CONTAM 3.4 PRJ sections we intend to serialize first. It intentionally
does not write a .prj until all required fields are explicit.

Covered first-pass sections:
- Section 10: Airflow Elements
- Section 14: Zones
- Section 15: Initial Zone Concentrations
- Section 16: Airflow Paths

The audit is fail-closed and entity-specific.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def audit_prj_readiness(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("compiler") != "contam-forced-manifest":
        raise ValueError("payload is not a forced CONTAM manifest")

    missing: dict[str, dict[str, list[str]]] = {
        "section_10_airflow_elements": {},
        "section_14_zones": {},
        "section_15_initial_concentrations": {},
        "section_16_airflow_paths": {},
        "global": {},
    }

    # Section 10: PL_ORFC needs stored lam/turb/expt/area/dia/coef/Re/unit fields.
    for element in manifest.get("airflow_elements") or []:
        fields: list[str] = []
        if element.get("flow_exponent") is None:
            fields.append("expt")
        if element.get("flow_area_m2") is None:
            fields.append("area")
        if element.get("discharge_coefficient") is None:
            fields.append("coef")
        if element.get("hydraulic_diameter_m") is None:
            fields.append("dia")
        # These are stored PRJ values and must not be guessed from higher-level
        # semantics without an explicit calibration/conversion policy.
        if element.get("laminar_flow_coefficient") is None:
            fields.append("lam")
        if element.get("turbulent_flow_coefficient") is None:
            fields.append("turb")
        if element.get("transition_reynolds_number") is None:
            fields.append("Re")
        if fields:
            missing["section_10_airflow_elements"][element["key"]] = fields

    # Section 14 requires concrete zone placement/state metadata in addition to volume.
    for zone in manifest.get("zones") or []:
        fields: list[str] = []
        required = {
            "level_number": "pl",
            "relative_height_m": "relHt",
            "initial_temperature_k": "T0",
            "initial_pressure_pa": "P0",
        }
        for source_field, prj_field in required.items():
            if zone.get(source_field) is None:
                fields.append(prj_field)
        if fields:
            missing["section_14_zones"][zone["key"]] = fields

    # Section 15 needs mass fractions, while our current contract stores ppm.
    # Require an explicit conversion policy/species molecular weight before writing.
    for contaminant in manifest.get("contaminants") or []:
        fields: list[str] = []
        if contaminant.get("molecular_weight_g_mol") is None:
            fields.append("molecular_weight_g_mol")
        if contaminant.get("mass_fraction_conversion") is None:
            fields.append("mass_fraction_conversion")
        if fields:
            missing["section_15_initial_concentrations"][contaminant["key"]] = fields

    # Section 16 has several concrete file-format fields not represented by the
    # topology-level manifest yet.
    for path in manifest.get("flow_paths") or []:
        fields: list[str] = []
        required = {
            "prj_flags": "flags",
            "filter_number": "pf",
            "wind_profile_number": "pw",
            "ahs_number": "pa",
            "schedule_number": "ps",
            "level_number": "pld",
            "x_m": "X",
            "y_m": "Y",
            "relative_height_m": "relHt",
            "element_multiplier": "mult",
            "constant_wind_pressure_pa": "wPset",
            "wind_speed_modifier": "wPmod",
        }
        for source_field, prj_field in required.items():
            if path.get(source_field) is None:
                fields.append(prj_field)
        if path.get("wall_azimuth_deg") is None:
            fields.append("wazm")
        if fields:
            missing["section_16_airflow_paths"][path["key"]] = fields

    global_required = {
        "project_controls": "section_1_project_weather_simulation_controls",
        "species_definitions": "section_2_species_and_contaminants",
        "level_records": "section_3_level_and_icon_data",
    }
    for source_field, label in global_required.items():
        if manifest.get(source_field) is None:
            missing["global"].setdefault("manifest", []).append(label)

    clean_missing = {
        section: entities
        for section, entities in missing.items()
        if entities
    }
    ready = not clean_missing
    payload = {
        "topology_id": manifest.get("topology_id"),
        "layout_contract_sha256": manifest.get("layout_contract_sha256"),
        "mapping_sha256": manifest.get("mapping_sha256"),
        "airflow_binding_sha256": manifest.get("airflow_binding_sha256"),
        "boundary_binding_sha256": manifest.get("boundary_binding_sha256"),
        "missing": clean_missing,
    }

    return {
        "schema_version": "0.1",
        "compiler": "contam-prj-readiness",
        "status": "READY_FOR_PRJ_SERIALIZATION" if ready else "BLOCKED",
        "prj_serialization_ready": ready,
        "readiness_sha256": _sha256(payload),
        **payload,
        "evidence_boundary": (
            "readiness audit only; no .prj is emitted unless every required "
            "concrete field is explicit"
        ),
    }
