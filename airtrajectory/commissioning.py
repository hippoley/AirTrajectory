"""Cross-repository validation for WindowPilot commissioning behavior evidence.

AirTrajectory does not trust a commissioning bundle merely because it says
status=PASS. It independently checks that the persisted phase measurements prove
a small reversible physical Reality Delta before any physical tau0 capture.

Expected WindowPilot bundle contract (schema >= 0.3):
READ -> OPEN_5 -> STOP -> CLOSE
with a commissioning.behavior_witness consistent with the phase rows.
"""
from __future__ import annotations

import hashlib
import json
import math


_PHASES=("READ","OPEN_5","STOP","CLOSE")


def _number(value,label):
    if isinstance(value,bool):
        raise RuntimeError(f"{label} must be numeric")
    try:
        number=float(value)
    except Exception as exc:
        raise RuntimeError(f"{label} is missing/invalid") from exc
    if not math.isfinite(number):
        raise RuntimeError(f"{label} is not finite")
    return number


def _integer(value,label):
    if isinstance(value,bool):
        raise RuntimeError(f"{label} must be an integer")
    try:
        number=int(value)
    except Exception as exc:
        raise RuntimeError(f"{label} is missing/invalid") from exc
    return number


def _schema_at_least_03(value):
    text=str(value or "").strip()
    parts=text.split(".")
    try:
        major=int(parts[0])
        minor=int(parts[1]) if len(parts)>1 else 0
    except Exception:
        return False
    return (major,minor)>=(0,3)


def _close(a,b,*,tol=1e-6):
    return abs(float(a)-float(b))<=tol


