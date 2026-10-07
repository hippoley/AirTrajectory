"""Golden Case scoring for Independent vs Joint real-CONTAM strategy comparison."""
from __future__ import annotations

import hashlib
import json
from statistics import mean
from typing import Any, Mapping

from .agents import MultiWindowRuleAgent


def _sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def normalize_golden_case(case: Mapping[str, Any], topology) -> dict[str, Any]:
    if not isinstance(case, Mapping):
        raise ValueError("golden case must be an object")
    if case.get("schema_version") != "0.1":
        raise ValueError("unsupported golden case schema_version")
    case_id = str(case.get("golden_case_id") or "")
    if not case_id:
        raise ValueError("golden_case_id is required")
    topology_id = str(case.get("topology_id") or "")
    if topology_id != str(topology.id):
        raise ValueError("golden case topology_id mismatch")

    origin = case.get("origin")
    if not isinstance(origin, Mapping):
        raise ValueError("golden case origin is required")
    co2 = origin.get("co2_ppm")
    openings = origin.get("opening_pct")
    if not isinstance(co2, Mapping) or set(co2) != set(topology.zones):
        raise ValueError("golden case origin co2_ppm must exactly cover topology zones")
    if not isinstance(openings, Mapping) or set(openings) != set(topology.openings):
        raise ValueError("golden case origin opening_pct must exactly cover topology openings")

    rule = case.get("independent_rule") or {}
    open_threshold = float(rule.get("open_threshold_ppm", 1200.0))
    close_threshold = float(rule.get("close_threshold_ppm", 800.0))
    open_target = float(rule.get("open_target_pct", 75.0))
    if not 0 <= open_target <= 100:
        raise ValueError("golden case independent open_target_pct out of range")

    exterior_ids = sorted(
        edge.id
        for edge in topology.openings.values()
        if edge.controllable
        and (
            edge.source == topology.outside_id
            or edge.target == topology.outside_id
        )
    )
    if not exterior_ids:
        raise ValueError("golden case topology has no controllable exterior openings")

    joint_candidates = case.get("joint_candidates")
    if not isinstance(joint_candidates, list) or not joint_candidates:
        raise ValueError("golden case joint_candidates are required")
    normalized_candidates = []
    labels = set()
    for raw in joint_candidates:
        if not isinstance(raw, Mapping):
            raise ValueError("joint candidate must be an object")
        label = str(raw.get("label") or "")
        if not label or label in labels:
            raise ValueError("joint candidate labels must be unique and non-empty")
        labels.add(label)
        values = raw.get("opening_pct")
        if not isinstance(values, Mapping) or set(values) != set(exterior_ids):
            raise ValueError(
                f"joint candidate {label} must exactly cover exterior openings"
            )
        normalized_values = {key: float(values[key]) for key in exterior_ids}
        if any(value < 0 or value > 100 for value in normalized_values.values()):
            raise ValueError(f"joint candidate {label} opening value out of range")
        normalized_candidates.append({
            "label": label,
            "opening_pct": normalized_values,
        })

    metrics = case.get("metrics") or {}
    iaq_reference = float(metrics.get("iaq_reference_ppm", 1000.0))
    high_co2 = float(metrics.get("high_co2_ppm", 1200.0))
    if iaq_reference <= 0 or high_co2 <= iaq_reference:
        raise ValueError("golden case CO2 metric thresholds are invalid")

    weights = case.get("objective_weights") or {}
    required_weights = (
        "mean_excess_1000",
        "max_excess_1200",
        "high_co2_zone_steps",
        "mean_room_imbalance",
        "movement_pct_sum",
    )
    normalized_weights = {}
    for key in required_weights:
        value = float(weights.get(key, 0.0))
        if value < 0:
            raise ValueError(f"golden case objective weight {key} must be non-negative")
        normalized_weights[key] = value

    payload = {
        "schema_version": "0.1",
        "golden_case_id": case_id,
        "topology_id": topology_id,
        "evidence_level": str(case.get("evidence_level") or "real-contam-demo"),
        "engineering_truth": bool(case.get("engineering_truth", False)),
        "time_step_s": int(case.get("time_step_s", 60)),
        "horizon_steps": int(case.get("horizon_steps", 3)),
        "origin": {
            "co2_ppm": {key: float(co2[key]) for key in sorted(co2)},
            "opening_pct": {key: float(openings[key]) for key in sorted(openings)},
        },
        "independent_rule": {
            "open_threshold_ppm": open_threshold,
            "close_threshold_ppm": close_threshold,
            "open_target_pct": open_target,
        },
        "joint_candidates": normalized_candidates,
        "metrics": {
            "iaq_reference_ppm": iaq_reference,
            "high_co2_ppm": high_co2,
        },
        "objective_weights": normalized_weights,
        "note": str(case.get("note") or ""),
    }
    if payload["time_step_s"] <= 0 or payload["horizon_steps"] <= 0:
        raise ValueError("golden case time_step_s/horizon_steps must be positive")
    return {
        **payload,
        "golden_case_sha256": _sha256(payload),
    }


