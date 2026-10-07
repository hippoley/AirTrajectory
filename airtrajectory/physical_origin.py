"""Consume a verified WindowPilot terminal receipt as a closed-loop origin."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .joint_closed_loop import ClosedLoopOrigin


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _verify_reconcile_hash(reconcile: Mapping[str, Any]) -> None:
    provided = str(reconcile.get("physical_reconcile_sha256") or "")
    if len(provided) != 64:
        raise RuntimeError("physical reconcile receipt is missing SHA-256")
    payload = {
        key: value
        for key, value in reconcile.items()
        if key != "physical_reconcile_sha256"
    }
    calculated = _sha256(payload)
    if calculated != provided:
        raise RuntimeError("physical reconcile receipt SHA-256 mismatch")


def physical_next_origin_from_reconcile(
    *,
    current_origin: Mapping[str, Any] | ClosedLoopOrigin,
    reconcile: Mapping[str, Any],
    zone_id: str,
) -> dict[str, Any]:
    """Patch exactly one measured physical zone/opening into the next origin.

    The remaining zones/openings stay unchanged. This is intentionally a
    single-device bridge: it does not claim whole-home physical observation.
    """
    if isinstance(current_origin, ClosedLoopOrigin):
        current = current_origin.normalized()
    elif isinstance(current_origin, Mapping):
        current = ClosedLoopOrigin(
            co2_ppm=current_origin.get("co2_ppm") or {},
            opening_pct=current_origin.get("opening_pct") or {},
            scalar_values=current_origin.get("scalar_values") or {},
        ).normalized()
    else:
        raise ValueError("current_origin must be a ClosedLoopOrigin or mapping")

    if not isinstance(reconcile, Mapping):
        raise ValueError("reconcile must be an object")
    _verify_reconcile_hash(reconcile)

    if reconcile.get("physical_next_origin_ready") is not True:
        raise RuntimeError("physical reconcile is not ready for next-origin consumption")
    if reconcile.get("next_origin_position_verified") is not True:
        raise RuntimeError("physical next-origin position is not verified")
    if reconcile.get("next_origin_sensor_verified") is not True:
        raise RuntimeError("physical next-origin sensors are not verified")

    opening_id = str(reconcile.get("opening_id") or "")
    if opening_id not in current["opening_pct"]:
        raise RuntimeError(
            f"physical reconcile opening {opening_id!r} is not present in current origin"
        )
    zone = str(zone_id or "")
    if zone not in current["co2_ppm"]:
        raise RuntimeError(
            f"physical reconcile zone {zone!r} is not present in current origin"
        )

    predicted_zone = reconcile.get("predicted_zone_id")
    if predicted_zone is not None and str(predicted_zone) != zone:
        raise RuntimeError(
            "physical reconcile predicted_zone_id does not match requested zone"
        )

    terminal_position = reconcile.get("terminal_position_pct")
    terminal_co2 = reconcile.get("terminal_co2_ppm")
    terminal_rain = reconcile.get("terminal_rain")
    terminal_co2_ts = reconcile.get("terminal_co2_timestamp")
    terminal_rain_ts = reconcile.get("terminal_rain_timestamp")
    closeout_ts = reconcile.get("post_closeout_timestamp")

    if terminal_position is None or terminal_co2 is None:
        raise RuntimeError("physical reconcile lacks terminal position/CO2")
    if terminal_rain is None:
        raise RuntimeError("physical reconcile lacks terminal rain state")

    position = float(terminal_position)
    co2 = float(terminal_co2)
    co2_ts = float(terminal_co2_ts or 0)
    rain_ts = float(terminal_rain_ts or 0)
    close_ts = float(closeout_ts or 0)
    if not 0 <= position <= 100:
        raise RuntimeError("terminal physical position is outside [0,100]")
    if co2 < 0:
        raise RuntimeError("terminal physical CO2 must be non-negative")
    if close_ts <= 0 or co2_ts <= close_ts or rain_ts <= close_ts:
        raise RuntimeError("terminal physical sensors are not newer than closeout")

    co2_map = dict(current["co2_ppm"])
    opening_map = dict(current["opening_pct"])
    scalar_map = dict(current["scalar_values"])
    co2_map[zone] = co2
    opening_map[opening_id] = position
    scalar_map["rain"] = 1.0 if bool(terminal_rain) else 0.0

    origin = ClosedLoopOrigin(
        co2_ppm=co2_map,
        opening_pct=opening_map,
        scalar_values=scalar_map,
    ).normalized()
    payload = {
        "schema_version": "0.1",
        "source": "windowpilot-physical-reconcile-v1",
        "zone_id": zone,
        "opening_id": opening_id,
        "physical_reconcile_sha256": str(
            reconcile["physical_reconcile_sha256"]
        ),
        "terminal_snapshot_sha256": str(
            reconcile.get("terminal_snapshot_sha256") or ""
        ),
        "origin": origin,
        "evidence_boundary": (
            "single physical opening/zone updated from measured terminal state; "
            "all untouched zones/openings remain inherited from the prior origin"
        ),
    }
    return {
        **payload,
        "origin_sha256": _sha256(origin),
        "physical_origin_receipt_sha256": _sha256(payload),
    }


def merge_physical_next_origins(
    *,
    current_origin: Mapping[str, Any] | ClosedLoopOrigin,
    measurements: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Merge multiple independently verified physical zone/opening receipts.

    Each row must contain zone_id and reconcile. Duplicate physical coverage is
    rejected rather than resolved by order. Untouched state stays inherited
    from the supplied origin and is reported explicitly.
    """
    if not isinstance(measurements, list) or not measurements:
        raise ValueError("measurements must be a non-empty list")

    if isinstance(current_origin, ClosedLoopOrigin):
        base = current_origin.normalized()
    elif isinstance(current_origin, Mapping):
        base = ClosedLoopOrigin(
            co2_ppm=current_origin.get("co2_ppm") or {},
            opening_pct=current_origin.get("opening_pct") or {},
            scalar_values=current_origin.get("scalar_values") or {},
        ).normalized()
    else:
        raise ValueError("current_origin must be a ClosedLoopOrigin or mapping")

    current = base
    seen_zones: set[str] = set()
    seen_openings: set[str] = set()
    rain_value: float | None = None
    applied: list[dict[str, Any]] = []

    for index, row in enumerate(measurements):
        if not isinstance(row, Mapping):
            raise ValueError("each physical measurement must be an object")
        zone_id = str(row.get("zone_id") or "")
        reconcile = row.get("reconcile")
        if not zone_id:
            raise ValueError("physical measurement requires zone_id")
        if not isinstance(reconcile, Mapping):
            raise ValueError("physical measurement requires reconcile object")

        opening_id = str(reconcile.get("opening_id") or "")
        if zone_id in seen_zones:
            raise RuntimeError(f"duplicate physical coverage for zone {zone_id}")
        if opening_id in seen_openings:
            raise RuntimeError(
                f"duplicate physical coverage for opening {opening_id}"
            )

        receipt = physical_next_origin_from_reconcile(
            current_origin=current,
            reconcile=reconcile,
            zone_id=zone_id,
        )
        candidate = receipt["origin"]
        candidate_rain = candidate["scalar_values"].get("rain")
        if rain_value is None:
            rain_value = candidate_rain
        elif candidate_rain != rain_value:
            raise RuntimeError(
                "conflicting measured rain state across physical receipts"
            )

        current = candidate
        seen_zones.add(zone_id)
        seen_openings.add(opening_id)
        applied.append(
            {
                "index": index,
                "zone_id": zone_id,
                "opening_id": opening_id,
                "physical_reconcile_sha256": str(
                    reconcile["physical_reconcile_sha256"]
                ),
                "physical_origin_receipt_sha256": str(
                    receipt["physical_origin_receipt_sha256"]
                ),
            }
        )

    measured_zones = sorted(seen_zones)
    measured_openings = sorted(seen_openings)
    inherited_zones = sorted(set(base["co2_ppm"]) - seen_zones)
    inherited_openings = sorted(set(base["opening_pct"]) - seen_openings)

    payload = {
        "schema_version": "0.1",
        "source": "windowpilot-multi-physical-origin-v1",
        "origin": current,
        "base_origin_sha256": _sha256(base),
        "measured_zones": measured_zones,
        "measured_openings": measured_openings,
        "inherited_zones": inherited_zones,
        "inherited_openings": inherited_openings,
        "applied_measurements": applied,
        "physical_measurement_count": len(applied),
        "whole_home_physically_measured": (
            not inherited_zones and not inherited_openings
        ),
        "evidence_boundary": (
            "only measured_zones/measured_openings are refreshed from physical "
            "terminal receipts; inherited_zones/inherited_openings remain prior-origin state"
        ),
    }
    return {
        **payload,
        "origin_sha256": _sha256(current),
        "multi_physical_origin_receipt_sha256": _sha256(payload),
    }
