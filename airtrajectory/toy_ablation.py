"""Replayable, same-origin toy ablation for the existing learning policies.

This is an experiment artifact generator, NOT a claim of engineering airflow,
CONTAM execution, real-world evidence, or proven post-training advantage.
"""
from __future__ import annotations

import hashlib
import json
from statistics import mean
from typing import Any, Mapping

from .agents import MultiWindowRuleAgent
from .dataset import transition_rows
from .environment import ScenarioMultizoneEnvironment
from .factory import TrajectoryFactory
from .learning import TopologyBCPolicy, TopologyOfflineQPolicy
from .physical import SafetyResolver
from .rollout import rollout
from .scenario import topology_manifest
from .structural_scenarios import generate_structural_scenario
from .trajectory import TransitionAction, Trajectory


def _sha(payload: Any) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class HoldPolicy:
    """Keep the current opening positions unchanged."""

    def __call__(self, observation: Mapping[str, Any]) -> list[TransitionAction]:
        return []


class IndependentWindowPolicy:
    """Open at most one exterior window per step; no coordinated window search.

    Interior doors follow the same 100%-open reference convention as the
    existing Rule/BC/Offline-Q policies. This is a *heuristic baseline*, not
    a stand-in for an actual non-post-trained language-model agent.
    """

    def __call__(self, observation: Mapping[str, Any]) -> list[TransitionAction]:
        windows = observation.get("opening_zone", {})
        co2 = observation["co2_ppm"]
        rain = bool(observation.get("rain", False))
        eligible = [
            opening_id for opening_id, zone_id in windows.items()
            if float(co2[zone_id]) >= 1200.0
        ]
        chosen = (
            sorted(eligible, key=lambda w: (-float(co2[windows[w]]), w))[0]
            if eligible and not rain else None
        )
        actions = [
            TransitionAction(w, 75.0 if w == chosen else 0.0)
            for w in sorted(windows)
        ]
        actions.extend(
            TransitionAction(door, 100.0)
            for door in sorted(observation.get("interior_openings", []))
        )
        return actions


def _metrics(trajectory: Trajectory, threshold_ppm: float) -> dict[str, float | int]:
    if not trajectory.steps:
        raise ValueError("empty trajectory cannot be benchmarked")
    all_values: list[float] = []
    motion_pct = 0.0
    intervention_steps = 0
    safety_violation_steps = 0
    for step in trajectory.steps:
        next_co2 = step.next_observation["co2_ppm"]
        all_values.extend(float(value) for value in next_co2.values())
        prior = step.observation["opening_pct"]
        for action in step.executed_actions:
            motion_pct += abs(float(action.target_pct) - float(prior[action.opening_id]))
        intervention_steps += int(bool(step.intervention))
        safety_violation_steps += int(step.reward.safety < 0)
    final_co2 = trajectory.steps[-1].next_observation["co2_ppm"]
    return {
        "mean_co2_excess_ppm": round(
            mean(max(0.0, value - threshold_ppm) for value in all_values), 6
        ),
        "worst_zone_peak_co2_ppm": round(max(all_values), 6),
        "final_worst_zone_co2_ppm": round(max(float(x) for x in final_co2.values()), 6),
        "zone_steps_above_threshold": sum(value > threshold_ppm for value in all_values),
        "total_window_and_door_motion_pct": round(motion_pct, 6),
        "safety_intervention_steps": intervention_steps,
        "safety_violation_steps": safety_violation_steps,
        "reward_return": round(trajectory.return_value, 6),
        "steps": len(trajectory.steps),
    }


def _frames(trajectory: Trajectory) -> list[dict[str, Any]]:
    return [
        {
            "step": step.index + 1,
            "co2_ppm": dict(step.next_observation["co2_ppm"]),
            "opening_pct": dict(step.next_observation["opening_pct"]),
            "proposed_actions": [
                {"opening_id": action.opening_id, "target_pct": action.target_pct}
                for action in step.proposed_actions
            ],
            "executed_actions": [
                {"opening_id": action.opening_id, "target_pct": action.target_pct}
                for action in step.executed_actions
            ],
            "intervention": step.intervention,
            "backend": step.info.get("backend"),
        }
        for step in trajectory.steps
    ]


