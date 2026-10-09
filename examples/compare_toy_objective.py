"""Project five actual toy-backend policy outcomes through ObjectiveContract.

Usage:
  python examples/compare_toy_objective.py --artifact web/data/toy_ablation.json
"""
import argparse
import json
from pathlib import Path

from airtrajectory.toy_objective_bridge import compare_toy_episode_first_step


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, default=Path("web/data/toy_ablation.json"))
    parser.add_argument("--episode-index", type=int, default=None, help="default: all episodes")
    parser.add_argument("--out", type=Path, default=Path("web/data/toy_objective_comparison.json"))
    args = parser.parse_args()
    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    indices = (range(len(artifact["episodes"])) if args.episode_index is None else [args.episode_index])
    reports = [compare_toy_episode_first_step(artifact, episode_index=i) for i in indices]
    report = {
        "schema_version": "0.1",
        "status": "TOY_CO2_ONLY_NOT_ENGINEERING_TRUTH",
        "source_artifact_sha256": artifact["artifact_sha256"],
        "episodes": reports,
        "execution_authorized": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "TOY_OBJECTIVE_BACKEND_PROJECTION_VERIFIED",
        report["source_artifact_sha256"],
        report["status"],
        len(report["episodes"]),
        args.out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
