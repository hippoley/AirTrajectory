"""Offline semantic verification of a saved real-CONTAM policy benchmark artifact.

This verifies recorded solver-branch/benchmark consistency without importing
or invoking the simulator. It does not authenticate the solver execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from airtrajectory.layout import LayoutContract
from airtrajectory.policy_benchmark import verify_policy_benchmark_report


def verify_artifact(artifact: dict, layout: LayoutContract) -> dict:
    if artifact.get("marker") != "REAL_CONTAM_JOINT_GOLDEN_CASE_EXECUTED":
        raise ValueError("artifact is not a real CONTAM golden-case runner output")
    benchmark = artifact.get("policy_benchmark")
    case = artifact.get("golden_case")
    branches = artifact.get("branches")
    if not isinstance(benchmark, dict) or not isinstance(case, dict):
        raise ValueError("artifact lacks case or policy benchmark")
    if not isinstance(branches, list) or not branches:
        raise ValueError("artifact lacks raw solver branches")
    if case.get("topology_id") != layout.topology_id:
        raise ValueError("artifact topology differs from supplied layout")
    if artifact.get("trusted_for_promotion") is True:
        raise ValueError("uncommissioned solver output must not claim physical promotion")
    if not verify_policy_benchmark_report(
        report=benchmark, response={"branches": branches},
        case=case, topology=layout.to_building_topology(),
    ):
        raise ValueError("independent benchmark replay failed")
    encoded = json.dumps(artifact, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                         allow_nan=False).encode("utf-8")
    return {
        "status": "PASS",
        "verification": "independent-offline-policy-benchmark-replay-v0.1",
        "artifact_sha256": hashlib.sha256(encoded).hexdigest(),
        "topology_id": layout.topology_id,
        "branches_verified": len(branches),
        "evidence_boundary": "offline semantic replay; not solver authenticity or physical field evidence",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--layout", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    layout = LayoutContract.from_file(args.layout)
    result = verify_artifact(artifact, layout)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
