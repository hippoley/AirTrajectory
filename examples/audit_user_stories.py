"""Run the 15-story horizontal evidence gate against an audit JSON snapshot."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from airtrajectory.horizontal_audit import validate_horizontal_matrix


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--matrix",type=Path,default=Path("docs/user-story-horizontal-matrix.json"))
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    result=validate_horizontal_matrix(json.loads(a.matrix.read_text(encoding="utf-8")))
    report=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(report,encoding="utf-8")
    print(report,end="")
    return 0 if result["status"]=="PASS" else 1


if __name__=="__main__":
    raise SystemExit(main())