def _canonical_sha256(payload):
    raw=json.dumps(
        payload,
        sort_keys=True,
        separators=(",",":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def require_commissioning_behavior(bundle) -> dict:
    if not isinstance(bundle,dict):
        raise RuntimeError("commissioning bundle must be a JSON object")
    if bundle.get("status")!="PASS":
        raise RuntimeError("commissioning bundle status is not PASS")
    if not _schema_at_least_03(bundle.get("schema_version")):
        raise RuntimeError(
            "commissioning bundle schema must be >=0.3 with behavior witness"
        )

    commissioning=bundle.get("commissioning")
    if not isinstance(commissioning,dict):
        raise RuntimeError("commissioning bundle missing commissioning object")

    raw_policy=commissioning.get("acceptance_policy")
    if not isinstance(raw_policy,dict):
        raise RuntimeError("commissioning acceptance_policy is missing")

    max_excursion=_number(
        raw_policy.get("max_first_excursion_pct"),
        "acceptance_policy max_first_excursion_pct",
    )
    requested_excursion=_number(
        raw_policy.get("requested_excursion_pct"),
        "acceptance_policy requested_excursion_pct",
    )
    tolerance=_number(
        raw_policy.get("position_tolerance_pct"),
        "acceptance_policy position_tolerance_pct",
    )
    minimum_stop_samples=_integer(
        raw_policy.get("minimum_stop_hold_samples"),
        "acceptance_policy minimum_stop_hold_samples",
    )
    stop_hold_samples=_integer(
        raw_policy.get("stop_hold_samples"),
        "acceptance_policy stop_hold_samples",
    )
    max_polls=_integer(
        raw_policy.get("max_polls"),
        "acceptance_policy max_polls",
    )
    poll_interval=_number(
        raw_policy.get("poll_interval_s"),
        "acceptance_policy poll_interval_s",
    )

    if not _close(max_excursion,5.0):
        raise RuntimeError(
            "commissioning acceptance policy max_first_excursion_pct must be 5"
        )
    if not 0 < requested_excursion <= max_excursion:
        raise RuntimeError(
            "commissioning acceptance policy requested excursion must be >0 and <=5"
        )
    if not 0 < tolerance <= 1.0:
        raise RuntimeError(
            "commissioning acceptance policy position tolerance must be >0 and <=1%"
        )
    if minimum_stop_samples!=2:
        raise RuntimeError(
            "commissioning acceptance policy minimum_stop_hold_samples must be 2"
        )
    if stop_hold_samples < minimum_stop_samples:
        raise RuntimeError(
            "commissioning acceptance policy STOP hold samples must be >=2"
        )
    if max_polls < 1:
        raise RuntimeError(
            "commissioning acceptance policy max_polls must be >=1"
        )
    if poll_interval < 0:
        raise RuntimeError(
            "commissioning acceptance policy poll_interval_s must be >=0"
        )
    for key in (
        "source_timestamps_strictly_increasing",
        "requires_positive_open_delta",
        "requires_negative_close_delta",
    ):
        if raw_policy.get(key) is not True:
            raise RuntimeError(
                f"commissioning acceptance policy {key} must be true"
            )

    canonical_policy={
        "max_first_excursion_pct":5.0,
        "requested_excursion_pct":requested_excursion,
        "position_tolerance_pct":tolerance,
        "minimum_stop_hold_samples":2,
        "stop_hold_samples":stop_hold_samples,
        "max_polls":max_polls,
        "poll_interval_s":poll_interval,
        "source_timestamps_strictly_increasing":True,
        "requires_positive_open_delta":True,
        "requires_negative_close_delta":True,
    }
    if raw_policy!=canonical_policy:
        raise RuntimeError(
            "commissioning acceptance policy is not canonical or has been altered"
        )

    raw_phases=commissioning.get("phases")
    if not isinstance(raw_phases,list):
        raise RuntimeError("commissioning bundle missing phase rows")
    names=[
        row.get("phase") if isinstance(row,dict) else None
        for row in raw_phases
    ]
    if tuple(names)!=_PHASES:
        raise RuntimeError(
            "commissioning phases are not exactly READ -> OPEN_5 -> STOP -> CLOSE"
        )

    rows={}
    normalized_phases=[]
    for row in raw_phases:
        phase=row["phase"]
        measured=_number(row.get("measured_pct"),f"{phase} measured_pct")
        commanded=_number(row.get("commanded_pct"),f"{phase} commanded_pct")
        timestamp=_number(row.get("timestamp"),f"{phase} timestamp")
        delta=_number(row.get("observed_delta_pct"),f"{phase} observed_delta_pct")
        sample_count=_integer(row.get("sample_count"),f"{phase} sample_count")
        span=_number(row.get("position_span_pct"),f"{phase} position_span_pct")
        if timestamp<=0:
            raise RuntimeError(f"{phase} timestamp must be positive")
        if row.get("timestamp_advanced") is not True:
            raise RuntimeError(f"{phase} does not assert timestamp_advanced=true")
        normalized={
            "phase":phase,
            "commanded_pct":commanded,
            "measured_pct":measured,
            "timestamp":timestamp,
            "observed_delta_pct":delta,
            "sample_count":sample_count,
            "position_span_pct":span,
            "timestamp_advanced":True,
        }
        rows[phase]=normalized
        normalized_phases.append(normalized)

    read=rows["READ"]
    opened=rows["OPEN_5"]
    stopped=rows["STOP"]
    closed=rows["CLOSE"]

    timestamps=[row["timestamp"] for row in normalized_phases]
    if not all(b>a for a,b in zip(timestamps,timestamps[1:])):
        raise RuntimeError(
            "commissioning source timestamps are not strictly increasing"
        )

    if read["measured_pct"] > tolerance:
        raise RuntimeError(
            "commissioning READ does not prove an initially closed window within policy tolerance"
        )
    if abs(read["commanded_pct"]) > 1e-6:
        raise RuntimeError("commissioning READ commanded_pct must be 0")

    excursion=_number(
        commissioning.get("excursion_pct"),
        "commissioning excursion_pct",
    )
    if not _close(excursion,requested_excursion):
        raise RuntimeError(
            "commissioning excursion_pct does not match acceptance policy"
        )
    if not _close(opened["commanded_pct"],excursion):
        raise RuntimeError("OPEN_5 commanded_pct does not match excursion_pct")
    if abs(opened["measured_pct"]-excursion) > tolerance:
        raise RuntimeError(
            "OPEN_5 measured position is outside acceptance-policy target tolerance"
        )

    calculated_open=opened["measured_pct"]-read["measured_pct"]
    if calculated_open<=tolerance:
        raise RuntimeError(
            "commissioning OPEN does not prove sufficient positive displacement"
        )
    if not _close(opened["observed_delta_pct"],calculated_open):
        raise RuntimeError(
            "OPEN_5 observed_delta_pct does not match measured positions"
        )

    if stopped["sample_count"] != stop_hold_samples:
        raise RuntimeError(
            "commissioning STOP sample count does not match acceptance policy"
        )
    if (
        stopped["position_span_pct"] < 0
        or stopped["position_span_pct"] > tolerance
    ):
        raise RuntimeError(
            "commissioning STOP position span exceeds acceptance-policy hold tolerance"
        )
    if abs(stopped["measured_pct"]-opened["measured_pct"]) > tolerance:
        raise RuntimeError(
            "commissioning STOP position drift exceeds acceptance-policy tolerance"
        )
    calculated_stop=stopped["measured_pct"]-opened["measured_pct"]
    if not _close(stopped["observed_delta_pct"],calculated_stop):
        raise RuntimeError(
            "STOP observed_delta_pct does not match measured positions"
        )

    if abs(closed["commanded_pct"]) > 1e-6:
        raise RuntimeError("commissioning CLOSE commanded_pct must be 0")
    if closed["measured_pct"] > tolerance:
        raise RuntimeError(
            "commissioning CLOSE did not return to closed tolerance"
        )
    calculated_close=closed["measured_pct"]-stopped["measured_pct"]
    if calculated_close>=-tolerance:
        raise RuntimeError(
            "commissioning CLOSE does not prove sufficient negative displacement"
        )
    if not _close(closed["observed_delta_pct"],calculated_close):
        raise RuntimeError(
            "CLOSE observed_delta_pct does not match measured positions"
        )

    witness=commissioning.get("behavior_witness")
    if not isinstance(witness,dict):
        raise RuntimeError("commissioning behavior_witness is missing")
    if witness.get("initial_closed_observed") is not True:
        raise RuntimeError(
            "commissioning behavior_witness does not prove initial closed state"
        )
    if witness.get("timestamps_strictly_increasing") is not True:
        raise RuntimeError(
            "commissioning behavior_witness does not prove timestamp ordering"
        )
    if witness.get("reality_delta_observed") is not True:
        raise RuntimeError(
            "commissioning behavior_witness does not prove Reality Delta"
        )

    witness_open=_number(
        witness.get("open_observed_delta_pct"),
        "behavior_witness open_observed_delta_pct",
    )
    witness_stop_count=_integer(
        witness.get("stop_sample_count"),
        "behavior_witness stop_sample_count",
    )
    witness_stop_span=_number(
        witness.get("stop_position_span_pct"),
        "behavior_witness stop_position_span_pct",
    )
    witness_close=_number(
        witness.get("close_observed_delta_pct"),
        "behavior_witness close_observed_delta_pct",
    )
    witness_ts=witness.get("source_timestamps")
    if not isinstance(witness_ts,list) or len(witness_ts)!=4:
        raise RuntimeError(
            "commissioning behavior_witness source_timestamps must contain four values"
        )
    witness_ts=[_number(x,"behavior_witness source timestamp") for x in witness_ts]

    if not _close(witness_open,calculated_open):
        raise RuntimeError(
            "commissioning behavior_witness OPEN delta disagrees with phase rows"
        )
    if witness_stop_count!=stopped["sample_count"]:
        raise RuntimeError(
            "commissioning behavior_witness STOP sample count disagrees with phase row"
        )
    if not _close(witness_stop_span,stopped["position_span_pct"]):
        raise RuntimeError(
            "commissioning behavior_witness STOP span disagrees with phase row"
        )
    if not _close(witness_close,calculated_close):
        raise RuntimeError(
            "commissioning behavior_witness CLOSE delta disagrees with phase rows"
        )
    if any(not _close(a,b) for a,b in zip(witness_ts,timestamps)):
        raise RuntimeError(
            "commissioning behavior_witness timestamps disagree with phase rows"
        )

    normalized={
        "schema_version":str(bundle.get("schema_version")),
        "excursion_pct":excursion,
        "acceptance_policy":canonical_policy,
        "phases":normalized_phases,
        "behavior_witness":{
            "initial_closed_observed":True,
            "open_observed_delta_pct":calculated_open,
            "stop_sample_count":stopped["sample_count"],
            "stop_position_span_pct":stopped["position_span_pct"],
            "close_observed_delta_pct":calculated_close,
            "source_timestamps":timestamps,
            "timestamps_strictly_increasing":True,
            "reality_delta_observed":True,
        },
    }
    return {
        "normalized":normalized,
        "sha256":_canonical_sha256(normalized),
    }


def validate_commissioning_behavior_context(witness,sha256) -> None:
    if not isinstance(witness,dict):
        raise RuntimeError("trajectory missing commissioning behavior witness")
    calculated=_canonical_sha256(witness)
    if calculated!=str(sha256 or ""):
        raise RuntimeError(
            "trajectory commissioning behavior witness/hash mismatch"
        )
