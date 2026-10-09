"""Import an IFC model into AirTrajectory Layout Contract v0.1."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from airtrajectory.importers.ifc import import_ifc
from airtrajectory.topology_acceptance import verify_topology_runtime

def main():
    p=argparse.ArgumentParser()
    p.add_argument("ifc",type=Path)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    layout=import_ifc(args.ifc)
    args.out.write_text(json.dumps(layout.web_snapshot(),indent=2,sort_keys=True)+"\n",encoding="utf-8")
    receipt=verify_topology_runtime(layout)
    print(json.dumps(receipt,indent=2,sort_keys=True))
    return 0 if receipt["status"]=="PASS" else 1

if __name__=="__main__":
    raise SystemExit(main())
