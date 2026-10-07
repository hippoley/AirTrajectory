"""Consume a verified WindowPilot terminal receipt as a closed-loop origin."""
from __future__ import annotations

import hashlib
import json
import uuid
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



def _require_sha256(value: Any, label: str) -> str:
    text=str(value or "")
    if len(text)!=64 or any(ch not in "0123456789abcdef" for ch in text.lower()):
        raise RuntimeError(f"{label} must be a 64-character SHA-256")
    return text


def _normalized_unique_strings(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value,list):
        raise RuntimeError(f"{label} must be a list")
    normalized=[str(item) for item in value]
    if any(not item for item in normalized):
        raise RuntimeError(f"{label} contains an empty identifier")
    if len(set(normalized))!=len(normalized):
        raise RuntimeError(f"{label} contains duplicate identifiers")
    return sorted(normalized)


def _validate_physical_origin_semantics(
    *,
    source: str,
    receipt: Mapping[str, Any],
    origin: Mapping[str, Any],
) -> dict[str, Any]:
    zones=set(origin["co2_ppm"])
    openings=set(origin["opening_pct"])
    measured_zones=_normalized_unique_strings(
        receipt.get("measured_zones"),
        "physical origin measured_zones",
    )
    measured_openings=_normalized_unique_strings(
        receipt.get("measured_openings"),
        "physical origin measured_openings",
    )

    zone_id=str(receipt.get("zone_id") or "")
    opening_id=str(receipt.get("opening_id") or "")

    if source=="windowpilot-physical-reconcile-v1":
        if not zone_id or not opening_id:
            raise RuntimeError(
                "single physical origin requires zone_id and opening_id"
            )
        if measured_zones or measured_openings:
            raise RuntimeError(
                "single first-contact origin must not self-declare aggregate measured coverage"
            )
        measured_zones=[zone_id]
        measured_openings=[opening_id]
    elif source=="windowpilot-replanned-physical-step-v1":
        if not zone_id or not opening_id:
            raise RuntimeError(
                "replanned physical origin requires zone_id and opening_id"
            )
        if zone_id not in measured_zones or opening_id not in measured_openings:
            raise RuntimeError(
                "replanned physical origin measured coverage omits current field step"
            )
        _require_sha256(
            receipt.get("parent_physical_origin_sha256"),
            "parent physical origin state",
        )
        _require_sha256(
            receipt.get("parent_physical_origin_receipt_sha256"),
            "parent physical origin receipt",
        )
        _require_sha256(
            receipt.get("replanned_action_authorization_sha256"),
            "replanned action authorization",
        )
        _require_sha256(receipt.get("command_ack_sha256"),"physical command acknowledgement")
        _require_sha256(receipt.get("sensor_snapshot_sha256"),"physical sensor snapshot")
        try:
            uuid.UUID(str(receipt.get("command_request_id") or ""))
            uuid.UUID(str(receipt.get("command_id") or ""))
        except (ValueError,TypeError,AttributeError) as exc:
            raise RuntimeError(
                "replanned physical origin command request/command identity is invalid"
            ) from exc
        command_accepted_at=float(receipt.get("command_accepted_at") or 0)
        actuator_feedback_at=float(
            receipt.get("actuator_feedback_timestamp") or 0
        )
        if command_accepted_at<=0:
            raise RuntimeError(
                "replanned physical origin command accepted_at is invalid"
            )
        if actuator_feedback_at < command_accepted_at:
            raise RuntimeError(
                "replanned physical origin actuator feedback predates command acceptance"
            )
    elif source=="windowpilot-multi-physical-origin-v1":
        applied=receipt.get("applied_measurements")
        if not isinstance(applied,list) or not applied:
            raise RuntimeError(
                "multi physical origin requires applied_measurements"
            )
        declared_count=receipt.get("physical_measurement_count")
        if int(declared_count or 0)!=len(applied):
            raise RuntimeError(
                "multi physical origin measurement count does not match applied measurements"
            )
        applied_zones=[]
        applied_openings=[]
        for row in applied:
            if not isinstance(row,Mapping):
                raise RuntimeError("multi physical origin applied measurement is invalid")
            applied_zones.append(str(row.get("zone_id") or ""))
            applied_openings.append(str(row.get("opening_id") or ""))
            _require_sha256(
                row.get("physical_reconcile_sha256"),
                "multi physical child reconcile",
            )
            _require_sha256(
                row.get("physical_origin_receipt_sha256"),
                "multi physical child origin receipt",
            )
        if sorted(applied_zones)!=measured_zones:
            raise RuntimeError(
                "multi physical origin measured_zones do not match applied measurements"
            )
        if sorted(applied_openings)!=measured_openings:
            raise RuntimeError(
                "multi physical origin measured_openings do not match applied measurements"
            )

    unknown_zones=sorted(set(measured_zones)-zones)
    unknown_openings=sorted(set(measured_openings)-openings)
    if unknown_zones or unknown_openings:
        raise RuntimeError(
            "physical origin measured coverage references unknown topology state: "
            f"zones={unknown_zones}, openings={unknown_openings}"
        )

    inherited_zones=sorted(zones-set(measured_zones))
    inherited_openings=sorted(openings-set(measured_openings))
    declared_inherited_zones=receipt.get("inherited_zones")
    declared_inherited_openings=receipt.get("inherited_openings")
    if declared_inherited_zones is not None:
        if _normalized_unique_strings(
            declared_inherited_zones,
            "physical origin inherited_zones",
        )!=inherited_zones:
            raise RuntimeError(
                "physical origin inherited_zones do not complement measured coverage"
            )
    if declared_inherited_openings is not None:
        if _normalized_unique_strings(
            declared_inherited_openings,
            "physical origin inherited_openings",
        )!=inherited_openings:
            raise RuntimeError(
                "physical origin inherited_openings do not complement measured coverage"
            )

    expected_whole_home=not inherited_zones and not inherited_openings
    if "whole_home_physically_measured" in receipt:
        if bool(receipt.get("whole_home_physically_measured"))!=expected_whole_home:
            raise RuntimeError(
                "whole_home_physically_measured contradicts measured/inherited coverage"
            )

    return {
        "measured_zones":measured_zones,
        "measured_openings":measured_openings,
        "inherited_zones":inherited_zones,
        "inherited_openings":inherited_openings,
        "whole_home_physically_measured":expected_whole_home,
    }


