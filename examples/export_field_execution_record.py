"""Export AirTrajectory physical-cycle evidence as FieldExecutionRecord v0.1."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.conformance_record import build_field_execution_record


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None):
    parser=argparse.ArgumentParser(
        description=(
            "Project one persisted AirTrajectory physical cycle into the "
            "transport-neutral FieldExecutionRecord v0.1 semantic model."
        )
    )
    parser.add_argument("--cycle-summary",type=Path,required=True)
    parser.add_argument("--step-summary",type=Path)
    parser.add_argument("--verification-receipt",type=Path)
    parser.add_argument(
        "--test-case-id",
        default="airtrajectory.replanned_physical_cycle",
    )
    parser.add_argument(
        "--spec-clause-ref",
        action="append",
        default=[],
        help="Optional external/non-normative clause or discussion reference.",
    )
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args(argv)

    record=build_field_execution_record(
        cycle_summary=_load(args.cycle_summary),
        step_summary=(
            _load(args.step_summary)
            if args.step_summary is not None
            else None
        ),
        verification_receipt=(
            _load(args.verification_receipt)
            if args.verification_receipt is not None
            else None
        ),
        test_case_id=args.test_case_id,
        spec_clause_refs=args.spec_clause_ref,
        artifact_refs=[
            str(path)
            for path in (
                args.cycle_summary,
                args.step_summary,
                args.verification_receipt,
            )
            if path is not None
        ],
    )

    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(
        json.dumps(record,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print(json.dumps(record,ensure_ascii=False,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
