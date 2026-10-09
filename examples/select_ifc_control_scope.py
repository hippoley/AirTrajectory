"""Audit a real IFC readiness receipt into a *candidate* engineering scope.

This is a scoped evidence decision, not physical readiness or permission to
delete omitted openings from the airflow model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def scope_candidate_receipt(readiness: dict[str, Any]) -> dict[str, Any]:
    if readiness.get("control_scope", {}).get("mode") != "ALL_OPENINGS":
        raise ValueError("candidate selection requires unfiltered ALL_OPENINGS source audit")
    source = readiness.get("source") or {}
    sha = source.get("sha256")
    if not isinstance(sha, str) or len(sha) != 64:
        raise ValueError("missing source IFC SHA-256")
    openings = (readiness.get("semantics") or {}).get("openings")
    if not isinstance(openings, list):
        raise ValueError("missing IFC opening semantics")
    identifiers = [row.get("id") for row in openings]
    if any(not isinstance(k, str) or not k for k in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate or invalid IFC opening IDs")
    blockers = readiness.get("blockers")
    if not isinstance(blockers, list):
        raise ValueError("missing original readiness blockers")
    blocked_ids = {b.get("entity_id") for b in blockers}
    candidates = []
    excluded = []
    for row in sorted(openings, key=lambda x: x["id"]):
        adjacent = row.get("adjacent_spaces")
        reasons = []
        if row["id"] in blocked_ids:
            reasons.append("ORIGINAL_READINESS_BLOCKER")
        if not isinstance(adjacent, list) or len(adjacent) not in (1, 2):
            reasons.append("MISSING_OR_AMBIGUOUS_ADJACENCY")
        elif len(set(adjacent)) != len(adjacent):
            reasons.append("DUPLICATE_ADJACENT_SPACE")
        for dimension in ("width_m", "height_m"):
            value = row.get(dimension)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not 0 < value < float("inf")):
                reasons.append("INVALID_" + dimension.upper())
        if reasons:
            excluded.append({"opening_id": row["id"], "reasons": sorted(set(reasons)),
                             "adjacent_spaces": adjacent})
        else:
            candidates.append({"opening_id": row["id"], "kind": row["kind"],
                               "adjacent_spaces": adjacent,
                               "width_m": row["width_m"], "height_m": row["height_m"]})
    if len(candidates) + len(excluded) != readiness.get("opening_count"):
        raise ValueError("candidate accounting disagrees with IFC opening count")
    result = {
        "schema_version": "airtrajectory-ifc-candidate-scope-v0.1",
        "source_ifc_sha256": sha,
        "original_full_scope_status": readiness.get("status"),
        "full_scope_blocker_count": len(blockers),
        "candidate_openings": candidates,
        "excluded_openings": excluded,
        "candidate_count": len(candidates),
        "excluded_count": len(excluded),
        "engineering_status": "BLOCKED_PENDING_SPACE_GEOMETRY_AND_AIRFLOW_REVIEW",
        "prj_compilation_authorized": False,
        "evidence_boundary": "source-evidenced adjacency/dimensions only; no reviewed volumes, boundary physics or solved CONTAM model",
    }
    return {**result, "receipt_sha256": _digest(result)}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("readiness", type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    receipt = scope_candidate_receipt(json.loads(args.readiness.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_count": receipt["candidate_count"],
                      "excluded_count": receipt["excluded_count"],
                      "engineering_status": receipt["engineering_status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
