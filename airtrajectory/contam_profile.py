"""Explicit airflow-element engineering profiles for CONTAM writer manifests.

Production bindings must provide an explicit profile. A bundled illustrative
profile exists for demos/tests only and carries its non-engineering provenance.

The binding layer still does not serialize a CONTAM PRJ.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


_SUPPORTED_MODELS = {"powerlaw-orifice-area"}


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def illustrative_opening_profile() -> dict[str, Any]:
    """Return an explicitly non-engineering preset for demos/tests."""
    return {
        "schema_version": "0.1",
        "profile_id": "nist-inspired-opening-demo-v1",
        "evidence_level": "illustrative",
        "engineering_validated": False,
        "source": {
            "title": "CONTAM User Guide and Program Documentation Version 3.4",
            "publisher": "NIST",
            "note": (
                "Demo parameters are representative only; project-specific "
                "airflow elements require engineering calibration."
            ),
        },
        "rules": {
            "window": {
                "model": "powerlaw-orifice-area",
                "flow_exponent": 0.5,
                "discharge_coefficient": 0.6,
                "closed_leakage_multiplier": 0.01,
            },
            "door": {
                "model": "powerlaw-orifice-area",
                "flow_exponent": 0.5,
                "discharge_coefficient": 0.6,
                "closed_leakage_multiplier": 0.01,
            },
            "vent": {
                "model": "powerlaw-orifice-area",
                "flow_exponent": 0.65,
                "discharge_coefficient": 0.6,
                "closed_leakage_multiplier": 0.01,
            },
        },
    }


def validate_airflow_profile(
    profile: dict[str, Any],
    *,
    require_engineering_validated: bool = False,
) -> None:
    if not isinstance(profile, dict):
        raise ValueError("airflow profile must be an object")
    if profile.get("schema_version") != "0.1":
        raise ValueError("unsupported airflow profile schema_version")
    if not str(profile.get("profile_id") or ""):
        raise ValueError("airflow profile_id is required")
    if require_engineering_validated and profile.get("engineering_validated") is not True:
        raise ValueError("engineering-validated airflow profile is required")

    rules = profile.get("rules")
    if not isinstance(rules, dict) or not rules:
        raise ValueError("airflow profile rules are required")

    for kind, rule in rules.items():
        if not isinstance(rule, dict):
            raise ValueError(f"airflow rule {kind} must be an object")
        model = rule.get("model")
        if model not in _SUPPORTED_MODELS:
            raise ValueError(f"airflow rule {kind} has unsupported model")
        exponent = float(rule.get("flow_exponent"))
        coefficient = float(rule.get("discharge_coefficient"))
        closed_leakage = float(rule.get("closed_leakage_multiplier", 0.0))
        if not 0.5 <= exponent <= 1.0:
            raise ValueError(
                f"airflow rule {kind} flow_exponent must be in [0.5,1.0]"
            )
        if not 0.0 < coefficient <= 1.0:
            raise ValueError(
                f"airflow rule {kind} discharge_coefficient must be in (0,1]"
            )
        if not 0.0 <= closed_leakage < 1.0:
            raise ValueError(
                f"airflow rule {kind} closed_leakage_multiplier must be in [0,1)"
            )


def bind_airflow_elements(
    manifest: dict[str, Any],
    profile: dict[str, Any],
    *,
    require_engineering_validated: bool = False,
) -> dict[str, Any]:
    """Bind each flow path to an explicit airflow element profile."""

    if manifest.get("compiler") != "contam-writer-manifest":
        raise ValueError("payload is not a CONTAM writer manifest")
    if manifest.get("status") != "READY_FOR_PRJ_SERIALIZATION":
        raise ValueError("writer manifest is not ready for airflow binding")

    validate_airflow_profile(
        profile,
        require_engineering_validated=require_engineering_validated,
    )

    rules = profile["rules"]
    elements: list[dict[str, Any]] = []
    paths: list[dict[str, Any]] = []
    for path in manifest.get("flow_paths") or []:
        kind = str(path["kind"])
        rule = rules.get(kind)
        if rule is None:
            raise ValueError(
                f"airflow profile has no rule for opening kind {kind}"
            )

        width = float(path["width_m"])
        height = float(path["height_m"])
        physical_area = width * height
        flow_area = float(path["max_area_m2"])
        if flow_area > physical_area + 1e-9:
            raise ValueError(
                f"path {path['key']} flow area exceeds physical opening area"
            )

        element_key = "element:" + str(path["layout_opening_id"])
        element = {
            "key": element_key,
            "layout_opening_id": path["layout_opening_id"],
            "model": rule["model"],
            "flow_area_m2": flow_area,
            "physical_area_m2": physical_area,
            "flow_exponent": float(rule["flow_exponent"]),
            "discharge_coefficient": float(rule["discharge_coefficient"]),
            "closed_leakage_multiplier": float(
                rule.get("closed_leakage_multiplier", 0.0)
            ),
            "hydraulic_diameter_m": rule.get("hydraulic_diameter_m"),
            "contam_element_number": None,
        }
        elements.append(element)
        paths.append(
            {
                **path,
                "airflow_element": {
                    "key": element_key,
                    "model": rule["model"],
                    "closed_leakage_multiplier": float(
                        rule.get("closed_leakage_multiplier", 0.0)
                    ),
                    "contam_element_number": None,
                },
            }
        )

    element_keys = [item["key"] for item in elements]
    if len(element_keys) != len(set(element_keys)):
        raise ValueError("duplicate airflow element keys")
    element_numbers = {
        key: index
        for index, key in enumerate(sorted(element_keys), start=1)
    }
    bound_elements = [
        {
            **item,
            "contam_element_number": element_numbers[item["key"]],
        }
        for item in elements
    ]
    bound_paths = [
        {
            **path,
            "airflow_element": {
                **path["airflow_element"],
                "contam_element_number": element_numbers[
                    path["airflow_element"]["key"]
                ],
            },
        }
        for path in paths
    ]

    canonical_elements = sorted(
        bound_elements,
        key=lambda item: item["key"],
    )
    binding_payload = {
        "profile_id": profile["profile_id"],
        "profile_sha256": _sha256(profile),
        "element_numbers": element_numbers,
        "airflow_elements": canonical_elements,
    }

    writer_contract = dict(manifest.get("writer_contract") or {})
    writer_contract["airflow_element_binding"] = "implemented"
    writer_contract["prj_serialization"] = "reserved"
    writer_contract["ready"] = False

    return {
        **manifest,
        "compiler": "contam-bound-manifest",
        "status": "READY_FOR_PRJ_SERIALIZATION",
        "airflow_profile": {
            "profile_id": profile["profile_id"],
            "profile_sha256": binding_payload["profile_sha256"],
            "evidence_level": profile.get("evidence_level"),
            "engineering_validated": profile.get("engineering_validated") is True,
            "source": profile.get("source"),
        },
        "element_numbers": element_numbers,
        "airflow_elements": bound_elements,
        "flow_paths": bound_paths,
        "airflow_binding_sha256": _sha256(binding_payload),
        "writer_contract": writer_contract,
    }
