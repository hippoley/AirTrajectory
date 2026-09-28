"""Inspect one layout contract and report physics-compiler readiness."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.layout import LayoutContract
from airtrajectory.spatial_compile import compile_spatial_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("layout", type=Path)
    parser.add_argument(
        "--require-contam-input-ready",
        action="store_true",
        help="exit non-zero unless metric geometry is complete",
    )
    args = parser.parse_args()

    layout = LayoutContract.from_file(args.layout)
    plan = compile_spatial_plan(layout)
    contam = plan["backend_requirements"]["contam"]

    result = {
        "topology_id": plan["topology_id"],
        "layout_contract_sha256": plan["layout_contract_sha256"],
        "coordinate_space": plan["coordinate_space"],
        "metric_geometry_ready": plan["metric_geometry_ready"],
        "contam_metric_inputs_ready": contam["metric_inputs_ready"],
        "prj_generation_implemented": contam["prj_generation_implemented"],
        "missing_metric_wall_fields": contam["missing_metric_wall_fields"],
        "missing_metric_opening_fields": contam["missing_metric_opening_fields"],
    }
    print(json.dumps(result, indent=2, sort_keys=True))

    if args.require_contam_input_ready and not contam["metric_inputs_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
