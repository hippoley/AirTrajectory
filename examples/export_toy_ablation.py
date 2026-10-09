"""Generate a reproducible, browser-consumable toy ablation artifact.

Usage:
    python examples/export_toy_ablation.py --train-count 6 --test-count 3
    python examples/export_toy_ablation.py --out web/data/toy_ablation.json
"""
import argparse
import json
from pathlib import Path

from airtrajectory.toy_ablation import same_origin_toy_ablation, verify_toy_ablation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-count", type=int, default=24)
    parser.add_argument("--test-count", type=int, default=8)
    parser.add_argument("--horizon", type=int, default=30)
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--test-families", default="chain", help="comma-separated: chain,branch,hub,loop,irregular")
    parser.add_argument("--out", type=Path, default=Path("web/data/toy_ablation.json"))
    args = parser.parse_args()
    artifact = same_origin_toy_ablation(
        train_count=args.train_count,
        test_count=args.test_count,
        horizon_steps=args.horizon,
        seed=args.seed,
        test_families=tuple(x.strip() for x in args.test_families.split(",")),
    )
    verify_toy_ablation(artifact)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "TOY_ABLATION_ARTIFACT_VERIFIED",
        artifact["artifact_sha256"],
        args.out,
        "episodes", len(artifact["episodes"]),
        "policies", len(artifact["evaluation"]["policies"]),
        "physics", artifact["evaluation"]["physics_backend"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
