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
) -> Trajectory:
    observation, reset_info = env.reset()
    trajectory = Trajectory(
        topology_id=topology_id,
        policy_id=policy_id,
        context={"reset_info": reset_info},
    )

    for index in range(max_steps):
        proposed = list(policy(observation))

        # Safety resolver will sit between proposed and executed.
        executed = list(proposed)

        next_observation, reward, terminated, truncated, info = env.step(executed)

        trajectory.append(
            TrajectoryStep(
                index=index,
                observation=observation,
                proposed_actions=proposed,
                executed_actions=executed,
                next_observation=next_observation,
                reward=reward,
                terminated=terminated or truncated,
                info=info,
            )
        )

        observation = next_observation
        if terminated or truncated:
            break

    return trajectory
