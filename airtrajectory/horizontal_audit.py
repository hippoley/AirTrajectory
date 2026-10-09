"""Executable horizontal completeness gate for all canonical product stories.

This gate checks audit RECORD completeness, not actual operational closure.
It prevents unsupported VERIFIED_CLOSED claims and missing dimensions.
"""
from __future__ import annotations
from typing import Any

DIMENSIONS=(
    "function", "state", "integration", "security_correctness",
    "performance", "maintainability", "observability", "testability",
    "user_value", "external_compatibility",
)
DIMENSION_STATES={"VERIFIED","PARTIAL","MISSING","NOT_APPLICABLE","BLOCKED"}
STORY_STATES={"PARTIAL","PENDING_INTEGRATION","PENDING_VERIFICATION","BLOCKED","VERIFIED_CLOSED"}
DEPENDENCIES={
    1:(), 2:(1,), 3:(2,), 4:(3,), 5:(2,4,), 6:(3,5,),
    7:(3,4,6,), 8:(2,5,), 9:(6,8,), 10:(9,),
    11:(2,5,6,), 12:(6,11,), 13:(1,12,), 14:(10,12,), 15:(1,6,12,),
}


def validate_horizontal_matrix(matrix: dict[str, Any]) -> dict[str, Any]:
    """Reject false closure when any dependency/dimension/evidence gate is absent."""
    if not isinstance(matrix,dict):
        raise ValueError("matrix must be an object")
    keys={str(i) for i in DEPENDENCIES}
    if set(matrix)!=keys:
        raise ValueError("matrix must contain exactly stories 1 through 15")
    failures={}
    for story,requires in DEPENDENCIES.items():
        item=matrix[str(story)]
        if not isinstance(item,dict) or item.get("status") not in STORY_STATES:
            raise ValueError(f"story {story}: invalid status")
        dims=item.get("dimensions")
        if not isinstance(dims,dict) or set(dims)!=set(DIMENSIONS):
            raise ValueError(f"story {story}: missing or extra horizontal dimensions")
        for name,value in dims.items():
            if (not isinstance(value,dict) or value.get("status") not in DIMENSION_STATES
                    or not isinstance(value.get("evidence"),str)
                    or not value["evidence"].strip()):
                raise ValueError(f"story {story}: dimension {name} lacks status/evidence")
            if value["status"]=="NOT_APPLICABLE" and not value.get("rationale"):
                raise ValueError(f"story {story}: N/A {name} requires rationale")
        if item["status"]=="VERIFIED_CLOSED":
            defects=[]
            for dep in requires:
                if matrix[str(dep)]["status"]!="VERIFIED_CLOSED":
                    defects.append(f"dependency story {dep} not closed")
            for name,value in dims.items():
                if value["status"] not in {"VERIFIED","NOT_APPLICABLE"}:
                    defects.append(f"dimension {name} not verified")
            if not item.get("vertical_evidence") or not item.get("independent_evidence"):
                defects.append("vertical and independent evidence required")
            if defects: failures[str(story)]=defects
    return {
        "status":"PASS" if not failures else "FAIL",
        "story_count":len(matrix),
        "verified_closed":sum(v["status"]=="VERIFIED_CLOSED" for v in matrix.values()),
        "failures":failures,
        "dependencies":{str(k):list(v) for k,v in DEPENDENCIES.items()},
    }


def impacted_stories(changed: set[int]) -> list[int]:
    """Transitive downstream impact from changed canonical story IDs."""
    unknown=set(changed)-set(DEPENDENCIES)
    if unknown:
        raise ValueError(f"unknown story IDs: {sorted(unknown)}")
    affected=set(changed)
    while True:
        new={story for story,deps in DEPENDENCIES.items()
             if any(dep in affected for dep in deps)}
        if new<=affected:
            break
        affected|=new
    return sorted(affected)
