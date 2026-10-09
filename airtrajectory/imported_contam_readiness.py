"""Distinguish topology portability from genuine CONTAM compile readiness.

This verifies symbolic IR compilation, not PRJ generation or a solved airflow.
"""
from __future__ import annotations

from typing import Any
from .layout import LayoutContract
from .topology_acceptance import verify_topology_runtime
from .contam_ir import compile_contam_ir


def verify_imported_contam_readiness(layout: LayoutContract) -> dict[str, Any]:
    if layout.source_kind != "imported-floorplan":
        raise ValueError("imported CONTAM acceptance requires imported-floorplan")
    topology = verify_topology_runtime(layout)
    receipt: dict[str, Any] = {
        "schema_version": "0.1",
        "topology_id": layout.topology_id,
        "layout_contract_sha256": layout.sha256(),
        "topology_status": topology["status"],
        "topology_checks": topology["checks"],
        "contam_ir_status": "BLOCKED",
        "contam_ir_sha256": None,
        "status": "BLOCKED",
        "blockers": [],
        "evidence_level": "COMPILE_READINESS_ONLY_NOT_SOLVED",
    }
    if topology["status"] != "PASS":
        receipt["blockers"].append("topology runtime contract failed")
        return receipt
    try:
        ir = compile_contam_ir(layout)
    except (ValueError, KeyError, TypeError) as exc:
        receipt["blockers"].append(str(exc))
        return receipt
    receipt["contam_ir_status"] = "PASS"
    receipt["contam_ir_sha256"] = ir["contam_semantics_sha256"]
    receipt["status"] = "PASS"
    return receipt