def independent_action_vector(case: Mapping[str, Any], topology) -> dict[str, float]:
    normalized = normalize_golden_case(case, topology)
    rule = normalized["independent_rule"]
    agent = MultiWindowRuleAgent(
        topology,
        open_threshold=rule["open_threshold_ppm"],
        close_threshold=rule["close_threshold_ppm"],
        open_target_pct=rule["open_target_pct"],
    )
    observation = {
        "co2_ppm": normalized["origin"]["co2_ppm"],
        "opening_pct": normalized["origin"]["opening_pct"],
        "rain": False,
    }
    actions = agent(observation)
    exterior = {
        edge.id
        for edge in topology.openings.values()
        if edge.controllable
        and (
            edge.source == topology.outside_id
            or edge.target == topology.outside_id
        )
    }
    values = {
        action.opening_id: float(action.target_pct)
        for action in actions
        if action.opening_id in exterior
    }
    if set(values) != exterior:
        raise RuntimeError("independent policy did not cover every exterior opening")
    return {key: values[key] for key in sorted(values)}


def build_strategy_candidates(case: Mapping[str, Any], topology) -> list[dict[str, Any]]:
    normalized = normalize_golden_case(case, topology)
    independent = independent_action_vector(normalized, topology)
    candidates = [{
        "label": "independent-reference",
        "actions": [
            {"opening_id": opening_id, "target_pct": independent[opening_id]}
            for opening_id in sorted(independent)
        ],
    }]
    for candidate in normalized["joint_candidates"]:
        candidates.append({
            "label": candidate["label"],
            "actions": [
                {"opening_id": opening_id, "target_pct": candidate["opening_pct"][opening_id]}
                for opening_id in sorted(candidate["opening_pct"])
            ],
        })
    return candidates


