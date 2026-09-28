"""Canonical safe-close evidence for physical tau0 capture."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import math


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


def _feedback_dict(feedback):
    if is_dataclass(feedback):
        return asdict(feedback)
    if isinstance(feedback,dict):
        return dict(feedback)
    raise RuntimeError("physical tau0 closeout feedback is missing/invalid")


def trajectory_last_feedback_timestamp(trajectory) -> float:
    latest=0.0
    for step in getattr(trajectory,"steps",[]) or []:
        for feedback in getattr(step,"actuator_feedback",[]) or []:
            ts=_number(
                getattr(feedback,"timestamp",None),
                "trajectory actuator feedback timestamp",
            )
            latest=max(latest,ts)
    return latest


def persisted_last_feedback_timestamp(steps) -> float:
    latest=0.0
    for step in steps or []:
        if not isinstance(step,dict):
            continue
        for feedback in step.get("actuator_feedback") or []:
            if not isinstance(feedback,dict):
                continue
            ts=_number(
                feedback.get("timestamp"),
                "persisted trajectory actuator feedback timestamp",
            )
            latest=max(latest,ts)
    return latest


def build_closeout_evidence(
    feedback,
    *,
    target_pct=0.0,
    tolerance_pct=1.0,
    after_timestamp=0.0,
) -> dict:
    payload={
        "target_pct":float(target_pct),
        "tolerance_pct":float(tolerance_pct),
        "feedback":_feedback_dict(feedback),
    }
    return validate_closeout_evidence(payload,after_timestamp=after_timestamp)


def validate_closeout_evidence(payload, *, after_timestamp=0.0) -> dict:
    if not isinstance(payload,dict):
        raise RuntimeError("physical tau0 receipt missing closeout evidence")

    target=_number(payload.get("target_pct"),"physical tau0 closeout target_pct")
    tolerance=_number(
        payload.get("tolerance_pct"),
        "physical tau0 closeout tolerance_pct",
    )
    if abs(target)>1e-9:
        raise RuntimeError("physical tau0 closeout target_pct must be 0")
    if not 0 < tolerance <= 1.0:
        raise RuntimeError(
            "physical tau0 closeout tolerance_pct must be >0 and <=1%"
        )

    feedback=_feedback_dict(payload.get("feedback"))
    measured=feedback.get("measured_position_pct")
    if measured is None:
        raise RuntimeError(
            "physical tau0 closeout requires measured actuator position"
        )
    measured=_number(measured,"physical tau0 closeout measured_position_pct")
    if measured<0 or measured>100:
        raise RuntimeError(
            "physical tau0 closeout measured position is outside [0,100]"
        )
    if measured>tolerance:
        raise RuntimeError(
            f"physical tau0 closeout did not return closed: "
            f"measured={measured:.3f}% > tolerance={tolerance:.3f}%"
        )

    timestamp=_number(
        feedback.get("timestamp"),
        "physical tau0 closeout feedback timestamp",
    )
    if timestamp<=0:
        raise RuntimeError("physical tau0 closeout feedback timestamp must be positive")
    previous=_number(after_timestamp,"physical tau0 prior actuator timestamp")
    if previous>0 and timestamp<=previous:
        raise RuntimeError(
            "physical tau0 closeout feedback is not newer than trajectory actuator feedback"
        )

    return {
        "target_pct":0.0,
        "tolerance_pct":tolerance,
        "feedback":{
            **feedback,
            "timestamp":timestamp,
            "measured_position_pct":measured,
        },
        "confirmed_closed":True,
    }
