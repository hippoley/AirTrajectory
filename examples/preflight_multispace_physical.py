"""Read-only multi-window physical preflight for the demo.

This command never calls set_position() and therefore never moves hardware.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.demo_physical_config import (
    build_windowpilot_drivers,
    load_windowpilot_driver_config,
)
from airtrajectory.demo_runtime import DemoRuntimeSnapshot
from airtrajectory.layout import LayoutContract
from airtrajectory.multiwindow_physical import MultiWindowPhysicalEnvironment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--layout",
        type=Path,
        default=Path("web/data/home_topology.fixed.json"),
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    layout = LayoutContract.from_file(args.layout)
    snapshot = DemoRuntimeSnapshot.resolve(layout)
    config = load_windowpilot_driver_config(args.config)
    if config.get("topology_id") != layout.topology_id:
        raise ValueError("physical config topology_id does not match layout")

    drivers = build_windowpilot_drivers(config)
    env = MultiWindowPhysicalEnvironment(
        layout.to_building_topology(),
        drivers,
        fixed_openings=config.get("fixed_openings") or {},
        initial_openings=snapshot.opening_states,
        require_write_ready=True,
    )
    observation, info = env.reset()
    readiness = info["physical_opening_readiness"]
    all_ready = all(
        item.get("physical_write_ready") is True
        for item in readiness.values()
    )
    payload = {
        "mode": "physical-preflight-only",
        "moves_hardware": False,
        "topology_id": layout.topology_id,
        "runtime_snapshot_sha256": snapshot.sha256(),
        "physical_openings": sorted(drivers),
        "fixed_openings": config.get("fixed_openings") or {},
        "readiness": readiness,
        "all_physical_openings_write_ready": all_ready,
        "observed_zones": sorted(observation["co2_ppm"]),
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0 if all_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
