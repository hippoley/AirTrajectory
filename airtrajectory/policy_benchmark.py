"""Model-agnostic policy benchmark contract for AirTrajectory.

The benchmark compares policies from the same origin and horizon.  It is not a
reward function and does not require a specific learning algorithm or physics
backend.
"""
from __future__ import annotations

from typing import Any, Mapping
from math import isfinite

from .contam_joint_golden_case import independent_action_vector, normalize_golden_case


def _finite(value: Any, name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{name} must be finite numeric")
    number = float(value)
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return number


def build_required_benchmark_candidates(
    case: Mapping[str, Any],
    topology,
) -> list[dict[str, Any]]:
    """Build HOLD + Independent + deterministic Joint candidates."""

    normalized = normalize_golden_case(case, topology)
    exterior_ids = sorted(
        edge.id
        for edge in topology.openings.values()
        if edge.controllable
        and topology.outside_id in (edge.source, edge.target)
    )
    hold = {
        opening_id: float(normalized["origin"]["opening_pct"][opening_id])
        for opening_id in exterior_ids
    }
    independent = independent_action_vector(normalized, topology)

    rows = [
        {
            "label": "HOLD",
            "policy_family": "hold",
            "actions": [
                {"opening_id": opening_id, "target_pct": hold[opening_id]}
                for opening_id in exterior_ids
            ],
        },
        {
            "label": "INDEPENDENT",
            "policy_family": "independent",
            "actions": [
                {
                    "opening_id": opening_id,
                    "target_pct": independent[opening_id],
                }
                for opening_id in exterior_ids
            ],
        },
    ]
    for candidate in normalized["joint_candidates"]:
        rows.append(
            {
                "label": f"JOINT:{candidate['label']}",
                "policy_family": "joint",
                "actions": [
                    {
                        "opening_id": opening_id,
                        "target_pct": float(candidate["opening_pct"][opening_id]),
                    }
                    for opening_id in exterior_ids
                ],
            }
        )
    return rows


def _movement_pct_sum(
    branch: Mapping[str, Any],
    origin_openings: Mapping[str, float],
) -> float:
    movement = 0.0
    seen = set()
    for action in branch.get("actions") or []:
        if action.get("kind") != "opening":
            continue
        opening_id = str(action["opening_id"])
        target = _finite(action["target_pct"], "benchmark action target_pct", minimum=0)
        if target > 100:
            raise ValueError("benchmark action target_pct outside [0,100]")
        if opening_id not in origin_openings:
            raise ValueError(f"benchmark action references unknown opening {opening_id}")
        if opening_id in seen:
            raise ValueError(f"duplicate benchmark action for {opening_id}")
        seen.add(opening_id)
        movement += abs(target - float(origin_openings[opening_id]))
    return movement


def _co2_metrics(
    series_by_zone: Mapping[str, list[float]],
    *,
    origin_co2: Mapping[str, float],
    time_step_s: int,
    safe_threshold_ppm: float,
) -> dict[str, Any]:
    if not series_by_zone:
        raise ValueError("benchmark requires co2_series_by_zone")
    lengths = {len(values) for values in series_by_zone.values()}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) <= 0:
        raise ValueError("benchmark CO2 series lengths must be equal and non-empty")

    step_count = next(iter(lengths))
    if set(origin_co2) != set(series_by_zone):
        raise ValueError("benchmark origin CO2 must cover the same zones as rollout series")
    normalized = {
        zone: [
            _finite(origin_co2[zone], f"origin CO2:{zone}", minimum=0),
            *[
                _finite(value, f"rollout CO2:{zone}", minimum=0)
                for value in values
            ],
        ]
        for zone, values in series_by_zone.items()
    }
    all_values = [value for values in normalized.values() for value in values]

    def trapezoid(values: list[float]) -> float:
        return sum(
            (values[index] + values[index + 1]) * 0.5 * time_step_s
            for index in range(len(values) - 1)
        )

    zone_auc = {
        zone: trapezoid(values)
        for zone, values in normalized.items()
    }
    zone_peak = {
        zone: max(values)
        for zone, values in normalized.items()
    }
    worst_zone = max(zone_peak, key=lambda zone: (zone_peak[zone], zone))

    unsafe_zone_steps = sum(
        value > safe_threshold_ppm
        for values in series_by_zone.values()
        for value in values
    )
    iaq_discomfort_ppmh_per_zone = (
        sum(
            trapezoid([
                max(0.0, value - safe_threshold_ppm)
                for value in values
            ])
            for values in normalized.values()
        )
        / 3600.0
        / len(normalized)
    )
    time_to_safe_s = None
    if all(
        normalized[zone][0] <= safe_threshold_ppm
        for zone in normalized
    ):
        time_to_safe_s = 0
    else:
        for sample_index in range(1, step_count + 1):
            if all(
                normalized[zone][sample_index] <= safe_threshold_ppm
                for zone in normalized
            ):
                time_to_safe_s = sample_index * time_step_s
                break

    return {
        "mean_co2_auc_ppm_s": round(
            sum(zone_auc.values()) / len(zone_auc), 3
        ),
        "worst_zone_co2_auc_ppm_s": round(max(zone_auc.values()), 3),
        "peak_co2_ppm": round(max(all_values), 3),
        "worst_zone_id": worst_zone,
        "worst_zone_peak_co2_ppm": round(zone_peak[worst_zone], 3),
        "zone_seconds_above_threshold": int(
            unsafe_zone_steps * time_step_s
        ),
        "iaq_discomfort_ppmh_per_zone": round(
            iaq_discomfort_ppmh_per_zone, 6
        ),
        "time_to_safe_s": time_to_safe_s,
    }


