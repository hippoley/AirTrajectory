"""Compare supplied multi-environment futures using an Objective Contract."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.multi_environment_compare import compare_candidate_futures
from airtrajectory.objective import compile_user_goal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "scenario",
        type=Path,
        nargs="?",
        default=Path("examples/multi_environment_conflict_v0.2.json"),
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.scenario.read_text(encoding="utf-8"))
    objective = compile_user_goal(payload["user_goal"])
    report = compare_candidate_futures(
        payload["candidates"],
        objective=objective,
        origin_openings=payload["origin_opening_pct"],
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
