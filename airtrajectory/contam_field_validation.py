"""Prediction-vs-field validation for engineering CONTAM runtime receipts.

This is the final evidence gate after:
approved engineering inputs → generated PRJ → real CONTAM runtime verification.

Thresholds live only in an approved validation protocol. Measurement bundles
cannot carry thresholds and must cover every prediction step in the runtime
receipt, preventing post-hoc threshold selection or cherry-picked samples.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any

from .layout import LayoutContract


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _timestamp(value: Any, field: str) -> str:
    text = str(value or "")
    if not text:
        raise ValueError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _source(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("field measurement source must be an object")
    kind = str(value.get("kind") or "")
    source_id = str(value.get("id") or "")
    if not kind or not source_id:
        raise ValueError("field measurement source kind and id are required")
    model = str(value.get("model") or "")
    serial = str(value.get("serial") or "")
    calibration_ref = str(value.get("calibration_ref") or "")
    if not model or not serial or not calibration_ref:
        raise ValueError(
            "field measurement source requires model, serial, and calibration_ref"
        )
    return {
        "kind": kind,
        "id": source_id,
        "model": model,
        "serial": serial,
        "calibration_ref": calibration_ref,
    }


def validate_field_validation_protocol(
    layout: LayoutContract,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(protocol, dict):
        raise ValueError("field validation protocol must be an object")
    if protocol.get("schema_version") != "0.1":
        raise ValueError("unsupported field validation protocol schema_version")
    protocol_id = str(protocol.get("protocol_id") or "")
    if not protocol_id:
        raise ValueError("field validation protocol_id is required")
    if protocol.get("topology_id") != layout.topology_id:
        raise ValueError("field validation protocol topology_id does not match layout")

    approval = protocol.get("approval")
    if not isinstance(approval, dict) or approval.get("approved") is not True:
        raise ValueError("field validation protocol requires approved=true")
    approved_by = str(approval.get("approved_by") or "")
    approved_role = str(approval.get("approved_role") or "")
    if not approved_by or not approved_role:
        raise ValueError(
            "field validation protocol approval requires approved_by and approved_role"
        )
    approved_at = _timestamp(approval.get("approved_at"), "approved_at")

    expected_zones = sorted(room.id for room in layout.rooms)
    expected_openings = sorted(opening.id for opening in layout.openings)
    co2 = protocol.get("co2")
    opening = protocol.get("opening_position")
    if not isinstance(co2, dict) or not isinstance(opening, dict):
        raise ValueError(
            "field validation protocol requires co2 and opening_position sections"
        )
    zones = sorted(str(x) for x in (co2.get("zones") or []))
    openings = sorted(str(x) for x in (opening.get("openings") or []))
    if zones != expected_zones:
        raise ValueError("field validation protocol must cover all topology zones")
    if openings != expected_openings:
        raise ValueError(
            "field validation protocol must cover all topology openings"
        )

    min_samples = int(protocol.get("min_samples"))
    if min_samples < 2:
        raise ValueError("field validation protocol min_samples must be >=2")

    alignment = protocol.get("alignment")
    if not isinstance(alignment, dict):
        raise ValueError("field validation protocol requires alignment section")
    sampling_interval_s = float(alignment.get("sampling_interval_s"))
    max_skew_s = float(alignment.get("max_skew_s"))
    aggregation = str(alignment.get("aggregation") or "")
    accepted_qualities = sorted(
        {str(item) for item in (alignment.get("accepted_qualities") or [])}
    )
    if sampling_interval_s <= 0:
        raise ValueError("alignment sampling_interval_s must be positive")
    if max_skew_s < 0 or max_skew_s > sampling_interval_s:
        raise ValueError(
            "alignment max_skew_s must be in [0, sampling_interval_s]"
        )
    if aggregation != "nearest":
        raise ValueError("alignment aggregation currently must be nearest")
    if not accepted_qualities:
        raise ValueError("alignment accepted_qualities is required")
    co2_rmse = float(co2.get("rmse_ppm_max"))
    co2_mae = float(co2.get("mae_ppm_max"))
    opening_mae = float(opening.get("mae_pct_max"))
    if co2_rmse <= 0 or co2_mae <= 0 or opening_mae <= 0:
        raise ValueError("field validation thresholds must be positive")

    normalized = {
        "schema_version": "0.1",
        "protocol_id": protocol_id,
        "topology_id": layout.topology_id,
        "min_samples": min_samples,
        "co2": {
            "zones": expected_zones,
            "rmse_ppm_max": co2_rmse,
            "mae_ppm_max": co2_mae,
        },
        "opening_position": {
            "openings": expected_openings,
            "mae_pct_max": opening_mae,
        },
        "alignment": {
            "sampling_interval_s": sampling_interval_s,
            "max_skew_s": max_skew_s,
            "aggregation": aggregation,
            "accepted_qualities": accepted_qualities,
        },
        "approval": {
            "approved": True,
            "approved_by": approved_by,
            "approved_role": approved_role,
            "approved_at": approved_at,
            "note": approval.get("note"),
        },
    }
    return {
        **normalized,
        "protocol_sha256": _sha256(normalized),
    }


def _validate_measurements(
    *,
    layout: LayoutContract,
    runtime_receipt: dict[str, Any],
    protocol: dict[str, Any],
    field_bundle: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(field_bundle, dict):
        raise ValueError("field validation bundle must be an object")
    if field_bundle.get("schema_version") != "0.1":
        raise ValueError("unsupported field validation bundle schema_version")
    if "thresholds" in field_bundle:
        raise ValueError("field validation bundle must not carry thresholds")
    validation_id = str(field_bundle.get("validation_id") or "")
    if not validation_id:
        raise ValueError("field validation_id is required")
    if field_bundle.get("protocol_id") != protocol["protocol_id"]:
        raise ValueError("field bundle protocol_id mismatch")
    if field_bundle.get("protocol_sha256") != protocol["protocol_sha256"]:
        raise ValueError("field bundle protocol_sha256 mismatch")
    if field_bundle.get("topology_id") != layout.topology_id:
        raise ValueError("field bundle topology_id mismatch")
    if (
        field_bundle.get("runtime_receipt_sha256")
        != runtime_receipt.get("runtime_receipt_sha256")
    ):
        raise ValueError("field bundle runtime_receipt_sha256 mismatch")

    captured_at = _timestamp(field_bundle.get("captured_at"), "captured_at")
    if datetime.fromisoformat(captured_at.replace("Z", "+00:00")) < datetime.fromisoformat(
        protocol["approval"]["approved_at"].replace("Z", "+00:00")
    ):
        raise ValueError(
            "field measurements were captured before protocol approval"
        )
    source = _source(field_bundle.get("source"))
    samples = field_bundle.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("field validation samples are required")

    predictions = {
        int(row["step"]): row
        for row in runtime_receipt.get("prediction_series") or []
    }
    if len(predictions) != int(runtime_receipt.get("steps") or 0):
        raise ValueError("runtime receipt prediction_series is incomplete")

    expected_steps = sorted(predictions)
    measured_steps = []
    normalized_samples = []
    expected_zones = set(protocol["co2"]["zones"])
    expected_openings = set(protocol["opening_position"]["openings"])
    seen = set()
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("field validation sample must be an object")
        step = int(sample.get("step"))
        if step in seen:
            raise ValueError("field validation sample steps must be unique")
        seen.add(step)
        measured_steps.append(step)

        co2 = {
            str(key): float(value)
            for key, value in (sample.get("co2_ppm") or {}).items()
        }
        opening = {
            str(key): float(value)
            for key, value in (sample.get("opening_pct") or {}).items()
        }
        if set(co2) != expected_zones:
            raise ValueError(
                f"field sample {step} must cover all protocol CO2 zones"
            )
        if set(opening) != expected_openings:
            raise ValueError(
                f"field sample {step} must cover all protocol openings"
            )
        for opening_id, value in opening.items():
            if not 0 <= value <= 100:
                raise ValueError(
                    f"field sample {step} opening {opening_id} must be 0..100"
                )
        normalized_samples.append(
            {
                "step": step,
                "co2_ppm": dict(sorted(co2.items())),
                "opening_pct": dict(sorted(opening.items())),
            }
        )

    if sorted(measured_steps) != expected_steps:
        raise ValueError(
            "field measurements must cover every runtime prediction step"
        )
    if len(normalized_samples) < protocol["min_samples"]:
        raise ValueError("field validation sample count below protocol minimum")

    alignment_receipt = field_bundle.get("alignment_receipt")
    alignment_sha256 = None
    if alignment_receipt is not None:
        if not isinstance(alignment_receipt, dict):
            raise ValueError("alignment_receipt must be an object")
        alignment_payload = dict(alignment_receipt)
        alignment_sha256 = str(
            alignment_payload.pop("alignment_sha256", "") or ""
        )
        if alignment_sha256 != _sha256(alignment_payload):
            raise ValueError("alignment_receipt SHA-256 integrity check failed")

    raw_capture_sha256 = field_bundle.get("raw_capture_sha256")
    if raw_capture_sha256 is not None and len(str(raw_capture_sha256)) != 64:
        raise ValueError("raw_capture_sha256 is invalid")

    return {
        "validation_id": validation_id,
        "captured_at": captured_at,
        "source": source,
        "samples": sorted(normalized_samples, key=lambda row: row["step"]),
        "bundle_sha256": _sha256(field_bundle),
        "raw_capture_sha256": raw_capture_sha256,
        "alignment_sha256": alignment_sha256,
    }


def validate_contam_against_field(
    *,
    layout: LayoutContract,
    runtime_receipt: dict[str, Any],
    protocol: dict[str, Any],
    field_bundle: dict[str, Any],
) -> dict[str, Any]:
    if runtime_receipt.get("status") != "ENGINEERING_RUNTIME_VERIFIED":
        raise ValueError("runtime receipt is not ENGINEERING_RUNTIME_VERIFIED")
    provided_runtime_sha = str(
        runtime_receipt.get("runtime_receipt_sha256") or ""
    )
    runtime_payload = dict(runtime_receipt)
    runtime_payload.pop("runtime_receipt_sha256", None)
    if provided_runtime_sha != _sha256(runtime_payload):
        raise ValueError("runtime receipt SHA-256 integrity check failed")
    prediction_series = runtime_receipt.get("prediction_series") or []
    if (
        runtime_receipt.get("prediction_series_sha256")
        != _sha256(prediction_series)
    ):
        raise ValueError("runtime prediction_series SHA-256 integrity check failed")
    if runtime_receipt.get("runtime_verified") is not True:
        raise ValueError("runtime receipt is not verified")
    if runtime_receipt.get("engineering_model_verified") is not True:
        raise ValueError("engineering model runtime is not verified")
    if runtime_receipt.get("topology_id") != layout.topology_id:
        raise ValueError("runtime receipt topology_id does not match layout")
    if runtime_receipt.get("layout_contract_sha256") != layout.sha256():
        raise ValueError("runtime receipt layout SHA-256 drift")

    normalized_protocol = validate_field_validation_protocol(layout, protocol)
    measurements = _validate_measurements(
        layout=layout,
        runtime_receipt=runtime_receipt,
        protocol=normalized_protocol,
        field_bundle=field_bundle,
    )

    predictions = {
        int(row["step"]): row
        for row in runtime_receipt["prediction_series"]
    }
    co2_metrics = {}
    for zone in normalized_protocol["co2"]["zones"]:
        errors = []
        for sample in measurements["samples"]:
            step = sample["step"]
            predicted = float(predictions[step]["co2_ppm"][zone])
            measured = float(sample["co2_ppm"][zone])
            errors.append(predicted - measured)
        mae = sum(abs(value) for value in errors) / len(errors)
        rmse = math.sqrt(
            sum(value * value for value in errors) / len(errors)
        )
        co2_metrics[zone] = {
            "mae_ppm": mae,
            "rmse_ppm": rmse,
            "mae_pass": mae
            <= normalized_protocol["co2"]["mae_ppm_max"],
            "rmse_pass": rmse
            <= normalized_protocol["co2"]["rmse_ppm_max"],
        }

    opening_metrics = {}
    for opening_id in normalized_protocol["opening_position"]["openings"]:
        errors = []
        for sample in measurements["samples"]:
            step = sample["step"]
            predicted = float(
                predictions[step]["opening_pct"][opening_id]
            )
            measured = float(sample["opening_pct"][opening_id])
            errors.append(predicted - measured)
        mae = sum(abs(value) for value in errors) / len(errors)
        opening_metrics[opening_id] = {
            "mae_pct": mae,
            "mae_pass": mae
            <= normalized_protocol["opening_position"]["mae_pct_max"],
        }

    passed = all(
        row["mae_pass"] and row["rmse_pass"]
        for row in co2_metrics.values()
    ) and all(row["mae_pass"] for row in opening_metrics.values())

    payload = {
        "schema_version": "0.1",
        "validator": "contam-field-validation",
        "status": (
            "FIELD_VALIDATION_PASSED"
            if passed
            else "FIELD_VALIDATION_FAILED"
        ),
        "topology_id": layout.topology_id,
        "runtime_receipt_sha256": runtime_receipt[
            "runtime_receipt_sha256"
        ],
        "prediction_series_sha256": runtime_receipt[
            "prediction_series_sha256"
        ],
        "protocol_id": normalized_protocol["protocol_id"],
        "protocol_sha256": normalized_protocol["protocol_sha256"],
        "field_validation_id": measurements["validation_id"],
        "field_bundle_sha256": measurements["bundle_sha256"],
        "raw_capture_sha256": measurements["raw_capture_sha256"],
        "alignment_sha256": measurements["alignment_sha256"],
        "sample_count": len(measurements["samples"]),
        "co2_metrics": co2_metrics,
        "opening_position_metrics": opening_metrics,
        "engineering_inputs_ready": True,
        "runtime_verified": True,
        "engineering_model_verified": True,
        "field_validation_verified": passed,
        "engineering_truth": passed,
        "engineering_truth_scope": (
            "Validated only for the approved protocol, topology, measured "
            "signals, thresholds, and tested operating window."
        ),
        "evidence_boundary": (
            "Passing this gate demonstrates prediction-vs-field agreement "
            "within the approved protocol; it does not establish universal "
            "model validity outside the tested operating window."
        ),
    }
    return {
        **payload,
        "field_validation_receipt_sha256": _sha256(payload),
    }