def score_benchmark_branch(
    branch: Mapping[str, Any],
    *,
    origin_openings: Mapping[str, float],
    origin_co2: Mapping[str, float],
    time_step_s: int,
    safe_threshold_ppm: float,
) -> dict[str, Any]:
    co2 = _co2_metrics(
        branch.get("co2_series_by_zone") or {},
        origin_co2=origin_co2,
        time_step_s=time_step_s,
        safe_threshold_ppm=safe_threshold_ppm,
    )
    safety = branch.get("safety_violations")
    prediction_error = branch.get("prediction_error")
    if safety is not None and (
        isinstance(safety,bool) or not isinstance(safety,int) or safety<0
    ):
        raise ValueError("safety_violations must be nonnegative integer")
    if prediction_error is not None:
        prediction_error = _finite(prediction_error, "prediction_error", minimum=0)

    return {
        "label": str(branch.get("label") or ""),
        "metrics": {
            **co2,
            "actuator_movement_pct_sum": round(
                _movement_pct_sum(branch, origin_openings), 3
            ),
            "safety_violations": (
                int(safety) if safety is not None else None
            ),
            "prediction_error": prediction_error,
        },
        "metric_availability": {
            "co2": "available",
            "actuator_movement": "available",
            "safety_violations": (
                "available" if safety is not None else "unavailable"
            ),
            "prediction_error": (
                "available" if prediction_error is not None else "unavailable"
            ),
        },
        "scalar_return": branch.get("return"),
    }


