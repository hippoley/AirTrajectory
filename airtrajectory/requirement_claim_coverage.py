"""Coverage reconciliation for externally defined conformance requirements."""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def reconcile_requirement_claim_coverage(
    expected_cr_ids: Iterable[str],
    requirement_claims: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Check whether every expected CR-ID has an explicit claim outcome.

    This deliberately does not define Margo profile membership, STM structure,
    or outcome vocabulary. Those remain external conformance-framework
    decisions. It only verifies coverage of an externally supplied obligation.
    """
    expected = [str(value) for value in expected_cr_ids]
    if not expected:
        raise ValueError("expected CR-ID set must not be empty")
    if any(not value for value in expected):
        raise ValueError("expected CR-ID must not be empty")
    if len(expected) != len(set(expected)):
        raise ValueError("duplicate CR-ID in expected requirement set")

    reported = []
    for claim in requirement_claims:
        cr_id = str(claim.get("cr_id") or "")
        outcome = str(claim.get("outcome") or "")
        if not cr_id:
            raise ValueError("requirement claim lacks cr_id")
        if not outcome:
            raise ValueError(f"requirement claim lacks explicit outcome: {cr_id}")
        reported.append(cr_id)

    if len(reported) != len(set(reported)):
        raise ValueError("duplicate CR-ID in requirement claims")

    expected_set = set(expected)
    reported_set = set(reported)
    missing = sorted(expected_set - reported_set)
    unexpected = sorted(reported_set - expected_set)

    if missing:
        status = "MISSING"
    elif unexpected:
        status = "UNEXPECTED"
    else:
        status = "COMPLETE"

    return {
        "expected_requirement_count": len(expected),
        "reported_requirement_count": len(reported),
        "missing_cr_ids": missing,
        "unexpected_cr_ids": unexpected,
        "coverage_status": status,
    }