def same_origin_toy_ablation(
    *, train_count: int = 24, test_count: int = 8,
    horizon_steps: int = 30, seed: int = 100,
    co2_threshold_ppm: float = 1000.0,
    test_families: tuple[str, ...] = ("chain",),
) -> dict[str, Any]:
    """Train current BC/Offline-Q and replay five policies on identical toy origins.

    Strictly distinguishes same-origin toy comparison from structural-family
    holdout, CONTAM-backed physics, and any measured physical validation.
    """
    if train_count < 1 or test_count < 1 or horizon_steps < 1:
        raise ValueError("train_count, test_count and horizon_steps must be positive")
    if co2_threshold_ppm <= 0:
        raise ValueError("co2_threshold_ppm must be positive")
    if not test_families or any(f not in {"chain", "branch", "hub", "loop", "irregular"} for f in test_families):
        raise ValueError("test_families must be non-empty supported graph families")

    factory = TrajectoryFactory(horizon_steps=horizon_steps, rooms=(2, 3, 4))
    train = [factory.rule_episode(seed + i) for i in range(train_count)]
    training_rows = [row for trajectory in train for row in transition_rows(trajectory)]
    bc = TopologyBCPolicy()
    offline_q = TopologyOfflineQPolicy()
    bc_samples = bc.fit(training_rows)
    q_samples = offline_q.fit(training_rows)

    episodes = []
    policy_names = ("HOLD", "Independent", "Rule Joint", "BC", "Offline-Q")
    for i in range(test_count):
        test_seed = seed + 10000 + i
        family = test_families[i % len(test_families)]
        scenario = generate_structural_scenario(test_seed, family)
        policies = {
            "HOLD": HoldPolicy(),
            "Independent": IndependentWindowPolicy(),
            "Rule Joint": MultiWindowRuleAgent(scenario.topology),
            "BC": bc,
            "Offline-Q": offline_q,
        }
        runs: dict[str, Any] = {}
        origin_sha: str | None = None
        for label, policy in policies.items():
            env = ScenarioMultizoneEnvironment(
                scenario, horizon_steps=horizon_steps
            )
            trajectory = rollout(
                env, policy, scenario.id, label,
                max_steps=horizon_steps, safety_resolver=SafetyResolver(),
            )
            if len(trajectory.steps) != horizon_steps:
                raise ValueError("different policy observation horizons")
            origin = trajectory.steps[0].observation
            digest = _sha(origin)
            if origin_sha is not None and digest != origin_sha:
                raise ValueError("policies do not share an identical initial origin")
            origin_sha = digest
            if any(
                step.info.get("backend") != "toy-scenario-v1"
                for step in trajectory.steps
            ):
                raise ValueError("unexpected or mixed physics backends")
            runs[label] = {
                "policy_id": label,
                "origin_sha256": digest,
                "physics_backend": "toy-scenario-v1",
                "metrics": _metrics(trajectory, co2_threshold_ppm),
                "frames": _frames(trajectory),
            }
        episodes.append({
            "scenario_id": scenario.id,
            "topology_family": family,
            "test_seed": test_seed,
            "topology": topology_manifest(scenario.topology),
            "origin": dict(trajectory.steps[0].observation),
            "origin_sha256": origin_sha,
            "horizon_steps": horizon_steps,
            "policies": runs,
        })

    aggregate = {}
    metric_names = (
        "mean_co2_excess_ppm",
        "worst_zone_peak_co2_ppm",
        "final_worst_zone_co2_ppm",
        "zone_steps_above_threshold",
        "total_window_and_door_motion_pct",
        "safety_intervention_steps",
        "safety_violation_steps",
        "reward_return",
    )
    for label in policy_names:
        aggregate[label] = {
            key: round(mean(
                episode["policies"][label]["metrics"][key]
                for episode in episodes
            ), 6)
            for key in metric_names
        }

    payload = {
        "schema_version": "airtrajectory-toy-ablation-v0.1",
        "experiment_id": "same-origin-toy-structural-v0.1",
        "status": "EXPLORATORY_NOT_ENGINEERING_TRUTH",
        "claim_boundary": (
            "Toy CO2 mixing only. Declared graph-family holdouts are toy "
            "topology tests, not CONTAM/CFD physics, no LLM-agent baseline, "
            "no measured physical tau0, and no demonstrated post-training gain."
        ),
        "training": {
            "physics_backend": "toy-scenario-v1",
            "data_source": "rule-policy-demonstrations",
            "train_room_counts": [2, 3, 4],
            "train_topology_families": ["chain"],
            "train_seeds": [seed + i for i in range(train_count)],
            "bc_samples": bc_samples,
            "offline_q_samples": q_samples,
        },
        "evaluation": {
            "physics_backend": "toy-scenario-v1",
            "test_room_counts": [5],
            "test_seeds": [seed + 10000 + i for i in range(test_count)],
            "test_topology_families": list(dict.fromkeys(episode["topology_family"] for episode in episodes)),
            "structural_family_holdout": all(episode["topology_family"] != "chain" for episode in episodes),
            "horizon_steps": horizon_steps,
            "dt_minutes": 1.0,
            "co2_threshold_ppm": co2_threshold_ppm,
            "policies": list(policy_names),
            "same_origin_verified": True,
            "safety_resolver": "SafetyResolver",
        },
        "aggregate": aggregate,
        "episodes": episodes,
    }
    payload["artifact_sha256"] = _sha(payload)
    return payload


