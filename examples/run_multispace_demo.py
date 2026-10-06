"""Run the multi-space / multi-window demo from one topology contract.

Default mode uses the deterministic toy backend and writes a trajectory artifact.
Physical mode is intentionally not auto-enabled: real WindowPilot endpoint mapping
must be supplied by an integration caller so hardware cannot be moved accidentally.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.demo_runtime import DemoRuntimeSnapshot
from airtrajectory.layout import LayoutContract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--layout",
        type=Path,
        default=Path("web/data/home_topology.fixed.json"),
    )
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--topology-revision", type=int, default=0)
    args = parser.parse_args()

    layout = LayoutContract.from_file(args.layout)
    snapshot = DemoRuntimeSnapshot.resolve(
        layout,
        topology_revision=args.topology_revision,
    )
    initial_co2 = {
        room.id: 1400.0 if room.id == "living" else 1100.0
        for room in layout.rooms
    }
    trajectory = snapshot.rollout_rule_policy(
        initial_co2=initial_co2,
        max_steps=args.steps,
    )

    payload = {
        "mode": "simulation",
        "topology_id": layout.topology_id,
        "topology_revision": snapshot.topology_revision,
        "runtime_snapshot_sha256": snapshot.sha256(),
        "opening_ids": sorted(snapshot.opening_states),
        "trajectory": trajectory.to_dict(),
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
