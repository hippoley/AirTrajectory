"""Bind weather/wind and contaminant forcing to a CONTAM manifest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.contam_allocator import allocate_contam_ids
from airtrajectory.contam_boundary import bind_boundary_profile
from airtrajectory.contam_ir import compile_contam_ir
from airtrajectory.contam_profile import (
    bind_airflow_elements,
    illustrative_opening_profile,
)
from airtrajectory.layout import LayoutContract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("layout", type=Path)
    parser.add_argument("boundary_profile", type=Path)
    parser.add_argument("--airflow-profile", type=Path)
    parser.add_argument("--illustrative-demo-airflow", action="store_true")
    parser.add_argument("--require-engineering-validated", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    if bool(args.airflow_profile) == bool(args.illustrative_demo_airflow):
        parser.error(
            "choose exactly one of --airflow-profile or --illustrative-demo-airflow"
        )

    layout = LayoutContract.from_file(args.layout)
    manifest = allocate_contam_ids(compile_contam_ir(layout))

    if args.airflow_profile is not None:
        airflow = json.loads(args.airflow_profile.read_text(encoding="utf-8"))
    else:
        airflow = illustrative_opening_profile()

    manifest = bind_airflow_elements(
        manifest,
        airflow,
        require_engineering_validated=args.require_engineering_validated,
    )

    boundary = json.loads(args.boundary_profile.read_text(encoding="utf-8"))
    manifest = bind_boundary_profile(
        manifest,
        boundary,
        require_engineering_validated=args.require_engineering_validated,
    )

    rendered = json.dumps(manifest, indent=2, sort_keys=True)
    print(rendered)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
