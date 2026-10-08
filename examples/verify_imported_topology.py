"""Verify an externally produced AirTrajectory topology contract.

This command is intentionally dependency-light and does not require a specific
IFC/gbXML/CAD parser. Any importer can emit Layout Contract v0.1 and use this
receipt to prove that the topology reaches the shared runtime path.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.layout import LayoutContract
from airtrajectory.topology_acceptance import verify_topology_runtime


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("layout",type=Path)
    parser.add_argument("--out",type=Path)
    args=parser.parse_args()

    layout=LayoutContract.from_file(args.layout)
    receipt=verify_topology_runtime(layout)
    payload={
        "schema_version":"0.1",
        "input":str(args.layout),
        "source_kind":layout.source_kind,
        "arbitrary_topology_import":layout.capabilities.get("arbitrary_topology_import"),
        "runtime_acceptance":receipt,
    }
    raw=json.dumps(payload,indent=2,sort_keys=True)+"\n"
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(raw,encoding="utf-8")
    print(raw,end="")
    return 0 if receipt["status"]=="PASS" else 1


if __name__=="__main__":
    raise SystemExit(main())
