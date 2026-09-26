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
) -> Trajectory:
    observation, reset_info = env.reset()
    trajectory = Trajectory(
        topology_id=topology_id,
        policy_id=policy_id,
        context={"reset_info": reset_info},
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

        trajectory.append(
            TrajectoryStep(
                index=index,
                observation=observation,
                proposed_actions=proposed,
                executed_actions=executed,
                next_observation=next_observation,
                reward=reward,
                intervention=intervention,
                terminated=terminated or truncated,
                info=info,
            )
        )

        observation = next_observation
        if terminated or truncated:
            break

    return trajectory
