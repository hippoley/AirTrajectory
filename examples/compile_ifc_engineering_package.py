"""Compile a reviewed, source-bound IFC engineering package through CONTAM."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from airtrajectory.layout import LayoutContract
from airtrajectory.ifc_engineering_package import compile_ifc_engineering_package

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--package",type=Path,required=True)
    p.add_argument("--layout",type=Path,required=True)
    p.add_argument("--ifc-readiness",type=Path,required=True)
    p.add_argument("--candidate-scope",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--receipt",type=Path,required=True)
    args=p.parse_args()
    def load(path): return json.loads(path.read_text(encoding="utf-8"))
    # Never generate a PRJ on a source mismatch, incomplete opening inventory,
    # absent approval or missing engineering bundles.
    receipt=compile_ifc_engineering_package(
        load(args.package),layout=LayoutContract.from_file(args.layout),
        readiness=load(args.ifc_readiness),scope=load(args.candidate_scope),
        out_path=str(args.out))
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":receipt.get("status"),"ifc_package":receipt["ifc_engineering_package"]},sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
