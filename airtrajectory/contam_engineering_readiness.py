"""Engineering-evidence readiness audit for generated CONTAM projects.

This is intentionally separate from PRJ serialization readiness. A project can be
software-valid and executable in real ContamX while still relying on illustrative
geometry, airflow, boundary, or serialization inputs.

The audit never upgrades evidence. It only summarizes explicit profile metadata
already carried in provenance.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


_ACCEPTED_ENGINEERING_LEVELS = {
    "measured",
    "calibrated",
    "approved",
    "engineering-reviewed",
    "project-calibrated",
}


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _component(
    name: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    profile = dict(payload or {})
    blockers: list[str] = []
    if not profile:
        blockers.append("missing_profile_provenance")
    if profile.get("engineering_validated") is not True:
        blockers.append("engineering_validated_false")
    level = str(profile.get("evidence_level") or "")
    if level not in _ACCEPTED_ENGINEERING_LEVELS:
        blockers.append("evidence_level_not_engineering")
    if not str(profile.get("profile_sha256") or profile.get("metric_geometry_profile_sha256") or ""):
        blockers.append("missing_profile_sha256")

    return {
        "name": name,
        "ready": not blockers,
        "profile_id": (
            profile.get("profile_id")
            or profile.get("metric_geometry_profile_id")
        ),
        "profile_sha256": (
            profile.get("profile_sha256")
            or profile.get("metric_geometry_profile_sha256")
        ),
        "evidence_level": profile.get("evidence_level"),
        "engineering_validated": profile.get("engineering_validated") is True,
        "source": profile.get("source"),
        "blockers": blockers,
    }


def audit_engineering_readiness(
    provenance: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(provenance, dict):
        raise ValueError("CONTAM provenance must be an object")

    components = {
        "metric_geometry": _component(
            "metric_geometry",
            provenance.get("metric_geometry_provenance"),
        ),
        "airflow_calibration": _component(
            "airflow_calibration",
            provenance.get("airflow_profile"),
        ),
        "boundary_weather_co2": _component(
            "boundary_weather_co2",
            provenance.get("boundary_profile"),
        ),
        "prj_serialization": _component(
            "prj_serialization",
            provenance.get("prj_serialization_profile"),
        ),
    }

    airflow = provenance.get("airflow_profile") or {}
    leakage = dict(
        airflow.get("closed_leakage_multiplier_by_kind") or {}
    )
    if not leakage:
        components["airflow_calibration"]["ready"] = False
        components["airflow_calibration"]["blockers"].append(
            "missing_closed_leakage_calibration"
        )

    software_verified = bool(
        provenance.get("dynamic_control_verified")
        or provenance.get("status") == "GENERATED_TOPOLOGY_LOAD_SMOKE"
    )
    engineering_ready = all(item["ready"] for item in components.values())
    blockers = {
        key: list(item["blockers"])
        for key, item in components.items()
        if item["blockers"]
    }

    evidence_payload = {
        "topology_id": provenance.get("topology_id"),
        "layout_contract_sha256": provenance.get("layout_contract_sha256"),
        "demo_runtime_snapshot_sha256": provenance.get(
            "demo_runtime_snapshot_sha256"
        ),
        "components": components,
        "closed_leakage_multiplier_by_kind": leakage,
        "software_verified": software_verified,
        "engineering_ready": engineering_ready,
    }

    return {
        "schema_version": "0.1",
        "auditor": "contam-engineering-readiness",
        "status": (
            "ENGINEERING_READY"
            if engineering_ready
            else "SOFTWARE_VERIFIED_ONLY"
        ),
        "software_verified": software_verified,
        "engineering_ready": engineering_ready,
        "engineering_truth": engineering_ready,
        "components": components,
        "closed_leakage_multiplier_by_kind": leakage,
        "blockers": blockers,
        "evidence_sha256": _sha256(evidence_payload),
        "evidence_boundary": (
            "This audit does not validate measurements/calibration itself; "
            "it only requires explicit engineering-validated profile evidence."
        ),
    }