def build_policy_benchmark_report(
    *,
    response: Mapping[str, Any],
    case: Mapping[str, Any],
    topology,
) -> dict[str, Any]:
    """Build a same-origin multi-metric benchmark receipt."""

    normalized = normalize_golden_case(case, topology)
    branches = response.get("branches")
    if not isinstance(branches, list) or not branches:
        raise ValueError("benchmark response contains no branches")

    labels_list = [str(branch.get("label") or "") for branch in branches]
    if any(not label for label in labels_list) or len(set(labels_list)) != len(labels_list):
        raise ValueError("benchmark labels must be nonempty and unique")
    labels = set(labels_list)
    if normalized["time_step_s"] <= 0 or normalized["horizon_steps"] <= 0:
        raise ValueError("benchmark horizon and time step must be positive")
    required = {"HOLD", "INDEPENDENT"}
    missing = sorted(required - labels)
    if missing:
        raise ValueError(
            "benchmark missing required baselines: " + ",".join(missing)
        )
    if not any(label.startswith("JOINT:") for label in labels):
        raise ValueError("benchmark requires at least one JOINT candidate")

    # HOLD is an actual backend rollout, not a repeated t0 snapshot.
    # Validate the declared no-movement action against all exterior openings.
    exterior = {
        edge.id for edge in topology.openings.values()
        if edge.controllable and topology.outside_id in (edge.source,edge.target)
    }
    hold_branch = next(branch for branch in branches if branch["label"] == "HOLD")
    hold_actions = [action for action in hold_branch.get("actions", []) if action.get("kind")=="opening"]
    if {action.get("opening_id") for action in hold_actions} != exterior or len(hold_actions)!=len(exterior):
        raise ValueError("HOLD must explicitly cover all exterior openings")
    if _movement_pct_sum(hold_branch, normalized["origin"]["opening_pct"]) != 0:
        raise ValueError("HOLD cannot change any opening")
    for branch in branches:
        series = branch.get("co2_series_by_zone")
        if not isinstance(series, Mapping) or set(series) != set(normalized["origin"]["co2_ppm"]):
            raise ValueError("benchmark branch has missing or extra CO2 zones")
        if any(
            not isinstance(values,(list,tuple))
            or len(values) != normalized["horizon_steps"]
            for values in series.values()
        ):
            raise ValueError("benchmark branch CO2 horizon does not match golden case")

    rows = [
        score_benchmark_branch(
            branch,
            origin_openings=normalized["origin"]["opening_pct"],
            origin_co2=normalized["origin"]["co2_ppm"],
            time_step_s=normalized["time_step_s"],
            safe_threshold_ppm=normalized["metrics"]["iaq_reference_ppm"],
        )
        for branch in branches
    ]

    # Pareto frontier over metrics that are always available in the current
    # CO2/actuation benchmark. Lower is better for all four.
    def vector(row):
        m = row["metrics"]
        return (
            m["iaq_discomfort_ppmh_per_zone"],
            m["peak_co2_ppm"],
            m["zone_seconds_above_threshold"],
            m["actuator_movement_pct_sum"],
        )

    frontier = []
    for row in rows:
        rv = vector(row)
        dominated = False
        for other in rows:
            if other is row:
                continue
            ov = vector(other)
            if all(a <= b for a, b in zip(ov, rv)) and any(
                a < b for a, b in zip(ov, rv)
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(row["label"])

    return {
        "schema_version": "0.1",
        "benchmark": "airtrajectory-policy-benchmark-v0.1",
        "topology_id": normalized["topology_id"],
        "golden_case_id": normalized["golden_case_id"],
        "same_origin": True,
        "same_horizon": True,
        "time_step_s": normalized["time_step_s"],
        "horizon_steps": normalized["horizon_steps"],
        "required_baselines": ["HOLD", "INDEPENDENT", "JOINT"],
        "metric_parameters": {
            "iaq_threshold_ppm_by_zone": {
                zone_id: normalized["metrics"]["iaq_reference_ppm"]
                for zone_id in sorted(topology.zones)
            },
            "trajectory_integral": "trapezoidal-origin-plus-rollout",
            "threshold_duration": "discrete-sample-hold-post-step",
            "zone_aggregation": "mean",
        },
        "ranking_policy": "none; inspect metrics and Pareto frontier",
        "pareto_frontier": sorted(frontier),
        "results": sorted(rows, key=lambda row: row["label"]),
        "evidence_boundary": (
            "multi-metric benchmark receipt; scalar return is retained for "
            "compatibility but is not the benchmark proof"
        ),
    }
