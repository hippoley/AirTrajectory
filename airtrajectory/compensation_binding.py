"""Bind verified compensation to the original logical physical effect."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def _sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def build_compensation_binding(
    *,
    original_effect_id: str,
    compensation_effect_id: str,
    compensation_target_pct: float,
    closeout_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    original_effect_id = str(original_effect_id or "").strip()
    compensation_effect_id = str(compensation_effect_id or "").strip()
    if not original_effect_id:
        raise ValueError("original_effect_id must not be empty")
    if not compensation_effect_id:
        raise ValueError("compensation_effect_id must not be empty")
    if original_effect_id == compensation_effect_id:
        raise ValueError("compensation effect must have a distinct identity")

    if not isinstance(closeout_evidence, Mapping):
        raise ValueError("closeout_evidence must be an object")
    if closeout_evidence.get("confirmed_closed") is not True:
        raise ValueError("compensation requires verified closeout evidence")

    feedback = closeout_evidence.get("feedback")
    if not isinstance(feedback, Mapping):
        raise ValueError("compensation closeout feedback is missing")
    measured = feedback.get("measured_position_pct")
    timestamp = feedback.get("timestamp")
    if measured is None or timestamp is None:
        raise ValueError("compensation requires measured position and timestamp")

    target = float(compensation_target_pct)
    if not 0 <= target <= 100:
        raise ValueError("compensation_target_pct must be in [0,100]")

    payload = {
        "record_type": "compensation-effect-binding-v0.1",
        "original_effect_id": original_effect_id,
        "compensation_effect_id": compensation_effect_id,
        "relation": "COMPENSATES",
        "compensation_target_pct": target,
        "verified_observation": {
            "measured_position_pct": float(measured),
            "timestamp": float(timestamp),
            "source": str(feedback.get("source") or feedback.get("quality") or "measured-feedback"),
        },
        "original_effect_history_rewritten": False,
        "evidence_boundary": (
            "verified compensation establishes the compensation outcome; "
            "it does not erase or rewrite the original effect history"
        ),
    }
    return {**payload, "binding_sha256": _sha256(payload)}


def validate_compensation_binding(binding: Mapping[str, Any]) -> None:
    if binding.get("record_type") != "compensation-effect-binding-v0.1":
        raise ValueError("unsupported compensation binding type")
    if binding.get("relation") != "COMPENSATES":
        raise ValueError("invalid compensation relation")
    if binding.get("original_effect_history_rewritten") is not False:
        raise ValueError("compensation must not rewrite original effect history")

    unsigned = {
        key: value
        for key, value in binding.items()
        if key != "binding_sha256"
    }
    if binding.get("binding_sha256") != _sha256(unsigned):
        raise ValueError("compensation binding sha256 mismatch")

    if binding.get("original_effect_id") == binding.get("compensation_effect_id"):
        raise ValueError("compensation effect must have a distinct identity")
