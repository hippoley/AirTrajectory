"""Deterministic numeric ID allocation for symbolic CONTAM IR.

The allocator does not serialize a PRJ. It freezes the mapping boundary between
stable symbolic identities (zone:living, path:W1, control:W1) and numeric IDs
that a future CONTAM writer will embed into a concrete project.

Rules:
- IDs are 1-based.
- Ordering is lexicographic by symbolic key, independent of source JSON order.
- Existing symbolic identity is the source of truth.
- Allocation emits a mapping SHA-256 for replay/audit.
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


def _allocate(keys: list[str]) -> dict[str, int]:
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate symbolic keys cannot be allocated")
    return {
        key: index
        for index, key in enumerate(sorted(keys), start=1)
    }


def allocate_contam_ids(ir: dict[str, Any]) -> dict[str, Any]:
    """Allocate deterministic numeric IDs for a CONTAM IR payload."""

    if not isinstance(ir, dict):
        raise ValueError("CONTAM IR must be an object")
    if ir.get("compiler") != "contam-ir":
        raise ValueError("payload is not CONTAM IR")
    if ir.get("status") != "READY_FOR_PRJ_WRITER":
        raise ValueError("CONTAM IR is not ready for PRJ writer allocation")

    zone_keys = [str(item["key"]) for item in ir.get("zones") or []]
    path_keys = [str(item["key"]) for item in ir.get("flow_paths") or []]
    control_keys = [str(item["key"]) for item in ir.get("controls") or []]

    zone_numbers = _allocate(zone_keys)
    path_numbers = _allocate(path_keys)
    control_numbers = _allocate(control_keys)

    mappings = {
        "zone_numbers": zone_numbers,
        "path_numbers": path_numbers,
        "control_numbers": control_numbers,
    }

    enriched_zones = [
        {
            **item,
            "contam_zone_number": zone_numbers[item["key"]],
        }
        for item in ir["zones"]
    ]
    enriched_paths = [
        {
            **item,
            "contam_path_number": path_numbers[item["key"]],
        }
        for item in ir["flow_paths"]
    ]
    enriched_controls = [
        {
            **item,
            "contam_control_number": control_numbers[item["key"]],
        }
        for item in ir["controls"]
    ]

    return {
        "schema_version": "0.1",
        "compiler": "contam-writer-manifest",
        "status": "READY_FOR_PRJ_SERIALIZATION",
        "topology_id": ir["topology_id"],
        "layout_contract_sha256": ir["layout_contract_sha256"],
        "spatial_connectivity_sha256": ir["spatial_connectivity_sha256"],
        "contam_semantics_sha256": ir["contam_semantics_sha256"],
        "mapping_sha256": _sha256(mappings),
        **mappings,
        "zones": enriched_zones,
        "flow_paths": enriched_paths,
        "controls": enriched_controls,
        "ambient_boundaries": list(ir.get("ambient_boundaries") or []),
        "walls": list(ir.get("walls") or []),
        "writer_contract": {
            "numeric_id_assignment": "implemented",
            "airflow_element_binding": "reserved",
            "prj_serialization": "reserved",
            "weather/wind_profile": "reserved",
            "contaminant_definition": "reserved",
            "ready": False,
        },
    }
