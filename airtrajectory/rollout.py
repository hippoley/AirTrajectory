from typing import Callable, Iterable

from .environment import VentilationEnvironment
from .trajectory import Trajectory, TrajectoryStep, TransitionAction

Policy = Callable[[dict], Iterable[TransitionAction]]


def rollout(
    env: VentilationEnvironment,
    policy: Policy,
    topology_id: str,
    policy_id: str,
    max_steps: int = 120,
    safety_resolver=None,
    context_extra=None,
    environment_kind: str | None = None,
) -> Trajectory:
    observation, reset_info = env.reset()
    context={"reset_info": reset_info}
    if context_extra:
        context.update(dict(context_extra))
    inferred_kind = environment_kind
    if inferred_kind is None:
        evidence_kind = str(reset_info.get("evidence_kind") or "")
        inferred_kind = "physical" if evidence_kind == "physical" else "simulation"
    trajectory = Trajectory(
        topology_id=topology_id,
        policy_id=policy_id,
        environment_kind=inferred_kind,
        context=context,
    )

    for index in range(max_steps):
        proposed = list(policy(observation))

        intervention = None
        if safety_resolver is None:
            executed = list(proposed)
        else:
            decision = safety_resolver.resolve(observation, proposed)
            proposed = list(decision.proposed)
            executed = list(decision.executed)
            intervention = decision.intervention

        next_observation, reward, terminated, truncated, info = env.step(executed)
        info = dict(info)
        info["safety_intervened"] = intervention is not None

        observation_evidence = list(observation.get("sensor_readings", [])) if isinstance(observation, dict) else []
        next_evidence = list(info.get("next_sensor_readings", []))
        actuator_feedback = list(info.get("actuator_feedback", []))
        clean_observation = dict(observation)
        clean_next_observation = dict(next_observation)
        clean_observation.pop("sensor_readings", None)
        clean_next_observation.pop("sensor_readings", None)

        trajectory.append(
            TrajectoryStep(
                index=index,
                observation=clean_observation,
                proposed_actions=proposed,
                executed_actions=executed,
                next_observation=clean_next_observation,
                reward=reward,
                sensor_readings=observation_evidence,
                next_sensor_readings=next_evidence,
                actuator_feedback=actuator_feedback,
                intervention=intervention,
                terminated=terminated or truncated,
                info=info,
            )
        )

        observation = next_observation
        if terminated or truncated:
            break

    return trajectory
