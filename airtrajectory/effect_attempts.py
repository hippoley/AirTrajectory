"""Logical-effect / transport-attempt trace semantics.

This module is transport-neutral. It does not perform retries. It validates
that multiple transport attempts can be represented without confusing them
with the single logical physical effect they belong to.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping


_ATTEMPT_STATUS = {"DISPATCHED", "ACKED", "TRANSPORT_ERROR", "UNRESOLVED"}


def build_effect_attempt_trace(
    *,
    logical_effect_id: str,
    request_id: str,
    attempts: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    logical_effect_id = str(logical_effect_id or "").strip()
    request_id = str(request_id or "").strip()
    if not logical_effect_id:
        raise ValueError("logical_effect_id must not be empty")
    if not request_id:
        raise ValueError("request_id must not be empty")

    normalized = []
    seen = set()
    for raw in attempts:
        attempt_id = str(raw.get("attempt_id") or "").strip()
        if not attempt_id:
            raise ValueError("attempt_id must not be empty")
        if attempt_id in seen:
            raise ValueError("duplicate attempt_id")
        seen.add(attempt_id)

        status = str(raw.get("status") or "").strip().upper()
        if status not in _ATTEMPT_STATUS:
            raise ValueError("invalid attempt status")

        row = {
            "attempt_id": attempt_id,
            "status": status,
            "transport_error": raw.get("transport_error"),
            "ack_id": raw.get("ack_id"),
        }
        if status == "ACKED" and not str(row["ack_id"] or "").strip():
            raise ValueError("ACKED attempt requires ack_id")
        if status == "TRANSPORT_ERROR" and not str(row["transport_error"] or "").strip():
            raise ValueError("TRANSPORT_ERROR attempt requires transport_error")
        normalized.append(row)

    if not normalized:
        raise ValueError("attempt trace must not be empty")

    # Ordering is evidence. Do not sort attempts.
    return {
        "record_type": "effect-attempt-trace-v0.1",
        "logical_effect_id": logical_effect_id,
        "request_id": request_id,
        "attempts": normalized,
        "effect_outcome": "UNRESOLVED",
        "evidence_boundary": (
            "transport attempts do not by themselves prove the physical effect outcome"
        ),
    }


def validate_effect_attempt_trace(trace: Mapping[str, Any]) -> None:
    if trace.get("record_type") != "effect-attempt-trace-v0.1":
        raise ValueError("unsupported effect attempt trace type")
    rebuilt = build_effect_attempt_trace(
        logical_effect_id=trace.get("logical_effect_id"),
        request_id=trace.get("request_id"),
        attempts=trace.get("attempts") or [],
    )
    if trace.get("effect_outcome") != "UNRESOLVED":
        raise ValueError(
            "transport attempt trace cannot assign a resolved physical effect outcome"
        )
    if trace.get("evidence_boundary") != rebuilt["evidence_boundary"]:
        raise ValueError("effect attempt trace evidence boundary mismatch")
