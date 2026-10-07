"""SpatialRuntime consumer bridge for AirTrajectory-generated CONTAM projects.

This module deliberately keeps SpatialRuntime optional for AirTrajectory core tests.
The integration boundary is activated explicitly by callers/CI that install
SpatialRuntime. No fallback silently substitutes for a missing dependency.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
import re
from pathlib import Path
import tempfile
from typing import Any, Mapping

from airtrajectory.contam_prj_reseed import reseed_initial_zone_mass_fractions


SCHEMA = "airtrajectory_spatialruntime_contam_consumer_v1"
RESULT_SCHEMA = "airtrajectory_spatialruntime_contam_result_consumer_v1"


class SpatialRuntimeConsumerError(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()




def _spatialruntime_commit_sha() -> str | None:
    value = os.environ.get("SPATIALRUNTIME_COMMIT_SHA")
    if value is None or not value.strip():
        return None
    value = value.strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise SpatialRuntimeConsumerError("SPATIALRUNTIME_COMMIT_SHA must be a 40-char git SHA")
    return value

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
        "spatialruntime_commit_sha": _spatialruntime_commit_sha(),
    }
    return {**payload, "receipt_sha256": _sha256(payload)}


def native_branch_result_from_stable(
    branch: Mapping[str, Any],
    provenance: Mapping[str, Any],
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
    zones = branch.get("end_co2_ppm_by_zone")
    paths = branch.get("path_flow_kg_s")
    if not isinstance(zones, Mapping) or set(zones) != set(zone_numbers):
        raise SpatialRuntimeConsumerError(
            "real CONTAM branch zone results do not exactly cover stable zone mappings"
        )
    if not isinstance(paths, Mapping) or set(paths) != set(path_numbers):
        raise SpatialRuntimeConsumerError(
            "real CONTAM branch path results do not exactly cover stable path mappings"
        )
    return {
        "source_format": "airtrajectory_real_contam_branch",
        "zones": [
            {
                "native_zone_number": int(zone_numbers[stable_id]),
                "co2_ppm": float(zones[stable_id]),
            }
            for stable_id in sorted(zone_numbers)
        ],
        "paths": [
            {
                "native_path_number": int(path_numbers[stable_id]),
                "mass_flow_kg_s": float(paths[stable_id]),
            }
            for stable_id in sorted(path_numbers)
        ],
        "execution": {
            "schema": "airtrajectory_real_contam_branch_execution_v1",
            "branch_label": str(branch.get("label") or ""),
            "evidence_level": branch.get("evidence_level"),
            "trusted_for_promotion": bool(branch.get("trusted_for_promotion", False)),
        },
    }


def reconstruct_reseeded_project_text(
    *,
    source_text: str,
    reseed_receipt: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    if not isinstance(reseed_receipt, Mapping):
        raise SpatialRuntimeConsumerError("CONTAM reseed receipt must be an object")
    if reseed_receipt.get("operation") != "contam-prj-section15-reseed-v1":
        raise SpatialRuntimeConsumerError("unsupported CONTAM reseed receipt operation")
    replacements = reseed_receipt.get("replacements")
    if not isinstance(replacements, Mapping) or not replacements:
        raise SpatialRuntimeConsumerError("CONTAM reseed receipt replacements missing")

    zone_mass_fractions = {}
    for zone, row in replacements.items():
        if not isinstance(row, Mapping) or "after_mass_fraction" not in row:
            raise SpatialRuntimeConsumerError(
                f"CONTAM reseed receipt missing after_mass_fraction for zone {zone}"
            )
        zone_mass_fractions[int(zone)] = float(row["after_mass_fraction"])

    rebuilt = reseed_initial_zone_mass_fractions(
        source_text,
        zone_mass_fractions,
    )
    rebuilt_receipt = rebuilt["receipt"]
    for key in ("source_prj_sha256", "reseeded_prj_sha256", "zone_count"):
        if rebuilt_receipt.get(key) != reseed_receipt.get(key):
            raise SpatialRuntimeConsumerError(
                f"CONTAM reseed receipt drift for {key}"
            )
    if rebuilt_receipt.get("replacements") != dict(replacements):
        raise SpatialRuntimeConsumerError(
            "CONTAM reseed receipt replacement lineage drifted"
        )
    return rebuilt["text"], rebuilt_receipt


def verify_branch_result_with_spatialruntime(
    *,
    project_path: str | Path,
    provenance: Mapping[str, Any],
    case_id: str,
    branch: Mapping[str, Any],
    source_step: int = 0,
    source_revision: int = 0,
    reseed_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        from spatialruntime.solver.contract import build_solver_request
        from spatialruntime.solver.contam.adapter import ContamProjectSolverAdapter
        from spatialruntime.solver.contam.binding import (
            build_binding_registry,
            registry_fingerprint,
        )
        from spatialruntime.solver.contam.inventory import (
            parse_prj_inventory,
            sha256_file,
        )
    except ImportError as exc:
        raise SpatialRuntimeConsumerError(
            "SpatialRuntime is not installed; install it explicitly before "
            "requesting SpatialRuntime result verification"
        ) from exc

    source_project = Path(project_path)
    if not source_project.is_file():
        raise FileNotFoundError(source_project)

    source_project_sha = sha256_file(source_project)
    provenance_sha = provenance.get("sha256")
    if provenance_sha is not None and str(provenance_sha) != source_project_sha:
        raise SpatialRuntimeConsumerError(
            "AirTrajectory provenance PRJ sha256 does not match source project hash"
        )

    temp_dir = None
    execution_project = source_project
    verified_reseed = None
    if reseed_receipt is not None:
        rebuilt_text, verified_reseed = reconstruct_reseeded_project_text(
            source_text=source_project.read_text(encoding="utf-8"),
            reseed_receipt=reseed_receipt,
        )
        temp_dir = tempfile.TemporaryDirectory()
        execution_project = Path(temp_dir.name) / source_project.name
        execution_project.write_text(
            rebuilt_text,
            encoding="utf-8",
            newline="\n",
        )

    try:
        inventory = parse_prj_inventory(execution_project)
        mappings = stable_mappings_from_provenance(provenance, inventory)
        registry = build_binding_registry(
            case_id=case_id,
            project_path=execution_project,
            inventory=inventory,
            mappings=mappings,
        )
        execution_project_sha = sha256_file(execution_project)
        if verified_reseed is not None and (
            execution_project_sha != verified_reseed.get("reseeded_prj_sha256")
        ):
            raise SpatialRuntimeConsumerError(
                "reconstructed execution PRJ hash does not match reseed receipt"
            )

        native = native_branch_result_from_stable(branch, provenance)

        def result_provider(request, project_path, binding_registry):
            return native

        adapter = ContamProjectSolverAdapter(
            project_path=execution_project,
            binding_registry=registry,
            result_provider=result_provider,
            strict_binding=True,
        )
        request = build_solver_request(
            case_id=case_id,
            source_step=int(source_step),
            source_revision=int(source_revision),
            world_state={
                "counterfactual_branch": str(branch.get("label") or ""),
                "execution_project_sha256": execution_project_sha,
            },
        )
        feedback = adapter.solve(request)

        expected_zones = {
            str(key): float(value)
            for key, value in (branch.get("end_co2_ppm_by_zone") or {}).items()
        }
        expected_paths = {
            str(key): float(value)
            for key, value in (branch.get("path_flow_kg_s") or {}).items()
        }
        actual_zones = {
            key: float(value["co2_ppm"])
            for key, value in feedback.get("zones", {}).items()
        }
        actual_paths = {
            key: float(value["mass_flow_kg_s"])
            for key, value in feedback.get("flow_paths", {}).items()
        }
        if set(actual_zones) != set(expected_zones):
            raise SpatialRuntimeConsumerError(
                "SpatialRuntime normalized zone IDs drifted"
            )
        if set(actual_paths) != set(expected_paths):
            raise SpatialRuntimeConsumerError(
                "SpatialRuntime normalized path IDs drifted"
            )

        zone_deltas = {
            key: abs(actual_zones[key] - expected_zones[key])
            for key in sorted(expected_zones)
        }
        path_deltas = {
            key: abs(actual_paths[key] - expected_paths[key])
            for key in sorted(expected_paths)
        }
        max_zone_delta = max(zone_deltas.values(), default=0.0)
        max_path_delta = max(path_deltas.values(), default=0.0)
        if max_zone_delta > 1e-9 or max_path_delta > 1e-12:
            raise SpatialRuntimeConsumerError(
                "SpatialRuntime normalized real CONTAM result changed AirTrajectory values"
            )

        solver_provenance = feedback.get("solver_provenance") or {}
        metadata = feedback.get("metadata") or {}
        unmapped = metadata.get("unmapped_native") or {}
        if (unmapped.get("zones") or []) or (unmapped.get("paths") or []):
            raise SpatialRuntimeConsumerError(
                f"SpatialRuntime left native CONTAM results unmapped: {unmapped}"
            )

        payload = {
            "schema": RESULT_SCHEMA,
            "verified": True,
            "case_id": case_id,
            "branch_label": str(branch.get("label") or ""),
            "source_project_sha256": source_project_sha,
            "execution_project_sha256": execution_project_sha,
            "reseeded_execution": verified_reseed is not None,
            "reseed_receipt_sha256": (
                _sha256(verified_reseed) if verified_reseed is not None else None
            ),
            "binding_registry_fingerprint": registry_fingerprint(registry),
            "adapter_id": solver_provenance.get("adapter_id"),
            "adapter_fingerprint": solver_provenance.get("adapter_fingerprint"),
            "request_hash": solver_provenance.get("request_hash"),
            "result_hash": solver_provenance.get("result_hash"),
            "feedback_sha256": _sha256(feedback),
            "zone_count": len(actual_zones),
            "flow_path_count": len(actual_paths),
            "max_abs_co2_ppm_delta": max_zone_delta,
            "max_abs_mass_flow_kg_s_delta": max_path_delta,
            "native_result_source": metadata.get("native_result_source"),
            "spatialruntime_commit_sha": _spatialruntime_commit_sha(),
        }
        # Keep the historical field as an alias for compatibility. It now points
        # at the PRJ that actually produced the branch, not always the source template.
        payload["project_sha256"] = execution_project_sha

        for key in (
            "source_project_sha256",
            "execution_project_sha256",
            "binding_registry_fingerprint",
            "adapter_fingerprint",
            "request_hash",
            "result_hash",
            "feedback_sha256",
        ):
            if not isinstance(payload.get(key), str) or len(payload[key]) != 64:
                raise SpatialRuntimeConsumerError(
                    f"SpatialRuntime result evidence missing SHA-256 field: {key}"
                )
        if verified_reseed is not None and (
            payload["execution_project_sha256"]
            != verified_reseed.get("reseeded_prj_sha256")
        ):
            raise SpatialRuntimeConsumerError(
                "SpatialRuntime result evidence is not bound to reseeded execution PRJ"
            )
        return {**payload, "receipt_sha256": _sha256(payload)}
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()

