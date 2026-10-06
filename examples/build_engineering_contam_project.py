"""Build an engineering-input CONTAM project from approved evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.contam_engineering_build import (
    build_engineering_contam_project,
    write_engineering_build_receipt,
)
from airtrajectory.layout import LayoutContract


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--layout",
        type=Path,
        default=Path("web/data/home_topology.fixed.json"),
    )
    parser.add_argument("--metric-evidence", type=Path, required=True)
    parser.add_argument("--airflow-evidence", type=Path, required=True)
    parser.add_argument("--boundary-evidence", type=Path, required=True)
    parser.add_argument("--prj-profile", type=Path, required=True)
    parser.add_argument("--prj-review-evidence", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    provenance = build_engineering_contam_project(
        layout=LayoutContract.from_file(args.layout),
        metric_evidence=_load(args.metric_evidence),
        airflow_evidence=_load(args.airflow_evidence),
        boundary_evidence=_load(args.boundary_evidence),
        prj_profile=_load(args.prj_profile),
        prj_review_evidence=_load(args.prj_review_evidence),
        out_path=args.out,
    )
    write_engineering_build_receipt(provenance, args.receipt)
    print(json.dumps(provenance, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
