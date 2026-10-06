"""Run the unified multi-space demo against a generated real CONTAM PRJ."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.demo_orchestrator import run_demo
from airtrajectory.demo_runtime import DemoRuntimeSnapshot
from airtrajectory.layout import LayoutContract


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prj", type=Path)
    parser.add_argument("provenance", type=Path)
    parser.add_argument(
        "--layout",
        type=Path,
        default=ROOT / "web" / "data" / "home_topology.fixed.json",
    )
    parser.add_argument("--steps", type=int, default=2)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    provenance=json.loads(args.provenance.read_text(encoding="utf-8"))
    layout=LayoutContract.from_file(args.layout)
    snapshot=DemoRuntimeSnapshot.resolve(layout)

    result=run_demo(
        snapshot,
        mode="contam",
        max_steps=args.steps,
        contam_prj_path=args.prj,
        contam_provenance=provenance,
        fixed_openings={"D1":100.0,"D2":100.0},
    )
    trajectory=result.trajectory
    payload={
        "marker":"GENERATED_CONTAM_TRAJECTORY_EXECUTED",
        "mode":result.mode,
        "topology_id":layout.topology_id,
        "runtime_snapshot_sha256":snapshot.sha256(),
        "trajectory":trajectory.to_dict(),
    }

    if trajectory.environment_kind!="contam":
        raise RuntimeError("trajectory environment_kind is not contam")
    if trajectory.context.get("demo_runtime_snapshot_sha256")!=snapshot.sha256():
        raise RuntimeError("CONTAM trajectory snapshot provenance mismatch")
    if len(trajectory.steps)!=args.steps:
        raise RuntimeError(
            f"unexpected trajectory length: {len(trajectory.steps)} != {args.steps}"
        )
    if not trajectory.steps:
        raise RuntimeError("CONTAM trajectory has no steps")
    first=trajectory.steps[0]
    action_ids={a.opening_id for a in first.executed_actions}
    if action_ids!={"W1","W2","W3","D1","D2"}:
        raise RuntimeError(f"unexpected executed opening set: {sorted(action_ids)}")
    flow=(first.next_observation or {}).get("path_flow_kg_s") or {}
    if set(flow)!={"W1","W2","W3","D1","D2"}:
        raise RuntimeError(f"missing CONTAM path-flow evidence: {sorted(flow)}")

    rendered=json.dumps(payload,indent=2,sort_keys=True)
    print(rendered)
    if args.out is not None:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(rendered+"\n",encoding="utf-8")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
