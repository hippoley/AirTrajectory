"""Minimal read-only decision API for independent contract consumers.

No physics is generated and no physical action is authorized. This is a
facade over the canonical v0.2 ObjectiveContract comparison, not a second
ranking algorithm or a deployment SDK.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .multi_environment_compare import compare_candidate_futures
from .objective import ObjectiveContract, compile_user_goal


def evaluate(
    *,
    candidates: Sequence[Mapping[str, Any]],
    origin_openings: Mapping[str, float],
    objective: ObjectiveContract | None = None,
    user_goal: str | None = None,
) -> dict[str, Any]:
    """Evaluate supplied futures from one explicit origin.

    Exactly one of `objective` or `user_goal` is required. `user_goal`
    supports only the deterministic preset vocabulary; unknown language
    fails closed. Every output declares execution_authorized=False.
    """
    if (objective is None) == (user_goal is None):
        raise ValueError("supply exactly one of objective or user_goal")
    if objective is not None and not isinstance(objective, ObjectiveContract):
        raise TypeError("objective must be an ObjectiveContract")
    contract = objective if objective is not None else compile_user_goal(user_goal)
    return compare_candidate_futures(
        candidates, objective=contract, origin_openings=origin_openings,
    )
