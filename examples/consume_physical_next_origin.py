"""Smoke the physical-origin consumer into one subsequent controller plan.

This is contract evidence only. It never contacts hardware; the input reconcile
must already be a verified physical receipt from the WindowPilot capture path.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from airtrajectory.physical_origin import physical_next_origin_from_reconcile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("current_origin", type=Path)
    parser.add_argument("physical_reconcile", type=Path)
    parser.add_argument("--zone-id", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    current = json.loads(args.current_origin.read_text(encoding="utf-8"))
    reconcile = json.loads(args.physical_reconcile.read_text(encoding="utf-8"))
    receipt = physical_next_origin_from_reconcile(
        current_origin=current,
        reconcile=reconcile,
        zone_id=args.zone_id,
    )
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
