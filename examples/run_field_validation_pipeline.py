"""Run import → alignment → prediction-vs-field validation in one command."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.field_validation_pipeline import (
    run_field_validation_pipeline,
)
from airtrajectory.layout import LayoutContract


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("runtime_receipt", type=Path)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("records", type=Path)
    parser.add_argument(
        "--format",
        choices=("auto", "jsonl", "csv"),
        default="auto",
    )
    parser.add_argument(
        "--layout",
        type=Path,
        default=Path("web/data/home_topology.fixed.json"),
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--aligned-out", type=Path)
    parser.add_argument("--require-pass", action="store_true")
    args = parser.parse_args()

    receipt, aligned = run_field_validation_pipeline(
        layout=LayoutContract.from_file(args.layout),
        runtime_receipt=_load(args.runtime_receipt),
        protocol=_load(args.protocol),
        manifest_path=args.manifest,
        records_path=args.records,
        records_format=args.format,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.aligned_out is not None:
        args.aligned_out.parent.mkdir(parents=True, exist_ok=True)
        args.aligned_out.write_text(
            json.dumps(aligned, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if args.require_pass and not receipt["field_validation_verified"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
