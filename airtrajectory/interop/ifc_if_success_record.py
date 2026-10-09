"""Render AirTrajectory IFC readiness as an IFC Implementers Forum-style success record.

This is an interoperability formatter. It does not claim certification or
buildingSMART endorsement.
"""
from __future__ import annotations

from typing import Any


def render_if_success_record(
    report: dict[str, Any],
    *,
    test_title: str,
    tool_name: str="AirTrajectory",
    tool_version: str="dev",
    source_model: str|None=None,
) -> str:
    status=str(report.get("status") or "UNKNOWN")
    coverage=report.get("opening_boundary_coverage") or {}
    scope=report.get("control_scope") or {}
    blockers=report.get("blockers") or []

    lines=[
        f"# {test_title} — {tool_name} {tool_version}",
        "",
        "## Result",
        "",
        f"- Readiness status: **{status}**",
        f"- Source model: {source_model or report.get('source',{}).get('path','unknown')}",
        f"- IFC schema: {report.get('source',{}).get('schema','unknown')}",
        f"- IfcSpace: {report.get('space_count',0)}",
        f"- IfcDoor: {report.get('door_count',0)}",
        f"- IfcWindow: {report.get('window_count',0)}",
        f"- IfcRelSpaceBoundary: {report.get('space_boundary_count',0)}",
        "",
        "## Verification checklist",
        "",
        f"- [{'x' if report.get('space_count',0)>0 else ' '}] At least one control-space candidate is present.",
        f"- [{'x' if coverage.get('doors_mapped',0)==coverage.get('doors_total',-1) else ' '}] Door-to-space boundary coverage is complete for the inspected model.",
        f"- [{'x' if coverage.get('windows_mapped',0)==coverage.get('windows_total',-1) else ' '}] Window-to-space boundary coverage is complete for the inspected model.",
        f"- [{'x' if not blockers else ' '}] No control-readiness blockers remain in the selected control scope.",
        "",
        "## Control scope",
        "",
        f"- Mode: {scope.get('mode','unknown')}",
        f"- Resolved controllable openings: {len(scope.get('resolved_opening_ids') or [])}",
        "",
        "## Blockers",
        "",
    ]
    if blockers:
        for blocker in blockers:
            detail=blocker.get("detail")
            suffix=f" — {detail}" if detail is not None else ""
            lines.append(
                f"- `{blocker.get('reason','UNKNOWN')}` @ "
                f"`{blocker.get('entity_id','<unknown>')}`{suffix}"
            )
    else:
        lines.append("- None.")

    lines += [
        "",
        "## Evidence boundary",
        "",
        "- This record is generated from AirTrajectory's control-readiness assessment.",
        "- It is not an IFC schema-validity certificate.",
        "- It is not buildingSMART software certification.",
        "- READY means the declared control scope passed AirTrajectory's current control-readiness checks; it does not by itself prove airflow-model or field-control validity.",
        "",
    ]
    return "\n".join(lines)
