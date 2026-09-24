"""Export trajectory-native transitions without erasing execution provenance."""
from dataclasses import asdict
import json
from pathlib import Path
from typing import Iterable
from .trajectory import Trajectory

def transition_rows(trajectory: Trajectory):
    """Yield offline-learning rows. Executed action is the behavior action; proposal is retained as context."""
    for step in trajectory.steps:
        yield {
            "schema_version":"0.1",
            "trajectory_id":trajectory.id,
            "topology_id":trajectory.topology_id,
            "policy_id":trajectory.policy_id,
            "environment_kind":trajectory.environment_kind,
            "step_index":step.index,
            "observation":step.observation,
            "proposed_actions":[asdict(a) for a in step.proposed_actions],
            "action":[asdict(a) for a in step.executed_actions],
            "intervention":step.intervention,
            "reward_vector":asdict(step.reward),
            "reward":step.reward.scalar(),
            "next_observation":step.next_observation,
            "terminated":step.terminated,
            "sensor_readings":[asdict(x) for x in step.sensor_readings],
            "actuator_feedback":[asdict(x) for x in step.actuator_feedback],
            "trace_id":step.info.get("trace_id"),
            "provenance":step.info.get("provenance"),
            "is_counterfactual":False,
        }

def export_jsonl(trajectories: Iterable[Trajectory], path: str | Path) -> int:
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); count=0
    with path.open("w",encoding="utf-8") as f:
        for trajectory in trajectories:
            for row in transition_rows(trajectory):
                f.write(json.dumps(row,ensure_ascii=False)+"\n"); count+=1
    return count

def counterfactual_rows(artifact: dict):
    """Keep simulated alternatives separate from behavior-policy data."""
    trace_id=artifact.get("trace_id")
    for branch in artifact.get("branches",[]):
        yield {
            "schema_version":"0.1",
            "request_id":artifact.get("request_id"),
            "trace_id":trace_id,
            "topology_id":artifact.get("topology_id"),
            "backend":artifact.get("backend"),
            "origin_kind":artifact.get("origin_kind"),
            "label":branch["label"],
            "target_pct":branch["target_pct"],
            "end_co2_ppm":branch["end_co2_ppm"],
            "return":branch["return"],
            "provenance":branch["provenance"],
            "is_counterfactual":True,
        }
