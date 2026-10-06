"""Compile engineering CONTAM profiles from raw evidence bundles."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.contam_profile_compiler import (
    compile_airflow_profile_from_evidence,
    compile_boundary_profile_from_evidence,
    compile_metric_overlay_from_evidence,
)
from airtrajectory.layout import LayoutContract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "kind",
        choices=("metric", "airflow", "boundary"),
    )
    parser.add_argument("bundle", type=Path)
    parser.add_argument(
        "--layout",
        type=Path,
        default=Path("web/data/home_topology.fixed.json"),
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    layout = LayoutContract.from_file(args.layout)
    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    compiler = {
        "metric": compile_metric_overlay_from_evidence,
        "airflow": compile_airflow_profile_from_evidence,
        "boundary": compile_boundary_profile_from_evidence,
    }[args.kind]
    result = compiler(layout, bundle)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
