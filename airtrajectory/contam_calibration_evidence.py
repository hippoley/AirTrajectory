"""Calibration/measurement evidence receipts for engineering CONTAM profiles.

Profiles may claim that they are engineering-validated, but that boolean alone is
not sufficient evidence. This module validates typed evidence bundles and emits a
small immutable receipt that can be carried in profile provenance.

The receipt intentionally stores hashes + summary metadata, not raw field data.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any


_EVIDENCE_TYPES = {
    "metric_geometry_measurement",
    "airflow_calibration",
    "boundary_measurement",
    "prj_engineering_review",
}


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _timestamp(value: Any) -> str:
    text = str(value or "")
    if not text:
        raise ValueError("captured_at is required")
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("captured_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("captured_at must include timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_source(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise ValueError("evidence source must be an object")
    kind = str(source.get("kind") or "")
    source_id = str(source.get("id") or "")
    if not kind or not source_id:
        raise ValueError("evidence source kind and id are required")
    return {
        "kind": kind,
        "id": source_id,
        "model": source.get("model"),
        "serial": source.get("serial"),
        "calibration_ref": source.get("calibration_ref"),
    }


def _validate_metric_geometry(data: dict[str, Any]) -> dict[str, Any]:
    rooms = data.get("rooms")
    walls = data.get("walls")
    openings = data.get("openings")
    if rooms is not None:
        if not isinstance(rooms, dict) or not rooms:
            raise ValueError("geometry evidence rooms must be a non-empty object")
        for room_id, row in rooms.items():
            if float(row.get("volume_m3")) <= 0:
                raise ValueError(
                    f"geometry room {room_id} volume_m3 must be positive"
                )
    if not isinstance(walls, dict) or not walls:
        raise ValueError("geometry evidence requires wall measurements")
    if not isinstance(openings, dict) or not openings:
        raise ValueError("geometry evidence requires opening measurements")
    for wall_id, row in walls.items():
        if float(row.get("length_m")) <= 0:
            raise ValueError(f"geometry wall {wall_id} length_m must be positive")
        azimuth = float(row.get("azimuth_deg"))
        if not 0 <= azimuth < 360:
            raise ValueError(f"geometry wall {wall_id} azimuth_deg must be in [0,360)")
    for opening_id, row in openings.items():
        for field in ("width_m", "height_m"):
            if float(row.get(field)) <= 0:
                raise ValueError(
                    f"geometry opening {opening_id} {field} must be positive"
                )
        if float(row.get("sill_height_m")) < 0:
            raise ValueError(
                f"geometry opening {opening_id} sill_height_m must be non-negative"
            )
    return {
        "room_count": len(rooms or {}),
        "wall_count": len(walls),
        "opening_count": len(openings),
        "data_sha256": _sha256(data),
    }


def _validate_airflow(data: dict[str, Any]) -> dict[str, Any]:
    fits = data.get("opening_fits")
    if not isinstance(fits, dict) or not fits:
        raise ValueError("airflow calibration evidence requires opening_fits")
    for opening_id, fit in fits.items():
        leakage = float(fit.get("closed_leakage_multiplier"))
        if not 0 <= leakage < 1:
            raise ValueError(
                f"airflow fit {opening_id} closed_leakage_multiplier must be in [0,1)"
            )
        samples = int(fit.get("sample_count"))
        if samples < 2:
            raise ValueError(
                f"airflow fit {opening_id} sample_count must be >=2"
            )
        rmse = float(fit.get("rmse"))
        if rmse < 0:
            raise ValueError(f"airflow fit {opening_id} rmse must be non-negative")
    return {
        "opening_fit_count": len(fits),
        "data_sha256": _sha256(data),
    }


def _validate_boundary(data: dict[str, Any]) -> dict[str, Any]:
    weather = data.get("weather")
    contaminants = data.get("contaminants")
    if not isinstance(weather, dict):
        raise ValueError("boundary evidence requires weather measurements")
    if not isinstance(contaminants, dict) or not contaminants:
        raise ValueError("boundary evidence requires contaminant measurements")
    if float(weather.get("wind_speed_m_s")) < 0:
        raise ValueError("boundary wind_speed_m_s must be non-negative")
    direction = float(weather.get("wind_direction_deg"))
    if not 0 <= direction < 360:
        raise ValueError("boundary wind_direction_deg must be in [0,360)")
    if not 30000 <= float(weather.get("barometric_pressure_pa")) <= 120000:
        raise ValueError("boundary barometric_pressure_pa is outside supported range")
    for key, value in contaminants.items():
        if isinstance(value, dict):
            if value.get("unit") != "ppm":
                raise ValueError(
                    f"boundary contaminant {key} currently requires unit=ppm"
                )
            if float(value.get("outdoor_concentration")) < 0:
                raise ValueError(
                    f"boundary contaminant {key} outdoor concentration must be non-negative"
                )
            initial = value.get("initial_zone_concentration")
            if not isinstance(initial, dict) or not initial:
                raise ValueError(
                    f"boundary contaminant {key} initial_zone_concentration is required"
                )
            for zone_key, zone_value in initial.items():
                if float(zone_value) < 0:
                    raise ValueError(
                        f"boundary contaminant {key} zone {zone_key} must be non-negative"
                    )
        elif float(value) < 0:
            raise ValueError(f"boundary contaminant {key} must be non-negative")
    return {
        "contaminant_count": len(contaminants),
        "data_sha256": _sha256(data),
    }


def _validate_prj_review(data: dict[str, Any]) -> dict[str, Any]:
    reviewer = str(data.get("reviewer") or "")
    role = str(data.get("reviewer_role") or "")
    approved_profile_sha256 = str(data.get("approved_profile_sha256") or "")
    if not reviewer or not role:
        raise ValueError("PRJ engineering review requires reviewer and reviewer_role")
    if len(approved_profile_sha256) != 64:
        raise ValueError("PRJ engineering review requires approved_profile_sha256")
    return {
        "reviewer": reviewer,
        "reviewer_role": role,
        "approved_profile_sha256": approved_profile_sha256,
        "data_sha256": _sha256(data),
    }


_VALIDATORS = {
    "metric_geometry_measurement": _validate_metric_geometry,
    "airflow_calibration": _validate_airflow,
    "boundary_measurement": _validate_boundary,
    "prj_engineering_review": _validate_prj_review,
}


def issue_evidence_receipt(bundle: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        raise ValueError("evidence bundle must be an object")
    if bundle.get("schema_version") != "0.1":
        raise ValueError("unsupported evidence schema_version")

    evidence_id = str(bundle.get("evidence_id") or "")
    evidence_type = str(bundle.get("evidence_type") or "")
    topology_id = str(bundle.get("topology_id") or "")
    method = str(bundle.get("method") or "")
    if not evidence_id:
        raise ValueError("evidence_id is required")
    if evidence_type not in _EVIDENCE_TYPES:
        raise ValueError("unsupported evidence_type")
    if not topology_id:
        raise ValueError("topology_id is required")
    if not method:
        raise ValueError("evidence method is required")

    source = _require_source(bundle.get("source"))
    captured_at = _timestamp(bundle.get("captured_at"))
    data = bundle.get("data")
    if not isinstance(data, dict):
        raise ValueError("evidence data must be an object")
    summary = _VALIDATORS[evidence_type](data)

    receipt_payload = {
        "schema_version": "0.1",
        "evidence_id": evidence_id,
        "evidence_type": evidence_type,
        "topology_id": topology_id,
        "captured_at": captured_at,
        "method": method,
        "source": source,
        "summary": summary,
    }
    return {
        **receipt_payload,
        "receipt_sha256": _sha256(receipt_payload),
    }


def validate_profile_evidence_receipts(
    receipts: Any,
    *,
    topology_id: str,
    required_type: str,
) -> list[dict[str, Any]]:
    if not isinstance(receipts, list) or not receipts:
        raise ValueError(f"{required_type} evidence receipt is required")
    normalized = []
    for receipt in receipts:
        if not isinstance(receipt, dict):
            raise ValueError("profile evidence receipt must be an object")
        if receipt.get("evidence_type") != required_type:
            continue
        if receipt.get("topology_id") != topology_id:
            raise ValueError(
                f"{required_type} evidence topology_id does not match profile"
            )
        if len(str(receipt.get("receipt_sha256") or "")) != 64:
            raise ValueError(f"{required_type} evidence receipt_sha256 is invalid")
        normalized.append(dict(receipt))
    if not normalized:
        raise ValueError(f"{required_type} evidence receipt is required")
    return normalized
