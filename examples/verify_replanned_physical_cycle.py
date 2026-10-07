"""Verify one persisted replanned physical cycle without contacting hardware."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.physical_cycle_verify import verify_persisted_physical_cycle


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None):
    parser=argparse.ArgumentParser(
        description=(
            "Independently verify persisted origin/planner/step/next-origin "
            "artifacts for one replanned physical field transition."
        )
    )
    parser.add_argument("--previous-origin",type=Path,required=True)
    parser.add_argument("--planner-receipt",type=Path,required=True)
    parser.add_argument("--step-summary",type=Path,required=True)
    parser.add_argument("--next-origin",type=Path,required=True)
    parser.add_argument("--out",type=Path)
    args=parser.parse_args(argv)

    result=verify_persisted_physical_cycle(
        previous_origin_receipt=_load(args.previous_origin),
        planner_payload=_load(args.planner_receipt),
        step_summary=_load(args.step_summary),
        next_origin_receipt=_load(args.next_origin),
    )
    rendered=json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)
    print(rendered)
    if args.out is not None:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(rendered+"\n",encoding="utf-8")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
