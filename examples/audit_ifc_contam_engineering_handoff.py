"""Prepare an evidence-only CONTAM engineering handoff for a public IFC.

Never silently derive airflow, leakage, exterior classification, or weather
from an IFC bounding box. This gate cannot authorize a PRJ without reviewed
engineering parameters and every excluded opening being accounted for.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from math import isfinite
from pathlib import Path


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def audit_duplex_engineering_inputs(readiness: dict, scope: dict, engineering: dict | None = None) -> dict:
    engineering = engineering or {}
    source_hash = (readiness.get("source") or {}).get("sha256")
    if not source_hash or source_hash != scope.get("source_ifc_sha256"):
        raise ValueError("IFC engineering handoff requires identical upstream source SHA")
    if readiness.get("control_scope", {}).get("mode") != "ALL_OPENINGS":
        raise ValueError("engineering handoff requires a full upstream opening inventory")
    spaces = (readiness.get("semantics") or {}).get("spaces")
    if not isinstance(spaces, list):
        raise ValueError("missing real IFC space inventory")
    issues = []
    space_ids = set()
    volumes = {}
    for space in spaces:
        sid = space.get("id")
        if not sid or sid in space_ids:
            raise ValueError("duplicate or empty source IFC space ID")
        space_ids.add(sid)
        volume = space.get("volume_m3")
        if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not isfinite(volume) or volume <= 0:
            issues.append({"entity_id": sid, "reason": "MISSING_MEASURED_SPACE_VOLUME"})
        else:
            volumes[sid] = {"volume_m3": volume, "source": space.get("volume_source")}
            if not space.get("volume_source"):
                issues.append({"entity_id": sid, "reason": "UNPROVEN_SPACE_VOLUME_SOURCE"})
    for opening in scope.get("candidate_openings", []):
        oid = opening["opening_id"]
        for sid in opening["adjacent_spaces"]:
            if sid not in space_ids:
                issues.append({"entity_id": oid, "reason": "ADJACENT_SPACE_NOT_IN_SOURCE_IFC", "space_id": sid})
        if len(opening["adjacent_spaces"]) == 1:
            issues.append({"entity_id": oid, "reason": "EXTERIOR_BOUNDARY_NOT_ENGINEERING_REVIEWED"})
        if len(opening["adjacent_spaces"]) == 2:
            issues.append({"entity_id": oid, "reason": "INTERIOR_FLOW_PATH_NOT_ENGINEERING_REVIEWED"})
    for opening in scope.get("excluded_openings", []):
        issues.append({"entity_id": opening["opening_id"], "reason": "EXCLUDED_OPENING_REQUIRES_AIRFLOW_TREATMENT"})
    required_inputs = (
        "opening_boundary_review", "airflow_element_calibration",
        "closed_leakage_calibration", "outdoor_weather_measurement",
        "initial_contaminant_conditions", "solver_serialization_review",
    )
    for key in required_inputs:
        evidence = engineering.get(key)
        if not isinstance(evidence, dict) or evidence.get("approved") is not True or evidence.get("source_ifc_sha256") != source_hash:
            issues.append({"entity_id": "ENGINEERING_EVIDENCE", "reason": "MISSING_APPROVED_" + key.upper()})
    # A scope marked unapproved cannot be silently promoted by providing
    # unrelated engineering metadata.
    if scope.get("prj_compilation_authorized") is not False:
        raise ValueError("unexpected pre-authorized candidate scope")
    result = {
        "schema_version": "airtrajectory-ifc-contam-engineering-gate-v0.1",
        "source_ifc_sha256": source_hash,
        "space_count": len(spaces),
        "verified_source_volumes": volumes,
        "candidate_count": scope["candidate_count"],
        "excluded_count": scope["excluded_count"],
        "issues": issues,
        "status": "BLOCKED" if issues else "READY_FOR_FORMAL_ENGINEERING_PROFILE_REVIEW",
        "prj_compilation_authorized": False,
        "contam_solver_executed": False,
        "evidence_boundary": "IFC geometry/space evidence inventory only; approvals must be verified through existing engineering profile compilers before PRJ execution",
    }
    return {**result, "receipt_sha256": _sha(result)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("readiness", type=Path)
    parser.add_argument("candidate_scope", type=Path)
    parser.add_argument("--engineering-evidence", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    def read(p): return json.loads(p.read_text(encoding="utf-8"))
    receipt = audit_duplex_engineering_inputs(read(args.readiness), read(args.candidate_scope),
        read(args.engineering_evidence) if args.engineering_evidence else None)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "issues": len(receipt["issues"]), "source": receipt["source_ifc_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
