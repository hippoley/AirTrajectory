"""Apply audited correction operations to an imported LayoutContract JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.layout import LayoutContract
from airtrajectory.layout_correction import correct_layout
from airtrajectory.topology_acceptance import verify_topology_runtime


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("layout",type=Path)
    parser.add_argument("operations",type=Path,help="JSON array of correction ops")
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    original=LayoutContract.from_file(args.layout)
    operations=json.loads(args.operations.read_text(encoding="utf-8"))
    if not isinstance(operations,list):
        raise ValueError("corrections file must contain an array")
    edited=correct_layout(original,operations)
    # web_snapshot is the public canonical UI handoff; verify physics/trajectory
    # readiness on the corrected graph before writing the new artifact.
    receipt=verify_topology_runtime(edited)
    if receipt["status"]!="PASS":
        print(json.dumps(receipt,indent=2))
        return 1
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(edited.web_snapshot(),indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(receipt,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