def verify_physical_origin_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Verify and normalize a persisted physical-origin receipt.

    Accepts both single-device and multi-device origin receipts. The returned
    payload is safe to use as a ClosedLoopOrigin only after its receipt hash
    and origin hash have been re-derived successfully.
    """
    if not isinstance(receipt, Mapping):
        raise ValueError("physical origin receipt must be an object")

    source=str(receipt.get("source") or "")
    if source in {
        "windowpilot-physical-reconcile-v1",
        "windowpilot-replanned-physical-step-v1",
    }:
        receipt_hash_field="physical_origin_receipt_sha256"
    elif source=="windowpilot-multi-physical-origin-v1":
        receipt_hash_field="multi_physical_origin_receipt_sha256"
    else:
        raise RuntimeError(
            "unsupported physical origin receipt source: "+repr(source)
        )

    if str(receipt.get("schema_version") or "")!="0.1":
        raise RuntimeError("unsupported physical origin receipt schema_version")

    provided_receipt_hash=_require_sha256(
        receipt.get(receipt_hash_field),
        "physical origin receipt",
    )
    payload={
        key:value
        for key,value in receipt.items()
        if key not in {receipt_hash_field,"origin_sha256"}
    }
    if provided_receipt_hash!=_sha256(payload):
        raise RuntimeError("physical origin receipt SHA-256 mismatch")

    origin=receipt.get("origin")
    if not isinstance(origin,Mapping):
        raise RuntimeError("physical origin receipt missing origin object")
    normalized=ClosedLoopOrigin(
        co2_ppm=origin.get("co2_ppm") or {},
        opening_pct=origin.get("opening_pct") or {},
        scalar_values=origin.get("scalar_values") or {},
    ).normalized()
    provided_origin_hash=_require_sha256(
        receipt.get("origin_sha256"),
        "physical origin state",
    )
    if provided_origin_hash!=_sha256(normalized):
        raise RuntimeError("physical origin state SHA-256 mismatch")

    semantics=_validate_physical_origin_semantics(
        source=source,
        receipt=receipt,
        origin=normalized,
    )

    return {
        "source":source,
        "origin":normalized,
        "origin_sha256":provided_origin_hash,
        "receipt_sha256":provided_receipt_hash,
        "receipt_hash_field":receipt_hash_field,
        "whole_home_physically_measured":semantics[
            "whole_home_physically_measured"
        ],
        "measured_zones":semantics["measured_zones"],
        "measured_openings":semantics["measured_openings"],
        "inherited_zones":semantics["inherited_zones"],
        "inherited_openings":semantics["inherited_openings"],
        "evidence_boundary":str(receipt.get("evidence_boundary") or ""),
    }


def merge_physical_next_origins(
    *,
    current_origin: Mapping[str, Any] | ClosedLoopOrigin,
    measurements: list[Mapping[str, Any]],
    max_measurement_skew_s: float = 10.0,
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

    max_skew=float(max_measurement_skew_s)
    if max_skew < 0:
        raise ValueError("max_measurement_skew_s must be non-negative")

    current = base
    seen_zones: set[str] = set()
    seen_openings: set[str] = set()
    rain_value: float | None = None
    applied: list[dict[str, Any]] = []
    measurement_windows: list[dict[str, Any]] = []

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

        co2_ts=float(reconcile.get("terminal_co2_timestamp") or 0)
        rain_ts=float(reconcile.get("terminal_rain_timestamp") or 0)
        if co2_ts<=0 or rain_ts<=0:
            raise RuntimeError(
                "physical measurement lacks terminal sensor timestamps"
            )
        measurement_windows.append(
            {
                "zone_id":zone_id,
                "opening_id":opening_id,
                "start_timestamp":min(co2_ts,rain_ts),
                "end_timestamp":max(co2_ts,rain_ts),
            }
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

    earliest=min(row["start_timestamp"] for row in measurement_windows)
    latest=max(row["end_timestamp"] for row in measurement_windows)
    measurement_skew_s=latest-earliest
    if measurement_skew_s>max_skew:
        raise RuntimeError(
            "physical measurements exceed max temporal skew: "
            f"{measurement_skew_s:.3f}s > {max_skew:.3f}s"
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
        "measurement_windows": measurement_windows,
        "measurement_time_range": {
            "earliest_timestamp": earliest,
            "latest_timestamp": latest,
            "skew_s": measurement_skew_s,
            "max_allowed_skew_s": max_skew,
        },
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
