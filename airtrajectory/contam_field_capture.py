"""Compile timestamped field events into validation samples.

The capture compiler aligns raw site events to the immutable runtime prediction
time axis using alignment rules frozen in the approved validation protocol.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from .contam_field_validation import validate_field_validation_protocol
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


def _parse_ts(value: Any, field: str) -> datetime:
    text = str(value or "")
    if not text:
        raise ValueError(f"{field} is required")
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if dt.tzinfo is None:
        raise ValueError(f"{field} must include timezone")
    return dt.astimezone(timezone.utc)


def _fmt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def compile_field_capture_bundle(
    *,
    layout: LayoutContract,
    runtime_receipt: dict[str, Any],
    protocol: dict[str, Any],
    capture: dict[str, Any],
) -> dict[str, Any]:
    normalized_protocol = validate_field_validation_protocol(layout, protocol)

    if runtime_receipt.get("status") != "ENGINEERING_RUNTIME_VERIFIED":
        raise ValueError("runtime receipt is not ENGINEERING_RUNTIME_VERIFIED")
    if runtime_receipt.get("topology_id") != layout.topology_id:
        raise ValueError("runtime receipt topology_id does not match layout")
    if capture.get("schema_version") != "0.1":
        raise ValueError("unsupported field capture schema_version")
    if capture.get("topology_id") != layout.topology_id:
        raise ValueError("field capture topology_id does not match layout")
    if capture.get("protocol_id") != normalized_protocol["protocol_id"]:
        raise ValueError("field capture protocol_id mismatch")
    if (
        capture.get("protocol_sha256")
        != normalized_protocol["protocol_sha256"]
    ):
        raise ValueError("field capture protocol_sha256 mismatch")
    if (
        capture.get("runtime_receipt_sha256")
        != runtime_receipt.get("runtime_receipt_sha256")
    ):
        raise ValueError("field capture runtime_receipt_sha256 mismatch")

    validation_id = str(capture.get("validation_id") or "")
    if not validation_id:
        raise ValueError("field capture validation_id is required")
    started_at = _parse_ts(capture.get("started_at"), "started_at")
    approved_at = _parse_ts(
        normalized_protocol["approval"]["approved_at"],
        "approved_at",
    )
    if started_at < approved_at:
        raise ValueError("field capture started before protocol approval")

    source = capture.get("source")
    if not isinstance(source, dict):
        raise ValueError("field capture source must be an object")
    for key in ("kind", "id", "model", "serial", "calibration_ref"):
        if not str(source.get(key) or ""):
            raise ValueError(
                "field capture source requires kind, id, model, serial, and calibration_ref"
            )

    records = capture.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("field capture records are required")

    accepted_qualities = set(
        normalized_protocol["alignment"]["accepted_qualities"]
    )
    allowed_units = {
        "co2_ppm": "ppm",
        "opening_pct": "percent",
    }
    normalized_records = []
    for index, row in enumerate(records):
        if not isinstance(row, dict):
            raise ValueError("field capture record must be an object")
        signal_type = str(row.get("signal_type") or "")
        if signal_type not in allowed_units:
            raise ValueError(
                f"field capture record {index} has unsupported signal_type"
            )
        unit = str(row.get("unit") or "")
        if unit != allowed_units[signal_type]:
            raise ValueError(
                f"field capture record {index} unit mismatch for {signal_type}"
            )
        quality = str(row.get("quality") or "")
        timestamp = _parse_ts(
            row.get("timestamp"),
            f"records[{index}].timestamp",
        )
        target_id = str(row.get("target_id") or "")
        if not target_id:
            raise ValueError(
                f"field capture record {index} target_id is required"
            )
        value = float(row.get("value"))
        if signal_type == "opening_pct" and not 0 <= value <= 100:
            raise ValueError(
                f"field capture record {index} opening_pct must be 0..100"
            )
        normalized_records.append(
            {
                "index": index,
                "timestamp": timestamp,
                "signal_type": signal_type,
                "target_id": target_id,
                "value": value,
                "unit": unit,
                "quality": quality,
            }
        )

    predictions = runtime_receipt.get("prediction_series") or []
    if not predictions:
        raise ValueError("runtime receipt prediction_series is required")
    if any("simulation_time_s" not in row for row in predictions):
        raise ValueError(
            "runtime prediction series lacks explicit simulation_time_s"
        )

    max_skew_s = float(
        normalized_protocol["alignment"]["max_skew_s"]
    )
    required = {
        "co2_ppm": list(normalized_protocol["co2"]["zones"]),
        "opening_pct": list(
            normalized_protocol["opening_position"]["openings"]
        ),
    }

    samples = []
    alignment_rows = []
    selected_indices = set()
    for prediction in predictions:
        step = int(prediction["step"])
        expected_at = started_at.timestamp() + float(
            prediction["simulation_time_s"]
        )
        sample = {
            "step": step,
            "co2_ppm": {},
            "opening_pct": {},
        }
        for signal_type, target_ids in required.items():
            for target_id in target_ids:
                candidates = []
                for row in normalized_records:
                    if row["index"] in selected_indices:
                        continue
                    if row["signal_type"] != signal_type:
                        continue
                    if row["target_id"] != target_id:
                        continue
                    if row["quality"] not in accepted_qualities:
                        continue
                    skew_s = row["timestamp"].timestamp() - expected_at
                    if abs(skew_s) <= max_skew_s:
                        candidates.append((abs(skew_s), skew_s, row))
                if not candidates:
                    raise ValueError(
                        f"no acceptable {signal_type} record for {target_id} at step {step}"
                    )
                candidates.sort(
                    key=lambda item: (
                        item[0],
                        item[2]["timestamp"],
                        item[2]["index"],
                    )
                )
                _, skew_s, chosen = candidates[0]
                selected_indices.add(chosen["index"])
                sample[signal_type][target_id] = chosen["value"]
                alignment_rows.append(
                    {
                        "step": step,
                        "simulation_time_s": float(
                            prediction["simulation_time_s"]
                        ),
                        "expected_timestamp": _fmt(
                            datetime.fromtimestamp(
                                expected_at,
                                tz=timezone.utc,
                            )
                        ),
                        "signal_type": signal_type,
                        "target_id": target_id,
                        "record_index": chosen["index"],
                        "record_timestamp": _fmt(chosen["timestamp"]),
                        "skew_s": float(skew_s),
                        "quality": chosen["quality"],
                    }
                )
        samples.append(sample)

    last_timestamp = max(
        row["timestamp"] for row in normalized_records
        if row["index"] in selected_indices
    )
    source_out = {
        key: source[key]
        for key in ("kind", "id", "model", "serial", "calibration_ref")
    }
    alignment_receipt = {
        "aggregation": "nearest",
        "max_skew_s": max_skew_s,
        "accepted_qualities": sorted(accepted_qualities),
        "selected_record_count": len(selected_indices),
        "input_record_count": len(normalized_records),
        "alignments": alignment_rows,
    }
    return {
        "schema_version": "0.1",
        "validation_id": validation_id,
        "protocol_id": normalized_protocol["protocol_id"],
        "protocol_sha256": normalized_protocol["protocol_sha256"],
        "topology_id": layout.topology_id,
        "runtime_receipt_sha256": runtime_receipt[
            "runtime_receipt_sha256"
        ],
        "captured_at": _fmt(last_timestamp),
        "source": source_out,
        "samples": samples,
        "capture_started_at": _fmt(started_at),
        "raw_capture_sha256": _sha256(capture),
        "alignment_receipt": {
            **alignment_receipt,
            "alignment_sha256": _sha256(alignment_receipt),
        },
    }
