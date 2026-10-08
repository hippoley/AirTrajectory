"""Inspect a real IFC model for AirTrajectory control readiness."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from airtrajectory.importers.ifc import inspect_ifc_control_readiness

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("ifc",type=Path)
    p.add_argument("--out",type=Path)
    p.add_argument("--require-ready",action="store_true")
    args=p.parse_args()
    report=inspect_ifc_control_readiness(args.ifc)
    raw=json.dumps(report,indent=2,sort_keys=True)+"\n"
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(raw,encoding="utf-8")
    print(raw,end="")
    if args.require_ready and report["status"]!="READY":
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
