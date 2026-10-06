"""Compile engineering CONTAM profiles directly from typed evidence bundles."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .contam_calibration_evidence import issue_evidence_receipt
from .layout import LayoutContract


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _require_bundle(
    layout: LayoutContract,
    bundle: dict[str, Any],
    evidence_type: str,
) -> dict[str, Any]:
    receipt = issue_evidence_receipt(bundle)
    if receipt["evidence_type"] != evidence_type:
        raise ValueError(
            f"expected {evidence_type} evidence, got {receipt['evidence_type']}"
        )
    if receipt["topology_id"] != layout.topology_id:
        raise ValueError("evidence topology_id does not match layout")
    return receipt


def _source_from(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": receipt["evidence_id"],
        "captured_at": receipt["captured_at"],
        "method": receipt["method"],
        "source": receipt["source"],
    }


def compile_metric_overlay_from_evidence(
    layout: LayoutContract,
    bundle: dict[str, Any],
) -> dict[str, Any]:
    receipt = _require_bundle(
        layout,
        bundle,
        "metric_geometry_measurement",
    )
    data = bundle["data"]
    rooms = data.get("rooms")
    walls = data.get("walls")
    openings = data.get("openings")
    if not isinstance(rooms, dict):
        raise ValueError("engineering metric evidence requires room volumes")

    expected_rooms = {room.id for room in layout.rooms}
    expected_walls = {wall.id for wall in layout.walls}
    expected_openings = {opening.id for opening in layout.openings}

    if set(rooms) != expected_rooms:
        raise ValueError("metric evidence must exactly cover layout rooms")
    if set(walls) != expected_walls:
        raise ValueError("metric evidence must exactly cover layout walls")
    if set(openings) != expected_openings:
        raise ValueError("metric evidence must exactly cover layout openings")

    normalized_openings = {}
    for opening_id, row in openings.items():
        width = float(row["width_m"])
        height = float(row["height_m"])
        max_area = float(row.get("max_area_m2"))
        if max_area <= 0:
            raise ValueError(
                f"geometry opening {opening_id} max_area_m2 must be positive"
            )
        if max_area > width * height + 1e-9:
            raise ValueError(
                f"geometry opening {opening_id} max_area_m2 exceeds physical area"
            )
        normalized_openings[opening_id] = {
            "width_m": width,
            "height_m": height,
            "sill_height_m": float(row["sill_height_m"]),
            "max_area_m2": max_area,
        }

    return {
        "schema_version": "0.1",
        "profile_id": f"metric-from-{receipt['evidence_id']}",
        "topology_id": layout.topology_id,
        "evidence_level": "measured",
        "engineering_validated": bool((receipt.get("approval") or {}).get("approved")),
        "source": _source_from(receipt),
        "evidence_receipts": [receipt],
        "rooms": {
            room_id: {"volume_m3": float(row["volume_m3"])}
            for room_id, row in sorted(rooms.items())
        },
        "walls": {
            wall_id: {
                "length_m": float(row["length_m"]),
                "azimuth_deg": float(row["azimuth_deg"]),
            }
            for wall_id, row in sorted(walls.items())
        },
        "openings": normalized_openings,
    }


def compile_airflow_profile_from_evidence(
    layout: LayoutContract,
    bundle: dict[str, Any],
) -> dict[str, Any]:
    receipt = _require_bundle(layout, bundle, "airflow_calibration")
    fits = bundle["data"].get("opening_fits")
    expected = {opening.id for opening in layout.openings}
    if set(fits or {}) != expected:
        raise ValueError(
            "airflow calibration must exactly cover layout openings"
        )

    opening_kind = {opening.id: opening.kind for opening in layout.openings}
    by_kind: dict[str, list[tuple[str, tuple[float, float, float]]]] = {}
    for opening_id, fit in sorted(fits.items()):
        exponent = float(fit.get("flow_exponent"))
        coefficient = float(fit.get("discharge_coefficient"))
        leakage = float(fit.get("closed_leakage_multiplier"))
        if not 0.5 <= exponent <= 1.0:
            raise ValueError(
                f"airflow fit {opening_id} flow_exponent must be in [0.5,1.0]"
            )
        if not 0 < coefficient <= 1:
            raise ValueError(
                f"airflow fit {opening_id} discharge_coefficient must be in (0,1]"
            )
        kind = opening_kind[opening_id]
        by_kind.setdefault(kind, []).append(
            (opening_id, (exponent, coefficient, leakage))
        )

    rules = {}
    for kind, rows in sorted(by_kind.items()):
        first_id, first = rows[0]
        for opening_id, values in rows[1:]:
            if any(abs(a - b) > 1e-9 for a, b in zip(first, values)):
                raise ValueError(
                    f"airflow fits for kind {kind} disagree: "
                    f"{first_id} vs {opening_id}; per-opening rules are not yet supported"
                )
        exponent, coefficient, leakage = first
        rules[kind] = {
            "model": "powerlaw-orifice-area",
            "flow_exponent": exponent,
            "discharge_coefficient": coefficient,
            "closed_leakage_multiplier": leakage,
        }

    return {
        "schema_version": "0.1",
        "profile_id": f"airflow-from-{receipt['evidence_id']}",
        "evidence_level": "calibrated",
        "engineering_validated": bool((receipt.get("approval") or {}).get("approved")),
        "source": _source_from(receipt),
        "evidence_receipts": [receipt],
        "rules": rules,
    }


def compile_boundary_profile_from_evidence(
    layout: LayoutContract,
    bundle: dict[str, Any],
) -> dict[str, Any]:
    receipt = _require_bundle(layout, bundle, "boundary_measurement")
    data = bundle["data"]
    weather = data["weather"]
    required_weather = (
        "wind_speed_m_s",
        "wind_direction_deg",
        "outdoor_temperature_c",
        "barometric_pressure_pa",
        "wind_pressure_model",
    )
    missing_weather = [field for field in required_weather if field not in weather]
    if missing_weather:
        raise ValueError(
            "boundary weather missing fields: " + ",".join(missing_weather)
        )

    expected_zone_keys = {f"zone:{room.id}" for room in layout.rooms}
    contaminants = []
    for key, item in sorted((data.get("contaminants") or {}).items()):
        if not isinstance(item, dict):
            raise ValueError(
                "engineering boundary compiler requires structured contaminants"
            )
        initial = {
            str(zone): float(value)
            for zone, value in item["initial_zone_concentration"].items()
        }
        if set(initial) != expected_zone_keys:
            raise ValueError(
                f"boundary contaminant {key} must exactly cover layout zones"
            )
        contaminants.append(
            {
                "key": key,
                "name": str(item.get("name") or key.upper()),
                "unit": "ppm",
                "outdoor_concentration": float(
                    item["outdoor_concentration"]
                ),
                "initial_zone_concentration": initial,
            }
        )
    if not contaminants:
        raise ValueError("boundary evidence requires structured contaminants")

    return {
        "schema_version": "0.1",
        "profile_id": f"boundary-from-{receipt['evidence_id']}",
        "evidence_level": "measured",
        "engineering_validated": bool((receipt.get("approval") or {}).get("approved")),
        "source": _source_from(receipt),
        "evidence_receipts": [receipt],
        "weather": {
            "wind_speed_m_s": float(weather["wind_speed_m_s"]),
            "wind_direction_deg": float(weather["wind_direction_deg"]),
            "outdoor_temperature_c": float(weather["outdoor_temperature_c"]),
            "barometric_pressure_pa": float(
                weather["barometric_pressure_pa"]
            ),
            "wind_pressure_model": str(weather["wind_pressure_model"]),
        },
        "contaminants": contaminants,
    }


def attach_prj_review_evidence(
    *,
    topology_id: str,
    prj_profile: dict[str, Any],
    review_bundle: dict[str, Any],
) -> dict[str, Any]:
    receipt = issue_evidence_receipt(review_bundle)
    if receipt["evidence_type"] != "prj_engineering_review":
        raise ValueError("PRJ profile requires prj_engineering_review evidence")
    if receipt["topology_id"] != topology_id:
        raise ValueError("PRJ review topology_id does not match project")

    reviewed = dict(prj_profile)
    reviewed.pop("evidence_receipts", None)
    reviewed.pop("engineering_validated", None)
    reviewed.pop("evidence_level", None)
    reviewed_sha = _sha256(reviewed)
    approved_sha = str(
        review_bundle["data"]["approved_profile_sha256"]
    )
    if approved_sha != reviewed_sha:
        raise ValueError(
            "PRJ review approved_profile_sha256 does not match current profile"
        )

    return {
        **reviewed,
        "evidence_level": "engineering-reviewed",
        "engineering_validated": bool((receipt.get("approval") or {}).get("approved")),
        "evidence_receipts": [receipt],
    }
