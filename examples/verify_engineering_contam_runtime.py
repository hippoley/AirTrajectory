"""Verify an engineering-input CONTAM PRJ through the shared runtime."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.contam_runtime_verification import (
    verify_engineering_contam_runtime,
)
from airtrajectory.layout import LayoutContract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prj", type=Path)
    parser.add_argument("build_receipt", type=Path)
    parser.add_argument(
        "--layout",
        type=Path,
        default=Path("web/data/home_topology.fixed.json"),
    )
    parser.add_argument("--steps", type=int, default=2)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    receipt = verify_engineering_contam_runtime(
        layout=LayoutContract.from_file(args.layout),
        prj_path=args.prj,
        build_receipt=json.loads(
            args.build_receipt.read_text(encoding="utf-8")
        ),
        steps=args.steps,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
