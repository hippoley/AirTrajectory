"""SpatialRuntime consumer bridge for AirTrajectory-generated CONTAM projects.

This module deliberately keeps SpatialRuntime optional for AirTrajectory core tests.
The integration boundary is activated explicitly by callers/CI that install
SpatialRuntime. No fallback silently substitutes for a missing dependency.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "airtrajectory_spatialruntime_contam_consumer_v1"


class SpatialRuntimeConsumerError(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def stable_mappings_from_provenance(
    provenance: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    zone_numbers = {
        key.split(":", 1)[1]: int(value)
        for key, value in (provenance.get("zone_numbers") or {}).items()
        if str(key).startswith("zone:")
    }
    path_numbers = {
        key.split(":", 1)[1]: int(value)
        for key, value in (provenance.get("path_numbers") or {}).items()
        if str(key).startswith("path:")
    }
    if not zone_numbers:
        raise SpatialRuntimeConsumerError("provenance has no stable zone_numbers")
    if not path_numbers:
        raise SpatialRuntimeConsumerError("provenance has no stable path_numbers")

    native_paths = {
        int(row["number"]): row
        for row in inventory.get("flow_paths", [])
    }
    zones = {
        stable_id: {"contam_zone_number": number}
        for stable_id, number in sorted(zone_numbers.items())
    }
    flow_paths: dict[str, dict[str, int]] = {}
    for stable_id, pnum in sorted(path_numbers.items()):
        row = native_paths.get(int(pnum))
        if row is None:
            raise SpatialRuntimeConsumerError(
                f"stable path {stable_id} references missing CONTAM path {pnum}"
            )
        enum = row.get("flow_element_number")
        if enum is None:
            raise SpatialRuntimeConsumerError(
                f"CONTAM path {pnum} has no flow_element_number"
            )
        flow_paths[stable_id] = {
            "contam_path_number": int(pnum),
            "contam_flow_element_number": int(enum),
        }
    return {"zones": zones, "flow_paths": flow_paths}


def verify_generated_prj_with_spatialruntime(
    *,
    project_path: str | Path,
    provenance: Mapping[str, Any],
    case_id: str,
) -> dict[str, Any]:
    try:
        from spatialruntime.solver.contam.binding import (
            assert_binding_fresh,
            build_binding_registry,
            registry_fingerprint,
            structural_digest,
        )
        from spatialruntime.solver.contam.inventory import (
            parse_prj_inventory,
            sha256_file,
        )
    except ImportError as exc:
        raise SpatialRuntimeConsumerError(
            "SpatialRuntime is not installed; install it explicitly before "
            "requesting SpatialRuntime verification"
        ) from exc

    project = Path(project_path)
    if not project.is_file():
        raise FileNotFoundError(project)

    inventory = parse_prj_inventory(project)
    mappings = stable_mappings_from_provenance(provenance, inventory)
    registry = build_binding_registry(
        case_id=case_id,
        project_path=project,
        inventory=inventory,
        mappings=mappings,
    )
    assert_binding_fresh(registry, project, inventory)

    project_sha = sha256_file(project)
    provenance_sha = provenance.get("sha256")
    if provenance_sha is not None and str(provenance_sha) != project_sha:
        raise SpatialRuntimeConsumerError(
            "AirTrajectory provenance PRJ sha256 does not match SpatialRuntime project hash"
        )

    payload = {
        "schema": SCHEMA,
        "verified": True,
        "case_id": case_id,
        "project_sha256": project_sha,
        "structural_inventory_sha256": structural_digest(inventory),
        "binding_registry_fingerprint": registry_fingerprint(registry),
        "binding_revision": int(registry.get("revision", 0)),
        "zone_ids": sorted(mappings["zones"]),
        "flow_path_ids": sorted(mappings["flow_paths"]),
        "zone_count": len(mappings["zones"]),
        "flow_path_count": len(mappings["flow_paths"]),
        "spatialruntime_binding_schema": registry.get("schema"),
    }
    return {**payload, "receipt_sha256": _sha256(payload)}
