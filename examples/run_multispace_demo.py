"""Run the multi-space / multi-window demo from one topology contract.

Simulation and CONTAM use the same DemoRuntimeSnapshot, MultiWindowRuleAgent,
rollout path, and Trajectory schema. Physical execution stays behind the
separate read-only preflight/config gate so this CLI cannot move hardware by
accident.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.demo_orchestrator import run_demo
from airtrajectory.demo_runtime import DemoRuntimeSnapshot
from airtrajectory.layout import LayoutContract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--layout",
        type=Path,
        default=Path("web/data/home_topology.fixed.json"),
    )
    parser.add_argument(
        "--mode",
        choices=("simulation", "contam"),
        default="simulation",
    )
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--topology-revision", type=int, default=0)
    parser.add_argument("--contam-prj", type=Path)
    parser.add_argument("--contam-provenance", type=Path)
    args = parser.parse_args()

    layout = LayoutContract.from_file(args.layout)
    snapshot = DemoRuntimeSnapshot.resolve(
        layout,
        topology_revision=args.topology_revision,
    )

    if args.mode == "simulation":
        initial_co2 = {
            room.id: 1400.0 if room.id == "living" else 1100.0
            for room in layout.rooms
        }
        result = run_demo(
            snapshot,
            mode="simulation",
            max_steps=args.steps,
            initial_co2=initial_co2,
        )
    else:
        if args.contam_prj is None or args.contam_provenance is None:
            parser.error(
                "--mode contam requires --contam-prj and --contam-provenance"
            )
        provenance = json.loads(
            args.contam_provenance.read_text(encoding="utf-8")
        )
        result = run_demo(
            snapshot,
            mode="contam",
            max_steps=args.steps,
            contam_prj_path=args.contam_prj,
            contam_provenance=provenance,
            fixed_openings={"D1": 100.0, "D2": 100.0},
        )

    trajectory = result.trajectory
    payload = {
        "mode": result.mode,
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