def score_strategy_branch(
    branch: Mapping[str, Any],
    *,
    case: Mapping[str, Any],
    topology,
) -> dict[str, Any]:
    normalized = normalize_golden_case(case, topology)
    series = branch.get("co2_series_by_zone")
    if not isinstance(series, Mapping) or set(series) != set(topology.zones):
        raise ValueError("strategy branch lacks complete co2_series_by_zone")
    lengths = {len(series[zone]) for zone in series}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) <= 0:
        raise ValueError("strategy branch CO2 series lengths are inconsistent")

    zone_order = sorted(series)
    step_count = next(iter(lengths))
    vectors = [
        [float(series[zone][index]) for zone in zone_order]
        for index in range(step_count)
    ]
    all_values = [value for vector in vectors for value in vector]
    iaq_ref = normalized["metrics"]["iaq_reference_ppm"]
    high = normalized["metrics"]["high_co2_ppm"]

    mean_excess = mean(max(0.0, value - iaq_ref) for value in all_values)
    max_excess = max(0.0, max(all_values) - high)
    high_steps = sum(1 for value in all_values if value > high)
    mean_imbalance = mean(max(vector) - min(vector) for vector in vectors)

    origin = normalized["origin"]["opening_pct"]
    action_targets = {}
    for action in branch.get("actions") or []:
        if action.get("kind") == "opening":
            action_targets[str(action["opening_id"])] = float(action["target_pct"])
    exterior_ids = {
        edge.id
        for edge in topology.openings.values()
        if edge.controllable
        and (
            edge.source == topology.outside_id
            or edge.target == topology.outside_id
        )
    }
    if set(action_targets) != exterior_ids:
        raise ValueError("strategy branch actions must cover every exterior opening")
    movement = sum(
        abs(action_targets[opening_id] - float(origin[opening_id]))
        for opening_id in sorted(exterior_ids)
    )

    metrics = {
        "mean_co2_ppm": round(mean(all_values), 3),
        "max_co2_ppm": round(max(all_values), 3),
        "mean_excess_1000_ppm": round(mean_excess, 3),
        "max_excess_1200_ppm": round(max_excess, 3),
        "high_co2_zone_steps": int(high_steps),
        "mean_room_imbalance_ppm": round(mean_imbalance, 3),
        "movement_pct_sum": round(movement, 3),
    }
    weights = normalized["objective_weights"]
    objective = (
        weights["mean_excess_1000"] * mean_excess
        + weights["max_excess_1200"] * max_excess
        + weights["high_co2_zone_steps"] * high_steps
        + weights["mean_room_imbalance"] * mean_imbalance
        + weights["movement_pct_sum"] * movement
    )
    return {
        "label": str(branch.get("label") or ""),
        "metrics": metrics,
        "objective_score": round(float(objective), 6),
    }


def compare_independent_vs_joint(
    *,
    response: Mapping[str, Any],
    case: Mapping[str, Any],
    topology,
    prj_sha256: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_golden_case(case, topology)
    branches = response.get("branches")
    if not isinstance(branches, list) or not branches:
        raise ValueError("strategy response contains no branches")

    scored = [
        score_strategy_branch(branch, case=normalized, topology=topology)
        for branch in branches
    ]
    by_label = {row["label"]: row for row in scored}
    independent = by_label.get("independent-reference")
    if independent is None:
        raise ValueError("strategy response lacks independent-reference branch")

    joint_rows = [
        row for row in scored if row["label"] != "independent-reference"
    ]
    if not joint_rows:
        raise ValueError("strategy response lacks joint candidates")

    selected = min(
        [independent, *joint_rows],
        key=lambda row: (row["objective_score"], row["label"]),
    )
    best_joint_only = min(
        joint_rows,
        key=lambda row: (row["objective_score"], row["label"]),
    )

    delta = round(
        float(independent["objective_score"])
        - float(selected["objective_score"]),
        6,
    )
    if selected["label"] == "independent-reference":
        outcome = "TIE"
    elif delta > 0:
        outcome = "WIN"
    else:
        outcome = "TIE"

    candidate_payload = build_strategy_candidates(normalized, topology)
    payload = {
        "schema_version": "0.1",
        "comparison": "independent-vs-joint-real-contam-golden-v1",
        "status": "PASS",
        "golden_case_id": normalized["golden_case_id"],
        "golden_case_sha256": normalized["golden_case_sha256"],
        "topology_id": normalized["topology_id"],
        "prj_sha256": prj_sha256,
        "time_step_s": normalized["time_step_s"],
        "horizon_steps": normalized["horizon_steps"],
        "initial_state_sha256": _sha256(normalized["origin"]),
        "candidate_set_sha256": _sha256(candidate_payload),
        "independent": independent,
        "best_joint_only": best_joint_only,
        "selected": selected,
        "joint_vs_independent_outcome": outcome,
        "objective_improvement": delta,
        "non_regression": selected["objective_score"] <= independent["objective_score"],
        "all_candidates": sorted(scored, key=lambda row: row["label"]),
        "engineering_truth": False,
        "evidence_boundary": "real ContamX demo Golden Case; no field validation",
    }
    return {
        **payload,
        "comparison_sha256": _sha256(payload),
    }
