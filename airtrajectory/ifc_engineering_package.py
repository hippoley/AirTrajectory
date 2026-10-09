"""Source-bound engineering package adapter for imported IFC -> existing CONTAM compiler.

The package binds an independently audited full IFC source, candidate scope,
per-opening treatments, and the four evidence bundles already consumed by the
engineering CONTAM build. No missing engineering values are inferred.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from .layout import LayoutContract
from .contam_engineering_build import build_engineering_contam_project


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def validate_ifc_engineering_package(
    package: Mapping[str, Any], *, layout: LayoutContract,
    readiness: Mapping[str, Any], scope: Mapping[str, Any],
) -> dict[str, Any]:
    if package.get("schema_version") != "airtrajectory-ifc-engineering-package-v0.1":
        raise ValueError("unsupported IFC engineering package schema")
    if layout.source_kind != "imported-floorplan":
        raise ValueError("engineering package requires an imported IFC layout")
    source_sha = (readiness.get("source") or {}).get("sha256")
    if not isinstance(source_sha, str) or re.fullmatch(r"[0-9a-f]{64}", source_sha) is None:
        raise ValueError("invalid source IFC SHA")
    if package.get("source_ifc_sha256") != source_sha or scope.get("source_ifc_sha256") != source_sha:
        raise ValueError("engineering package IFC source hash mismatch")
    if readiness.get("control_scope", {}).get("mode") != "ALL_OPENINGS":
        raise ValueError("engineering review requires the full IFC opening inventory")
    if package.get("topology_id") != layout.topology_id:
        raise ValueError("engineering package topology mismatch")
    if package.get("layout_sha256") != layout.sha256():
        raise ValueError("engineering package layout hash mismatch")
    if package.get("scope_receipt_sha256") != scope.get("receipt_sha256"):
        raise ValueError("engineering package candidate scope receipt mismatch")
    if scope.get("prj_compilation_authorized") is not False:
        raise ValueError("candidate scope must not pre-authorize compilation")

    all_ids = {row["opening_id"] for row in scope.get("candidate_openings", [])}
    excluded = {row["opening_id"] for row in scope.get("excluded_openings", [])}
    if all_ids & excluded or len(all_ids) != scope.get("candidate_count") or len(excluded) != scope.get("excluded_count"):
        raise ValueError("candidate and excluded scope accounting mismatch")
    reviewed = package.get("opening_treatments")
    if not isinstance(reviewed, dict) or set(reviewed) != all_ids | excluded:
        raise ValueError("engineering opening treatments must cover every IFC opening")
    layout_ids = {row.id for row in layout.openings}
    if layout_ids != all_ids | excluded:
        raise ValueError("imported layout opening inventory does not match complete IFC scope")
    allowed = {"controllable", "fixed-flow", "closed-calibrated", "excluded-modeled"}
    for opening_id, treatment in reviewed.items():
        if not isinstance(treatment, dict) or treatment.get("disposition") not in allowed:
            raise ValueError(f"invalid opening disposition: {opening_id}")
        if opening_id in excluded and treatment["disposition"] == "controllable":
            raise ValueError(f"blocked upstream opening cannot become controllable: {opening_id}")
        if not isinstance(treatment.get("engineering_reference"), str) or not treatment["engineering_reference"].strip():
            raise ValueError(f"opening {opening_id} lacks review reference")
        if treatment.get("approved") is not True:
            raise ValueError(f"opening {opening_id} is not approved")
    approvals = package.get("approval")
    if not isinstance(approvals, dict) or approvals.get("approved") is not True or not approvals.get("reviewer") or not approvals.get("reviewer_role"):
        raise ValueError("engineering package requires attributable human review")
    if approvals.get("reviewed_source_sha256") != source_sha:
        raise ValueError("review approval is not bound to the original IFC source")
    required = ("metric_evidence", "airflow_evidence", "boundary_evidence",
                "prj_profile", "prj_review_evidence")
    for key in required:
        item = package.get(key)
        if not isinstance(item, dict):
            raise ValueError(f"missing engineering compiler input {key}")
        if item.get("source_ifc_sha256") != source_sha:
            raise ValueError(f"{key} source binding mismatch")
    # Evidence bundles remain strictly validated by the existing typed
    # profile compilers. A package approval does not bypass their gates.
    return {"status": "REVIEWED_FOR_COMPILER_VALIDATION", "source_ifc_sha256": source_sha,
            "package_sha256": _sha(dict(package)), "topology_id": layout.topology_id,
            "candidate_count": len(all_ids), "excluded_count": len(excluded)}


def compile_ifc_engineering_package(
    package: Mapping[str, Any], *, layout: LayoutContract,
    readiness: Mapping[str, Any], scope: Mapping[str, Any], out_path: str,
) -> dict[str, Any]:
    binding = validate_ifc_engineering_package(
        package, layout=layout, readiness=readiness, scope=scope,
    )
    # Existing compiler consumes the original validated input bundles.
    provenance = build_engineering_contam_project(
        layout=layout,
        metric_evidence=package["metric_evidence"],
        airflow_evidence=package["airflow_evidence"],
        boundary_evidence=package["boundary_evidence"],
        prj_profile=package["prj_profile"],
        prj_review_evidence=package["prj_review_evidence"],
        out_path=out_path,
    )
    return {**provenance, "ifc_engineering_package": binding,
            "runtime_verified": False, "engineering_truth": False}