def verify_toy_ablation(payload: Mapping[str, Any]) -> bool:
    """Reject tampered, mismatched, or overclaimed toy replay artifacts."""
    if payload.get("schema_version") != "airtrajectory-toy-ablation-v0.1":
        raise ValueError("unsupported toy ablation schema")
    if payload.get("status") != "EXPLORATORY_NOT_ENGINEERING_TRUTH":
        raise ValueError("toy evidence cannot be promoted to physical truth")
    ev = payload["evaluation"]
    if ev["physics_backend"] != "toy-scenario-v1":
        raise ValueError("toy evidence boundary is inconsistent")
    families = ev["test_topology_families"]
    if not families or any(f not in {"chain", "branch", "hub", "loop", "irregular"} for f in families):
        raise ValueError("invalid topology family")
    if ev["structural_family_holdout"] != ("chain" not in families):
        raise ValueError("structural holdout boundary is inconsistent")
    if set(payload["training"]["train_seeds"]) & set(ev["test_seeds"]):
        raise ValueError("training and test seeds overlap")
    expected = set(ev["policies"])
    if expected != {"HOLD", "Independent", "Rule Joint", "BC", "Offline-Q"}:
        raise ValueError("policy comparison is incomplete")
    if len(payload["episodes"]) != len(ev["test_seeds"]):
        raise ValueError("test episode count mismatch")
    for episode, seed in zip(payload["episodes"], ev["test_seeds"]):
        if episode["test_seed"] != seed:
            raise ValueError("test seed mismatch")
        if episode["topology_family"] not in families:
            raise ValueError("episode topology family mismatch")
        digest = _sha(episode["origin"])
        if episode["origin_sha256"] != digest:
            raise ValueError("origin hash mismatch")
        if set(episode["policies"]) != expected:
            raise ValueError("episode policy coverage mismatch")
        if episode["horizon_steps"] != ev["horizon_steps"]:
            raise ValueError("episode horizon mismatch")
        for label, run in episode["policies"].items():
            if run["origin_sha256"] != digest:
                raise ValueError(f"{label} has different origin")
            if run["physics_backend"] != ev["physics_backend"]:
                raise ValueError(f"{label} uses a different physics backend")
            frames = run["frames"]
            if len(frames) != ev["horizon_steps"]:
                raise ValueError(f"{label} has a different frame horizon")
            if [frame["step"] for frame in frames] != list(range(1, len(frames) + 1)):
                raise ValueError(f"{label} has invalid frame indices")
            if any(frame["backend"] != ev["physics_backend"] for frame in frames):
                raise ValueError(f"{label} has mixed frame provenance")
            if any(set(frame["co2_ppm"]) != set(episode["origin"]["co2_ppm"])
                   for frame in frames):
                raise ValueError(f"{label} has mismatched zone coverage")
    checksum = payload.get("artifact_sha256")
    content = {k: v for k, v in payload.items() if k != "artifact_sha256"}
    if checksum != _sha(content):
        raise ValueError("artifact checksum mismatch")
    return True
