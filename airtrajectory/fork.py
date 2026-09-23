from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List

from .environment import SnapshotableEnvironment
from .trajectory import RewardVector, TransitionAction


@dataclass
class BranchResult:
    label: str
    actions: List[TransitionAction]
    observations: List[dict]
    rewards: List[RewardVector]
    return_value: float
    terminated: bool


def fork_actions(
    env: SnapshotableEnvironment,
    candidates: Dict[str, Iterable[TransitionAction]],
    horizon_steps: int = 10,
    continuation: Callable[[dict], Iterable[TransitionAction]] | None = None,
) -> Dict[str, BranchResult]:
    """Evaluate alternative futures from exactly the same environment state.

    The source environment is restored after every branch and before returning.
    """
    origin = env.snapshot()
    results: Dict[str, BranchResult] = {}

    try:
        for label, first_actions in candidates.items():
            env.restore(origin)
            actions = list(first_actions)
            observations = []
            rewards = []
            terminated = False

            for index in range(horizon_steps):
                step_actions = actions if index == 0 else (
                    list(continuation(observations[-1])) if continuation else actions
                )
                obs, reward, done, truncated, _ = env.step(step_actions)
                observations.append(obs)
                rewards.append(reward)
                terminated = done or truncated
                if terminated:
                    break

            results[label] = BranchResult(
                label=label,
                actions=actions,
                observations=observations,
                rewards=rewards,
                return_value=sum(r.scalar() for r in rewards),
                terminated=terminated,
            )
    finally:
        env.restore(origin)

    return results
