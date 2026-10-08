"""PPEP v0.1 evidence construction and validation.

PPEP is intentionally small: one observable interaction, its experiment
assignment, its outcome claim, and a deterministic evidence hash.

A missing real-world proof is represented honestly as outcome.verified=False.
The validator never upgrades an unverified outcome.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Mapping

_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_OUTCOME_TYPES = {"digital_state_change", "choice", "real_world_action", "none"}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_value(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _unsigned_record(record: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(record))
    provenance = dict(payload.get("provenance") or {})
    provenance.pop("evidence_hash", None)
    payload["provenance"] = provenance
    return payload


def compute_evidence_hash(record: Mapping[str, Any]) -> str:
    return sha256_value(_unsigned_record(record))


def seal_evidence(record: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(record))
    provenance = dict(payload.get("provenance") or {})
    payload["provenance"] = provenance
    provenance["evidence_hash"] = compute_evidence_hash(payload)
    validate_evidence(payload)
    return payload


def _require_object(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be an object")
    return value


def _require_text(parent: Mapping[str, Any], key: str, path: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}.{key} must be a non-empty string")
    return value.strip()


def validate_evidence(record: Mapping[str, Any]) -> None:
    if not isinstance(record, Mapping):
        raise ValueError("PPEP evidence must be an object")
    if record.get("schema_version") != "0.1.0":
        raise ValueError("unsupported PPEP schema_version")
    _require_text(record, "probe_id", "record")

    experiment = _require_object(record, "experiment")
    for key in ("hypothesis", "variant", "assignment_id"):
        _require_text(experiment, key, "experiment")

    interaction = _require_object(record, "interaction")
    for key in ("actor_id", "action"):
        _require_text(interaction, key, "interaction")
    timestamp = _require_text(interaction, "timestamp", "interaction")
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("interaction.timestamp must be ISO-8601") from exc
    if not isinstance(interaction.get("prompted"), bool):
        raise ValueError("interaction.prompted must be boolean")
    for key in ("previous_state_hash", "result_state_hash"):
        value = _require_text(interaction, key, "interaction")
        if not _HASH_RE.match(value):
            raise ValueError(f"interaction.{key} must be sha256:<64 hex>")

    outcome = _require_object(record, "outcome")
    outcome_type = _require_text(outcome, "type", "outcome")
    if outcome_type not in _OUTCOME_TYPES:
        raise ValueError("unsupported outcome.type")
    if not isinstance(outcome.get("verified"), bool):
        raise ValueError("outcome.verified must be boolean")
    refs = outcome.get("evidence_refs")
    if not isinstance(refs, list) or any(not isinstance(item, str) or not item for item in refs):
        raise ValueError("outcome.evidence_refs must be a list of non-empty strings")
    if len(refs) != len(set(refs)):
        raise ValueError("outcome.evidence_refs must be unique")
    if outcome["verified"] and not refs:
        raise ValueError("verified outcome requires at least one evidence_ref")

    provenance = _require_object(record, "provenance")
    _require_text(provenance, "source", "provenance")
    _require_text(provenance, "consent_scope", "provenance")
    evidence_hash = _require_text(provenance, "evidence_hash", "provenance")
    if not _HASH_RE.match(evidence_hash):
        raise ValueError("provenance.evidence_hash must be sha256:<64 hex>")
    expected = compute_evidence_hash(record)
    if evidence_hash != expected:
        raise ValueError("PPEP evidence hash mismatch")


def build_evidence(
    *,
    probe_id: str,
    hypothesis: str,
    variant: str,
    assignment_id: str,
    actor_id: str,
    action: str,
    timestamp: str,
    prompted: bool,
    previous_state: Any,
    result_state: Any,
    outcome_type: str,
    verified: bool,
    evidence_refs: list[str] | None = None,
    source: str = "interactive_probe",
    consent_scope: str = "experiment",
) -> dict[str, Any]:
    record = {
        "schema_version": "0.1.0",
        "probe_id": probe_id,
        "experiment": {
            "hypothesis": hypothesis,
            "variant": variant,
            "assignment_id": assignment_id,
        },
        "interaction": {
            "actor_id": actor_id,
            "action": action,
            "timestamp": timestamp,
            "prompted": prompted,
            "previous_state_hash": sha256_value(previous_state),
            "result_state_hash": sha256_value(result_state),
        },
        "outcome": {
            "type": outcome_type,
            "verified": verified,
            "evidence_refs": list(evidence_refs or []),
        },
        "provenance": {
            "source": source,
            "consent_scope": consent_scope,
            "evidence_hash": "sha256:" + "0" * 64,
        },
    }
    return seal_evidence(record)
