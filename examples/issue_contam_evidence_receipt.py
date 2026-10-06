"""Validate a calibration/measurement bundle and emit an immutable receipt."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.contam_calibration_evidence import issue_evidence_receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.bundle.read_text(encoding="utf-8"))
    receipt = issue_evidence_receipt(payload)
    rendered = json.dumps(receipt, indent=2, sort_keys=True)
    print(rendered)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
