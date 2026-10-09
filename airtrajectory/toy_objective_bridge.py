"""Bridge *actual toy-backend first-step* outcomes to the Objective Contract.

Deliberately CO2-only. Does not invent PM2.5, thermal or humidity physics,
pretend that one-step actions are full-horizon interventions, or authorize
physical control.
"""
from __future__ import annotations

from typing import Any, Mapping

from .multi_environment_compare import compare_candidate_futures
from .objective import ObjectiveContract, PollutantGoal
from .toy_ablation import verify_toy_ablation


def compare_toy_episode_first_step(
    artifact: Mapping[str, Any], *, episode_index: int = 0,
    co2_target_ppm: float = 1000.0,
) -> dict[str, Any]:
    """Compare five already-simulated policies at t=0→1 min.

    This is not a multi-environment claim: absent PM2.5/thermal/RH results
    remain unavailable and no pollutant transport is imputed.
    """
    verify_toy_ablation(artifact)
    if artifact["evaluation"]["physics_backend"] != "toy-scenario-v1":
        raise ValueError("only toy-scenario-v1 artifacts are supported")
    if not 0 <= episode_index < len(artifact["episodes"]):
        raise ValueError("episode_index outside verified artifact")
    episode = artifact["episodes"][episode_index]
    origin_obs = episode["origin"]
    opening_kinds = {
        opening["id"]: opening["kind"]
        for opening in episode["topology"]["openings"]
    }
    openings = dict(origin_obs["opening_pct"])
    if set(opening_kinds) != set(openings):
        raise ValueError("topology/opening observation mismatch")
    if not isinstance(origin_obs.get("rain"), bool):
        raise ValueError("toy origin missing rain")
    initial = {
        "opening_pct": openings,
        "opening_kind": opening_kinds,
        "rain": origin_obs["rain"],
        "co2_ppm": dict(origin_obs["co2_ppm"]),
    }
    objective = ObjectiveContract(
        objective_id="toy-co2-first-step-v0.1",
        pollutants={"co2_ppm": PollutantGoal("co2_ppm", co2_target_ppm)},
        priorities=("co2_excess", "movement"),
        max_intervention_min=1.0,
        rain_hard_constraint=True,
        source_text="CO2-only first-step diagnostic, not a user-goal parser",
    )
    candidates = []
    for label in artifact["evaluation"]["policies"]:
        run = episode["policies"][label]
        first = run["frames"][0]
        actions = list(first["executed_actions"])
        if len({a["opening_id"] for a in actions}) != len(actions):
            raise ValueError("backend emitted duplicate opening actions")
        changed = any(
            float(a["target_pct"]) != float(openings[a["opening_id"]])
            for a in actions
        )
        candidates.append({
            "label": label,
            "origin": initial,
            "time_grid_min": [0.0, 1.0],
            "series_by_metric": {
                "co2_ppm": {
                    zone: [float(value), float(first["co2_ppm"][zone])]
                    for zone, value in initial["co2_ppm"].items()
                }
            },
            "actions": actions,
            "duration_min": 1.0 if changed else 0.0,
            "rain": initial["rain"],
            "provenance": {
                "kind": "simulated",
                "backend": "toy-scenario-v1",
                "engineering_truth": False,
                "source_artifact_sha256": artifact["artifact_sha256"],
                "source_scenario_id": episode["scenario_id"],
                "source_policy_id": label,
            },
        })
    report = compare_candidate_futures(
        candidates, objective=objective, origin_openings=openings
    )
    return {
        "schema_version": "0.1",
        "adapter": "airtrajectory-toy-first-step-objective-v0.1",
        "source_artifact_sha256": artifact["artifact_sha256"],
        "scenario_id": episode["scenario_id"],
        "origin_sha256": report["origin_sha256"],
        "time_grid_min": report["time_grid_min"],
        "observed_metric_fields": ["co2_ppm"],
        "unavailable_metric_fields": [
            "pm25_ug_m3", "temperature_c", "relative_humidity_pct",
            "tvoc_ug_m3", "hcho_mg_m3",
        ],
        "decision": report,
        "status": "TOY_FIRST_STEP_DIAGNOSTIC",
        "execution_authorized": False,
        "claim_boundary": (
            "Only t=0 to t=1 backend-produced toy CO2 is evaluated. "
            "Not a full trajectory comparison, multi-environment physics, "
            "post-training benefit, real CONTAM or measured physical evidence."
        ),
    }
