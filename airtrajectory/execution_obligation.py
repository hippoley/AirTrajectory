"""Bind expected execution obligations to an explicit external source identity."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

from .execution_coverage import reconcile_execution_coverage


def build_execution_obligation_binding(
    *,
    source_kind: str,
    source_identity: str,
    source_revision: str,
    expected_execution_ids: Iterable[str],
) -> dict[str, Any]:
    """Build a deterministic binding for an externally defined execution obligation.

    The binding makes later tampering with the expected execution set detectable.
    It does not prove that the named source is authoritative; callers must establish
    that trust independently.
    """
    source_kind = str(source_kind or "").strip()
    source_identity = str(source_identity or "").strip()
    source_revision = str(source_revision or "").strip()
    if not source_kind:
        raise ValueError("source_kind must not be empty")
    if not source_identity:
        raise ValueError("source_identity must not be empty")
    if not source_revision:
        raise ValueError("source_revision must not be empty")

    expected = [str(value) for value in expected_execution_ids]
    if not expected:
        raise ValueError("expected execution set must not be empty")
    if any(not value for value in expected):
        raise ValueError("expected execution_id must not be empty")
    if len(expected) != len(set(expected)):
        raise ValueError("duplicate execution_id in expected execution set")

    payload = {
        "record_type": "execution-obligation-binding-v0.1",
        "source": {
            "kind": source_kind,
            "identity": source_identity,
            "revision": source_revision,
        },
        "expected_execution_ids": sorted(expected),
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    payload["binding_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def validate_execution_obligation_binding(binding: Mapping[str, Any]) -> None:
    """Validate shape and deterministic digest for an obligation binding."""
    if binding.get("record_type") != "execution-obligation-binding-v0.1":
        raise ValueError("unsupported execution obligation binding type")

    source = binding.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("binding source must be an object")

    expected = binding.get("expected_execution_ids")
    if not isinstance(expected, list) or not expected:
        raise ValueError("expected_execution_ids must be a non-empty list")
    if any(not isinstance(value, str) or not value for value in expected):
        raise ValueError("expected execution_id must not be empty")
    if expected != sorted(expected):
        raise ValueError("expected_execution_ids must be canonically sorted")
    if len(expected) != len(set(expected)):
        raise ValueError("duplicate execution_id in expected execution set")

    for field in ("kind", "identity", "revision"):
        if not str(source.get(field) or "").strip():
            raise ValueError(f"source.{field} must not be empty")

    unsigned = {
        "record_type": binding["record_type"],
        "source": {
            "kind": str(source["kind"]),
            "identity": str(source["identity"]),
            "revision": str(source["revision"]),
        },
        "expected_execution_ids": list(expected),
    }
    canonical = json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    expected_digest = hashlib.sha256(canonical).hexdigest()
    if binding.get("binding_sha256") != expected_digest:
        raise ValueError("execution obligation binding sha256 mismatch")


def reconcile_bound_execution_coverage(
    binding: Mapping[str, Any],
    evidence_records: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Reconcile observed evidence against a verified expected-obligation binding."""
    validate_execution_obligation_binding(binding)
    result = reconcile_execution_coverage(
        binding["expected_execution_ids"],
        evidence_records,
    )
    return {
        **result,
        "obligation_binding_sha256": binding["binding_sha256"],
        "obligation_source": dict(binding["source"]),
    }
