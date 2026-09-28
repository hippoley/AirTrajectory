"""Bind CONTAM writer manifest flow paths to explicit airflow elements."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.contam_allocator import allocate_contam_ids
from airtrajectory.contam_ir import compile_contam_ir
from airtrajectory.contam_profile import (
    bind_airflow_elements,
    illustrative_opening_profile,
)
from airtrajectory.layout import LayoutContract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("layout", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--illustrative-demo-profile", action="store_true")
    parser.add_argument("--require-engineering-validated", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    if bool(args.profile) == bool(args.illustrative_demo_profile):
        parser.error(
            "choose exactly one of --profile or --illustrative-demo-profile"
        )

    if args.profile is not None:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
    else:
        profile = illustrative_opening_profile()

    layout = LayoutContract.from_file(args.layout)
    manifest = allocate_contam_ids(compile_contam_ir(layout))
    bound = bind_airflow_elements(
        manifest,
        profile,
        require_engineering_validated=args.require_engineering_validated,
    )

    rendered = json.dumps(bound, indent=2, sort_keys=True)
    print(rendered)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
