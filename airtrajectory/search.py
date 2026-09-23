from dataclasses import dataclass
from itertools import product
from typing import Dict, Iterable, Sequence

from .environment import SnapshotableEnvironment
from .fork import BranchResult, fork_actions
from .trajectory import TransitionAction


@dataclass(frozen=True)
class SearchResult:
    label: str
    actions: tuple[TransitionAction, ...]
    branch: BranchResult


def exhaustive_opening_search(
    env: SnapshotableEnvironment,
    opening_ids: Sequence[str],
    *,
    levels: Sequence[int] = (0, 25, 50, 75, 100),
    fixed_actions: Iterable[TransitionAction] = (),
    horizon_steps: int = 30,
    top_k: int = 4,
) -> list[SearchResult]:
    """Rank fixed opening configurations from the exact same snapshot.

    This is a deterministic search baseline, not a learned controller.
    Higher scalar return ranks first.
    """
    if not opening_ids:
        raise ValueError("opening_ids must not be empty")
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    if not levels:
        raise ValueError("levels must not be empty")

    fixed = tuple(fixed_actions)
    candidates: Dict[str, tuple[TransitionAction, ...]] = {}
    for values in product(levels, repeat=len(opening_ids)):
        variable = tuple(TransitionAction(opening_id, value) for opening_id, value in zip(opening_ids, values))
        label = "SEARCH · " + "/".join(str(v) for v in values)
        candidates[label] = variable + fixed

    branches = fork_actions(env, candidates, horizon_steps=horizon_steps)
    ranked = sorted(branches.values(), key=lambda branch: branch.return_value, reverse=True)
    return [SearchResult(branch.label, tuple(branch.actions), branch) for branch in ranked[:top_k]]
