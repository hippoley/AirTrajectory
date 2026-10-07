"""Coverage reconciliation between an externally selected execution obligation and observed evidence."""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def reconcile_execution_coverage(
    expected_execution_ids: Iterable[str],
    evidence_records: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare an externally committed expected set with observed execution evidence.

    This function deliberately does not define how a conformance framework
    represents or signs its selected test plan. The caller supplies the expected
    execution IDs from that external source of truth.
    """
    expected = [str(value) for value in expected_execution_ids]
    if not expected:
        raise ValueError("expected execution set must not be empty")
    if any(not value for value in expected):
        raise ValueError("expected execution_id must not be empty")
    if len(expected) != len(set(expected)):
        raise ValueError("duplicate execution_id in expected execution set")

    observed = []
    for record in evidence_records:
        execution_id = str(record.get("execution_id") or "")
        if not execution_id:
            raise ValueError("execution evidence lacks execution_id")
        observed.append(execution_id)

    if len(observed) != len(set(observed)):
        raise ValueError("duplicate execution_id in observed evidence")

    expected_set = set(expected)
    observed_set = set(observed)
    missing = sorted(expected_set - observed_set)
    unexpected = sorted(observed_set - expected_set)

    if missing:
        status = "MISSING"
    elif unexpected:
        status = "UNEXPECTED"
    else:
        status = "COMPLETE"

    return {
        "expected_count": len(expected),
        "observed_count": len(observed),
        "missing_execution_ids": missing,
        "unexpected_execution_ids": unexpected,
        "coverage_status": status,
    }
